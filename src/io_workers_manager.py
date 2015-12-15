import logging

from utils.vhost import Vhost, vhost_write, vhost_read, \
    vhost_worker_set_cpu_mask, get_cpu_usage
from utils.io_worker import IOWorker

__author__ = 'eyalmo'


class IOWorkersManager:
    def __init__(self, devices, vm_manager, backing_devices_manager,
                 io_workers_info,
                 vq_classifier, poll_policy, throughput_policy, latency_policy,
                 io_core_policy=None, balance_policy=None, regret_policy=None):
        self.io_workers = [IOWorker(w_info) for w_info in io_workers_info]
        self.backing_devices_manager = backing_devices_manager

        self.vq_classifier = vq_classifier
        self.poll_policy = poll_policy
        self.throughput_policy = throughput_policy
        self.latency_policy = latency_policy

        self.io_core_policy = io_core_policy
        self.balance_policy = balance_policy
        self.regret_policy = regret_policy

        self.devices = devices

        self.vm_manager = vm_manager

        self.cooling_off_period = 1  # 20
        self.epochs_last_action = 0

    def initialize(self):
        logging.info("\x1b[37mIOWorkersManager initialize\x1b[39m")
        shared_workers = len(self.io_workers) > 0

        self.vq_classifier.initialize()
        self.poll_policy.initialize(shared_workers)
        self.throughput_policy.initialize()
        self.latency_policy.initialize()
        self.backing_devices_manager.initialize(self.io_workers,
                                                self.vm_manager)
        self.regret_policy.initialize()

    def update_io_core_number(self):
        shared_workers = len(self.io_workers) > 0
        self.throughput_policy.calculate_load(shared_workers)

        self.epochs_last_action += 1
        if self.epochs_last_action <= self.cooling_off_period:
            return

        if not shared_workers:
            should_start, suggested_io_cores = \
                self.throughput_policy.should_start_shared_worker()
            if not should_start:
                return
            self.epochs_last_action = 0
            logging.info("\x1b[33menable shared IO workers.\x1b[39m")
            logging.info("\x1b[33madd a new IOcore\x1b[39m")

            cpu_ids = self.vm_manager.remove_core(number=suggested_io_cores)
            for cpu_id in cpu_ids:
                self.io_core_policy.add(cpu_id)
            self.enable_shared_workers(cpu_ids)
            return

        if self.throughput_policy.should_stop_shared_worker():
            self.epochs_last_action = 0
            logging.info("\x1b[33mdisable shared IO workers.\x1b[39m")
            logging.info("\x1b[33mremove IOcore\x1b[39m")
            # remove the IO core
            cpu_id = self.io_core_policy.remove()
            self.vm_manager.add_core(cpu_id)
            self.disable_shared_workers()
            self.vm_manager.disable_shared_workers()
            return

        add_io_core, can_remove_io_core = \
            self.throughput_policy.should_update_core_number()
        remove_io_core, can_add_io_core = \
            self.vm_manager.should_update_core_number()

        if add_io_core and can_add_io_core:
            self.epochs_last_action = 0
            logging.info("\x1b[33madd a new IOcore\x1b[39m")
            cpu_id = self.vm_manager.remove_core()
            if self.regret_policy.should_regret():
                self.vm_manager.add_core(cpu_id)
                return
            self.io_core_policy.add(cpu_id)
            new_worker_id = self._add_io_worker(cpu_id)
            self.io_workers.append(IOWorker({"id": new_worker_id,
                                             "cpu": cpu_id}))
            balance_changes = \
                self.balance_policy.balance_after_addition(self.io_workers,
                                                           [new_worker_id])
            self._move_devices(balance_changes)
            return

        if not remove_io_core or not can_remove_io_core:
            return

        logging.info("\x1b[33mremove IOcore\x1b[39m")
        self.epochs_last_action = 0
        # remove the IO core
        cpu_id = self.io_core_policy.remove()
        removed_worker = [w for w in Vhost.INSTANCE.workers.values()
                          if w["cpu"] == cpu_id][0]
        removed_worker_id = removed_worker["id"]

        balance_changes = \
            self.balance_policy.balance_before_removal(self.io_workers,
                                                       removed_worker_id)
        self._move_devices(balance_changes)
        self.backing_devices_manager.update()
        if self.regret_policy.should_regret():
            undo_balance_changes = {}
            for dev_id, (old_worker, new_worker) in balance_changes.items():
                undo_balance_changes[dev_id] = (new_worker, old_worker)
            self._move_devices(undo_balance_changes)
            return

        self._remove_io_worker(removed_worker)
        self.io_workers = [w for w in self.io_workers
                           if w.id != removed_worker_id]
        logging.info("Removed Worker: {id: %s, cpu: %d}" %
                     (removed_worker["id"], cpu_id))

        self.vm_manager.add_core(cpu_id)

    def update_balance(self):
        if self.epochs_last_action <= self.cooling_off_period:
            return

        balance_changes = self.balance_policy.balance()
        if not balance_changes:
            return
        self._move_devices(balance_changes)

    def update_polling(self):
        if self.epochs_last_action <= self.cooling_off_period:
            return

        self.poll_policy.update_polling()

    def update_vq_classifications(self):
        can_update = self.epochs_last_action > self.cooling_off_period
        self.vq_classifier.update_classifications(can_update)

    def _move_devices(self, balance_changes):
        logging.info("\x1b[37mMoving devices:\x1b[39m")
        if not balance_changes:
            logging.info("no balance changes")
            return

        for dev_id, (old_worker, new_worker) in balance_changes.items():
            logging.info("\x1b[37mdev: %s from worker: %s to worker: %s"
                         "\x1b[39m\n" %
                         (dev_id, old_worker["id"], new_worker["id"]))
            vhost_write(Vhost.INSTANCE.devices[dev_id], "worker",
                        new_worker["id"])
            Vhost.INSTANCE.devices[dev_id]["worker"] = new_worker["id"]

            new_worker["dev_list"].append(dev_id)
            old_worker["dev_list"].remove(dev_id)

        self.backing_devices_manager.balance(self.io_workers)

    def enable_shared_workers(self, io_cores):
        vhost = Vhost.INSTANCE
        worker_ids = \
            sorted(vhost.workers.keys(),
                   key=lambda w_id: int(w_id.split(".")[1]))[:len(io_cores)]

        # initialize the io workers
        logging.info("initialize the io workers")
        self.io_workers = []
        for worker_id, io_core in zip(worker_ids, io_cores):
            worker_ids.add(worker_id)
            self.io_workers.append(IOWorker({"id": worker_id, "cpu": io_core}))
            vhost_worker_set_cpu_mask(vhost.workers[worker_id], 1 << io_core)
            vhost.workers[worker_id]["cpu"] = io_core

        # move all devices to the workers
        logging.info("move all devices to the workers")
        balance_changes = \
            self.balance_policy.balance_after_addition(self.io_workers,
                                                       worker_ids)
        self._move_devices(balance_changes)

        # notify poll policy that we moved to shared worker configuration
        logging.info("notify poll policy that we moved to shared worker "
                     "configuration")
        self.poll_policy.enable_shared_workers()

        # remove all workers except the ones in use
        logging.info("remove all workers except the ones in use")
        for worker in vhost.workers.values():
            if worker["id"] in worker_ids:
                continue
            self._remove_io_worker(worker)

    def disable_shared_workers(self):
        self.poll_policy.disable_shared_workers()
        self.io_workers = []
        vhost = Vhost.INSTANCE
        # create a worker for each device
        for dev in self.devices[1:]:
            worker_id = self._add_io_worker()
            vhost_write(vhost.devices[dev.id], "worker", worker_id)

    @staticmethod
    def _add_io_worker(new_io_core=0):
        # add a new worker to the I/O cores
        vhost = Vhost.INSTANCE

        vhost_write(vhost.workersGlobal, "create", new_io_core)
        new_worker_id = vhost_read(vhost.workersGlobal, "create").strip()
        vhost.update_all_entries_with_id(new_worker_id)
        vhost.workers[new_worker_id]["cpu_usage_counter"] = \
            get_cpu_usage(vhost.workers[new_worker_id]["pid"])
        # vhost.workers[new_worker_id]["cpu_usage_counter"] = \
        #     ProcessCPUUsageCounter(new_worker_id)
        vhost_worker_set_cpu_mask(vhost.workers[new_worker_id],
                                  1 << new_io_core)
        # logging.info("Added Worker: {id: %s, cpu: %d}" % (new_worker_id,
        #                                                   new_io_core))
        return new_worker_id

    @staticmethod
    def _remove_io_worker(removed_worker):
        # logging.info("removed_worker: %s" % (removed_worker["id"],))
        # remove the worker from the cores
        vhost = Vhost.INSTANCE
        workers = vhost.workers

        # lock the worker
        vhost_write(removed_worker, "locked", 1)
        removed_worker["locked"] = 1

        # remove the worker from the workers dictionary
        # removed_worker_dev_ids = vhost_read(removed_worker,
        #                                     "dev_list").strip().split("\t")
        # logging.info("removed_worker_dev_ids: %s" % (removed_worker_dev_ids,))
        # assert not removed_worker_dev_ids

        del workers[removed_worker["id"]]
        vhost_write(vhost.workersGlobal, "remove", removed_worker["id"])
