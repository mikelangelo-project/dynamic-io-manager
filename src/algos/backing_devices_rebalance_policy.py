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
        logging.info("backing devices configurations:")
        for w, bds in self.backing_devices_configurations.items():
            logging.info("vhost_workers %d:" % (w,))
            for bd_id, bd in bds.items():
                logging.info("\x1b[37m%s: %s\x1b[39m" % (bd_id, bd))

        self.cpu_configuration = {
            c: list(set([cpu for cpus in bd.values() for cpu in cpus]))
            for c, bd in self.backing_devices_configurations.items()
        }
        logging.info("cpu configurations:")
        for c, cl in self.cpu_configuration.items():
            logging.info("cpu %d: %s" % (c, cl))

        self.backing_devices = None
        self.vm_manager = None

    def initialize(self, backing_devices, io_workers, vm_manager):
        self.backing_devices = backing_devices
        self.vm_manager = vm_manager
        self.balance(io_workers)

    def balance(self, io_workers):
        logging.info("io_workers: %s" % (io_workers, ))

        backing_devices_conf = \
            self.backing_devices_configurations[len(io_workers)]
        cpus_conf = self.cpu_configuration[len(io_workers)]

        logging.info("backing devices configuration:")
        for bd_id, bd in backing_devices_conf.items():
            logging.info("\x1b[37m%s: %s\x1b[39m" % (bd_id, bd))
        logging.info("cpu configurations: %s" % (cpus_conf, ))

        if io_workers:
            cpu_mapping = {cpu_conf: io_worker.cpu
                           for cpu_conf, io_worker in zip(cpus_conf,
                                                          io_workers)}
        else:
            cpu_mapping = {cpu_conf: cpu
                           for cpu_conf, cpu in zip(cpus_conf,
                                                    self.vm_manager.cpus)}

        logging.info("cpu_mapping:")
        for cpu_conf, cpu in cpu_mapping.items():
            logging.info("\x1b[37m%s: %s\x1b[39m" % (cpu_conf, cpu))

        # moving vms to the correct cpu cores
        logging.info("\x1b[37mmoving backing devices to the correct cpu "
                     "cores\x1b[39m")
        for bd in self.backing_devices.values():
            cpu_mask = 0
            for c in backing_devices_conf[bd.id]:
                cpu_mask += (1 << cpu_mapping[c])
            logging.info("\x1b[37mbacking device %s: %x\x1b[39m" %
                         (bd.id, cpu_mask))
            bd.zero_cpu_mask()
            bd.merge_cpu_mask(cpu_mask)
            bd.apply_cpu_mask()


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
