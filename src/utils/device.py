import os
import logging

from affinity_entity import AffinityEntity, Thread
from aux import warn
from vhost import Vhost, vhost_worker_set_cpu_mask, vhost_worker_get_cpu_mask


IRQ_DIRECTORY = "/proc/irq"
IRQ_FILENAME = "/proc/interrupts"


def get_irq_numbers(irq_prefix):
    logging.info(irq_prefix)
    # get interrupt number from name
    with open(IRQ_FILENAME, "r") as irq_file:
        for line in irq_file:
            if irq_prefix not in line:
                continue
            yield line.split(":", 1)[0].strip()


class IRQ(AffinityEntity):
    # Assuming that the cpumask contains only a single cpu
    def __init__(self, irq_id, cpu_mask):
        self.id = int(irq_id)
        self.current_cpu = None
        AffinityEntity.__init__(self, cpu_mask)
        self.current_cpu = self.first_cpu()

        logging.info("assigning IRQ %d to CPU 0x%x" % (self.id, self.cpu_mask))
        if self.cpu_mask != 0:
            self.apply_cpu_mask()

    def add_cpu(self, cpu):
        logging.info("IRQ %d add CPU %d" % (self.id, cpu))
        AffinityEntity.add_cpu(self, cpu)

        if self.cpu_mask == 0:
            self.current_cpu = self.first_cpu()

    def apply_cpu_mask(self):
        if self.current_cpu == -1:
            self.current_cpu = self.first_cpu()
        logging.info("apply_cpu_mask: assigning IRQ %s to CPU %d" %
                     (self, self.current_cpu))
        with open(os.path.join(IRQ_DIRECTORY, str(self.id),
                               "smp_affinity_list"), "w") as affinity_file:
            affinity_file.write(str(self.current_cpu))

    def next_cpu(self, cpu=None):
        self.current_cpu = AffinityEntity.next_cpu(self,
                                                   self.current_cpu
                                                   if cpu is None else cpu)
        if self.current_cpu == -1:
            self.current_cpu = self.first_cpu()
        self.apply_cpu_mask()

    def __str__(self):
        mask_str = "Nan" if self.cpu_mask is None else "%x" % (self.cpu_mask,)
        return "id: %s, cpu_mask: %s, current_cpu: %s" % \
               (self.id, mask_str, self.current_cpu)

    def set_cpu_mask(self, cpu_mask=None, cpu_sequence=None):
        AffinityEntity.set_cpu_mask(self, cpu_mask=cpu_mask,
                                    cpu_sequence=cpu_sequence)
        logging.info("set_cpu_mask: %s" % (self,))

    def merge_cpu_mask(self, cpu_mask):
        AffinityEntity.merge_cpu_mask(self, cpu_mask)
        logging.info("merge_cpu_mask: %s" % (self,))


class BackingDevice:
    def __init__(self, backing_device_info):
        self.id = backing_device_info["id"]
        self.type = backing_device_info["type"]

        self.devices = set()

        if "physical" == self.type:
            self.affinity_entities = \
                BackingDevice.init_irqs(backing_device_info["interrupts"])
        elif "software" == self.type:
            self.affinity_entities = \
                BackingDevice.init_threads(backing_device_info["threads"])
        else:
            self.affinity_entities = []
            warn("Unknown backing device type: %s" % (self.type,))

        self.zero_cpu_mask()

    @staticmethod
    def init_irqs(interrupts_info):
        return [IRQ(irq_id, None)
                for irq in interrupts_info
                for irq_id in get_irq_numbers(irq["irq_prefix"])]

    @staticmethod
    def init_threads(threads_info):
        return [Thread(t["pid"], idx, None)
                for idx, t in enumerate(threads_info)]

    def remove_core(self, cpu_id):
        for ea in self.affinity_entities:
            ea.remove_cpu(cpu_id)
            ea.apply_cpu_mask()

    def add_core(self, cpu_id):
        for ea in self.affinity_entities:
            ea.add_cpu(cpu_id)
            ea.apply_cpu_mask()

    def zero_cpu_mask(self):
        for ea in self.affinity_entities:
            ea.zero_cpu_mask()

    def apply_cpu_mask(self):
        for ea in self.affinity_entities:
            ea.apply_cpu_mask()

    def merge_cpu_mask(self, cpumask):
        for ea in self.affinity_entities:
            ea.merge_cpu_mask(cpumask)

    def add_device(self, dev_id):
        devices = Vhost.INSTANCE.devices
        workers = Vhost.INSTANCE.workers

        self.devices.add(dev_id)
        worker = workers[devices[dev_id]["worker"]]
        cpu_mask = vhost_worker_get_cpu_mask(worker)
        self.merge_cpu_mask(cpu_mask)
        self.apply_cpu_mask()

    def update_cpu_mask(self, dev_id, old_cpu, new_cpu):
        devices = Vhost.INSTANCE.devices
        workers = Vhost.INSTANCE.workers

        if dev_id not in self.devices:
            # device not found
            return

        if old_cpu == new_cpu:
            # new change in cpu_mask
            return

        self.add_core(new_cpu)
        for dev in self.devices:
            if dev == dev_id:
                # skipping the given device
                continue
            worker = workers[devices[dev]["worker"]]
            if (vhost_worker_get_cpu_mask(worker) & (1 << old_cpu)) != 0:
                # we found another device that runs on old_cpu
                return

        # no other device of this backing device is running on old_cpu,
        # remove old_cpu
        self.remove_core(old_cpu)

    def next_cpu(self):
        for ea in self.affinity_entities:
            ea.next_cpu()


class Device:
    def __init__(self, vm, dev_info, backing_devices):
        self.id = dev_info["id"]
        self.vm = vm

        self.backing_device = None
        if "backing_device" in dev_info:
            self.backing_device = backing_devices[dev_info["backing_device"]]
            self.backing_device.add_device(self.id)

    def set_affinity_to_backing_devices(self, cpu_mask):
        vhost_worker_id = Vhost.INSTANCE.devices[self.id]["worker"]
        vhost_worker = Vhost.INSTANCE.workers[vhost_worker_id]
        vhost_worker_set_cpu_mask(vhost_worker, cpu_mask)

        if self.backing_device:
            self.backing_device.merge_cpu_mask(cpu_mask)
            self.backing_device.apply_cpu_mask()
