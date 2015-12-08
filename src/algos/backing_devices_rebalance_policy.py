import logging
from utils.aux import parse_user_list
from utils.vhost import Vhost

__author__ = 'eyalmo'


class BackingDevicesPreConfiguredBalancePolicy:
    def __init__(self, balancer_info):
        self.backing_devices_configurations = {
            int(conf["vhost_workers"]): {
                bd["id"]: list(parse_user_list(bd["cpu"]))
                for bd in conf["backing_devices"]
            }
            for conf in balancer_info["configurations"]
        }
        self.cpu_configuration = {
            c: list(set([cpu for cpus in bd.values() for cpu in cpus]))
            for c, bd in self.backing_devices_configurations.items()
        }
        self.backing_devices = None
        self.vm_manager = None

    def initialize(self, backing_devices, io_workers, vm_manager):
        self.backing_devices = backing_devices
        self.vm_manager = vm_manager
        self.balance(io_workers)

    def balance(self, io_workers):
        backing_devices_conf = \
            self.backing_devices_configurations[len(io_workers)]
        cpus_conf = self.cpu_configuration[len(io_workers)]
        if io_workers:
            cpu_mapping = {cpu_conf: io_worker.cpu
                           for cpu_conf, io_worker in zip(cpus_conf,
                                                          io_workers)}
        else:
            cpu_mapping = {cpu_conf: cpu
                           for cpu_conf, cpu in zip(cpus_conf,
                                                    self.vm_manager.cpus)}

        # moving vms to the correct cpu cores
        logging.info("\x1b[37mmoving backing devices to the correct cpu "
                     "cores\x1b[39m")
        for bd in self.backing_devices:
            new_cpu_sequence = [cpu_mapping[c] for c in bd[bd.idx]]
            logging.info("\x1b[37mbacking device %s: %s\x1b[39m" %
                         (bd.idx, new_cpu_sequence))
            cpu_mask = 0
            for c in backing_devices_conf[bd.idx]:
                cpu_mask += (1 << cpu_mapping[c])
            bd.set_cpu_mask(cpu_mask)


class BackingDevicesPolicy:
    def __init__(self):
        self.backing_devices = None
        self.vm_manager = None

    def initialize(self, backing_devices, io_workers, vm_manager):
        self.backing_devices = backing_devices
        self.vm_manager = vm_manager
        self.balance(io_workers)

    def _disable_shared_workers(self):
        for bd in self.backing_devices.values():
            bd.zero_cpu_mask()
            for dev in bd.devices:
                for t in dev.vm.vcpus:
                    bd.merge_cpu_mask(t.cpu_mask)
            bd.apply_cpu_mask()

    def balance(self, io_workers):
        if io_workers:
            self._disable_shared_workers()
            return

        devices = Vhost.INSTANCE.devices
        cpu_mapping = {io_worker.id: io_worker.cpu for io_worker in io_workers}
        for bd in self.backing_devices.values():
            bd.zero_cpu_mask()
            for dev in bd.devices:
                vhost_worker_id = devices[dev.id]["worker"]
                bd.add_core(cpu_mapping[vhost_worker_id])
            bd.apply_cpu_mask()
