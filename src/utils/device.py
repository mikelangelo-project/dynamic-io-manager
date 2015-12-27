import logging
import os

from affinity_entity import AffinityEntity
from vhost import Vhost, vhost_worker_set_cpu_mask

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
        # logging.info("IRQ %d add CPU %d" % (self.id, cpu))
        AffinityEntity.add_cpu(self, cpu)

        if self.cpu_mask == 0:
            self.current_cpu = self.first_cpu()

    def apply_cpu_mask(self):
        if self.current_cpu == -1:
            self.current_cpu = self.first_cpu()
        # logging.info("apply_cpu_mask: assigning IRQ %s to CPU %d" %
        #              (self, self.current_cpu))
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
        # logging.info("set_cpu_mask: %s" % (self,))

    def merge_cpu_mask(self, cpu_mask):
        AffinityEntity.merge_cpu_mask(self, cpu_mask)
        # logging.info("merge_cpu_mask: %s" % (self,))


class Device:
    def __init__(self, vm, dev_info, backing_devices):
        self.id = dev_info["id"]
        self.vm = vm
        logging.info("Device %s, vm: %s" % (self.id, self.vm.idx))

        self.backing_device = None
        if "backing_device" in dev_info:
            self.backing_device = backing_devices[dev_info["backing_device"]]
            self.backing_device.add_device(self.id)
            # logging.info("backing device: %s" % (dev_info["backing_device"],))

    def set_affinity_to_backing_devices(self, cpu_mask):
        # logging.info("set affinity to backing device of Device %s, vm: %s" %
        #              (self.id, self.vm.idx))
        vhost_worker_id = Vhost.INSTANCE.devices[self.id]["worker"]
        vhost_worker = Vhost.INSTANCE.workers[vhost_worker_id]
        vhost_worker_set_cpu_mask(vhost_worker, cpu_mask)

        if self.backing_device:
            self.backing_device.merge_cpu_mask(cpu_mask)
            self.backing_device.apply_cpu_mask()
