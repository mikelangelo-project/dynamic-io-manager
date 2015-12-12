from utils.affinity_entity import Thread
from utils.aux import warn
from utils.device import IRQ, get_irq_numbers
from utils.vhost import Vhost, vhost_worker_get_cpu_mask


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

    def __str__(self):
        devices_str = ", ".join([d.id for d in self.devices])
        cpu_mask = self.affinity_entities[0].cpu_mask \
            if self.affinity_entities else 0

        return "BackingDevice: id: %s, type: %s, devices: %s, cpu_mask: %x" % \
               (self.id, self.type, devices_str, cpu_mask)

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
