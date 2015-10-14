import logging

from utils.vhost import Vhost
from algos.vq_classifier import LOW_USAGE

__author__ = 'eyalmo'


def divide_ceil(num1, num2):
    int1 = int(num1)
    int2 = int(num2)
    return int1 / int2 + (1 if int1 % int2 != 0 else 0)


class IOCoresPreConfiguredBalancePolicy:
    def __init__(self, balancer_info, devices):
        vms_confs = {
            len(conf["vhost_workers"]): {
                vm["id"]: vm["vhost_worker"]
                for vm in conf["vms"]}
            for conf in balancer_info["configurations"]}

        self.devices_configurations = {
            c_id: {dev.id: vms_conf[dev.vm.idx] for dev in devices}
            for c_id, vms_conf in vms_confs.items()
        }

        self.workers_configurations = {
            len(conf["vhost_workers"]): [w["id"] for w in conf["vhost_workers"]]
            for conf in balancer_info["configurations"]
        }
        logging.info("workers_configurations: %s" %
                     (self.workers_configurations,))

    def _balance(self, io_workers):
        devices = Vhost.INSTANCE.devices
        workers = Vhost.INSTANCE.workers
        # logging.info("Vhost.INSTANCE.devices: %s" % (devices,))
        workers_conf = self.workers_configurations[len(io_workers)]
        logging.info("workers_conf: %s" % (workers_conf,))
        devices_conf = self.devices_configurations[len(io_workers)]
        logging.info("devices_conf: %s" % (devices_conf,))
        worker_mapping = {worker_conf: workers[worker.id]
                          for worker_conf, worker in zip(workers_conf,
                                                         io_workers)}

        balance_changes = {}
        # move devices to the correct workers

        for dev_id, dev in devices.items():
            dev_conf = devices_conf[dev_id]
            if dev["worker"] == worker_mapping[dev_conf]:
                continue
            balance_changes[dev_id] = (workers[dev["worker"]],
                                       worker_mapping[dev_conf])

        # logging.info(balance_changes)
        return balance_changes

    def balance_after_addition(self, io_workers, new_worker_id):
        """
        Re-balance the system after adding a new io worker thread
        :param io_workers: The existing IO worker thread, including the newly
        added thread
        :param new_worker_id: The newly added worker thread id
        """
        logging.info("\x1b[37mbalance_after_addition:\x1b[39m worker_id %s" %
                     (new_worker_id,))
        logging.info("io_workers %s" % (io_workers,))
        return self._balance(io_workers)

    def balance_before_removal(self, io_workers, worker_id):
        """
        Re-balance the system after removing an io worker thread
        :param io_workers: The existing IO worker thread, including the io
        thread for removal
        :param worker_id: The worker thread id for removal
        """
        logging.info("\x1b[37mbalance_after_addition:\x1b[39m worker_id %s" %
                     (worker_id,))
        logging.info("io_workers %s" % (io_workers,))
        remaining_workers = [w for w in io_workers if w.id != worker_id]
        logging.info("remaining_workers %s" % (remaining_workers,))
        return self._balance(remaining_workers)

    @staticmethod
    def balance():
        return {}


class BalanceByDeviceNumberPolicy:
    def __init__(self):
        pass

    @staticmethod
    def balance_after_addition(io_workers, worker_id):
        logging.info("\x1b[37mbalance_after_addition:\x1b[39m worker_id %s" %
                     (worker_id,))
        balance_changes = {}
        vhost = Vhost.INSTANCE
        # get all devices located in the socket of the removed worker
        remaining_workers = [w for w_id, w in vhost.workers.items()
                             if w_id != worker_id]

        device_count = sum(len(w["dev_list"]) for w in remaining_workers)
        max_devices_per_worker = divide_ceil(device_count,
                                             len(remaining_workers) + 1)
        logging.info("device_count: %d, max_devices_per_worker: %d" %
                     (device_count, max_devices_per_worker))

        new_worker = vhost.workers[worker_id]

        for w in sorted(remaining_workers,
                        key=lambda _w: device_count - len(_w["dev_list"])):
            if len(w["dev_list"]) > max_devices_per_worker:
                balance_changes.update({dev_id: (w, new_worker)
                                        for dev_id in
                                        w["dev_list"][max_devices_per_worker:]})
                continue

        # logging.info(balance_changes)
        return balance_changes

    @staticmethod
    def balance_before_removal(io_workers, worker_id):
        logging.info("\x1b[37mbalance_before_removal:\x1b[39m worker_id %s" %
                     (worker_id,))
        balance_changes = {}
        workers = Vhost.INSTANCE.workers
        # get all unassigned devices in socket
        worker_for_removal = workers[worker_id]
        unassigned_devices_ids = worker_for_removal["dev_list"]

        remaining_workers = [w for w_id, w in workers.items()
                             if w_id != worker_id]

        max_devices_per_worker = \
            divide_ceil((sum(len(w["dev_list"])
                             for w in remaining_workers) +
                         len(unassigned_devices_ids)), len(remaining_workers))

        logging.info(max_devices_per_worker)
        logging.info([w["id"] for w in remaining_workers])
        logging.info(unassigned_devices_ids)
        for w in remaining_workers:
            n = max_devices_per_worker - len(w["dev_list"])
            balance_changes.update(
                {dev_id: (worker_for_removal, w)
                 for dev_id in unassigned_devices_ids[:n]})
            unassigned_devices_ids = unassigned_devices_ids[n:]

        # logging.info(balance_changes)
        return balance_changes

    @staticmethod
    def balance():
        return {}

