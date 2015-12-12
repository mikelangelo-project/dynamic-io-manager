#!/usr/bin/python

import logging

from affinity_entity import Thread, parse_cpu_mask_from_cpu_list
from device import Device


class VM(Thread):
    def __init__(self, vm_info, backing_devices):
        Thread.__init__(self, int(vm_info["pid"]), vm_info["id"],
                        parse_cpu_mask_from_cpu_list(vm_info["cpu"]))

        logging.info(self.idx)
        logging.info(self.pid)
        logging.info(self.cpu_mask)

        self.devices = [Device(self, dev_info, backing_devices)
                        for dev_info in vm_info["devices"]]

    def remove_core(self, cpu_id):
        self.remove_cpu(cpu_id)
        self.apply_cpu_mask()

    def add_core(self, cpu_id):
        self.add_cpu(cpu_id)
        self.apply_cpu_mask()

    def set_cpu_mask(self, cpu_mask=None, cpu_sequence=None):
        self.set_cpu_mask(cpu_mask=cpu_mask, cpu_sequence=cpu_sequence)
        self.apply_cpu_mask()

    def __str__(self):
        return "VM: {pid: %d, id: %s}" % (self.pid, self.idx)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