class BalanceByGroupingPolicy:
    """
    First we divide the devices into two groups: active and inactive devices
    which are categorized the vq_classifier class). Afterwards, we take the
    active devices connected to the same backing device and bunch them into
    group. The last step is dividing the groups into cores while keep as much of
    them on the same core.

    """
    def __init__(self, devices, backing_devices_manager):
        self.backing_device_groups = \
            {bd_id: []
             for bd_id in backing_devices_manager.backing_devices.keys()}
        for d in devices:
            bd_id = d.backing_device.id
            self.backing_device_groups[bd_id].append(d.id)

    def balance_after_addition(self, io_workers, new_worker_id):
        logging.info("\x1b[37mbalance_after_addition:\x1b[39m worker_id %s" %
                     (new_worker_id,))
        balance_changes = {}
        workers = Vhost.INSTANCE.workers
        devices = Vhost.INSTANCE.devices

        active_devices = {d_id: d for d_id, d in devices.items()
                          if d["classification"] != LOW_USAGE}
        inactive_devices = {d_id: d for d_id, d in devices.items()
                            if d["classification"] == LOW_USAGE}

        active_groups = {bd_id: [active_devices[d_id] for d_id in bdg]
                         for bd_id, bdg in self.backing_device_groups.items()}

        remaining_workers = io_workers
        active_groups_len = 1
        while active_groups_len > 0:
            found = False
            new_worker = remaining_workers[0]
            remaining_workers = remaining_workers[1:]
            active_groups_len = sum(len(ag) for ag in active_groups.values())
            max_active_devices_per_worker = divide_ceil(active_groups_len,
                                                        len(remaining_workers))
            # take only groups with the exact number of devices
            for bd_id, ag in active_groups.items():
                if len(ag) != max_active_devices_per_worker:
                    continue
                for d in ag:
                    old_worker = workers[d["worker"]]
                    if old_worker["id"] == new_worker["id"]:
                        continue
                    balance_changes[d["id"]] = (old_worker, new_worker)
                found = True
                del active_groups[bd_id]
                break

            if found:
                continue

            # take only groups with the more devices then the number needed
            for bd_id, ag in active_groups.items():
                if len(ag) < max_active_devices_per_worker:
                    continue
                for d in ag[:max_active_devices_per_worker]:
                    old_worker = workers[d["worker"]]
                    if old_worker["id"] == new_worker["id"]:
                        continue
                    balance_changes[d["id"]] = (old_worker, new_worker)
                found = True
                active_groups[bd_id] = ag[max_active_devices_per_worker:]

            if found:
                continue

            # take groups with the less devices then the number needed
            for bd_id, ag in active_groups.items():
                if len(ag) < max_active_devices_per_worker:
                    continue
                for d in ag[:max_active_devices_per_worker]:
                    old_worker = workers[d["worker"]]
                    if old_worker["id"] == new_worker["id"]:
                        continue
                    balance_changes[d["id"]] = (old_worker, new_worker)
                active_groups[bd_id] = ag[max_active_devices_per_worker:]

        # logging.info(balance_changes)
        return balance_changes

    def balance_before_removal(self, io_workers, worker_id):
        logging.info("\x1b[37mbalance_before_removal:\x1b[39m worker_id %s" %
                     (worker_id,))
        balance_changes = {}
        workers = Vhost.INSTANCE.workers
        # get all unassigned devices in socket
        worker_for_removal = workers[worker_id]
        unassigned_devices_ids = worker_for_removal["dev_list"]

        remaining_workers = [w for w_id, w in workers.items()
                             if w_id != worker_id]

        max_devices_per_worker = \
            divide_ceil((sum(len(w["dev_list"])
                             for w in remaining_workers) +
                         len(unassigned_devices_ids)), len(remaining_workers))

        logging.info(max_devices_per_worker)
        logging.info([w["id"] for w in remaining_workers])
        logging.info(unassigned_devices_ids)
        for w in remaining_workers:
            n = max_devices_per_worker - len(w["dev_list"])
            balance_changes.update(
                {dev_id: (worker_for_removal, w)
                 for dev_id in unassigned_devices_ids[:n]})
            unassigned_devices_ids = unassigned_devices_ids[n:]

        # logging.info(balance_changes)
        return balance_changes

    @staticmethod
    def balance():
        return {}




# TODO: add a balancer that balances each device type individually

# TODO: add a balancer that balances by trying to give a throughput device that
# needs more processing time
