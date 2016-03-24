#!/usr/bin/python

import logging

from affinity_entity import Thread, parse_cpu_mask_from_cpu_list
from device import Device


class VM(Thread):
    def __init__(self, vm_info, backing_devices):
        Thread.__init__(self, int(vm_info["pid"]), vm_info["id"],
                        parse_cpu_mask_from_cpu_list(vm_info["cpu"]))
        self.devices = [Device(self, dev_info, backing_devices)
                        for dev_info in vm_info["devices"]]

    def remove_core(self, cpu_id):
        Thread.remove_cpu(self, cpu_id)
        Thread.apply_cpu_mask(self)

    def add_core(self, cpu_id):
        Thread.add_cpu(self, cpu_id)
        Thread.apply_cpu_mask(self)

    def set_cpu_mask(self, cpu_mask=None, cpu_sequence=None):
        Thread.set_cpu_mask(self, cpu_mask=cpu_mask, cpu_sequence=cpu_sequence)
        Thread.apply_cpu_mask(self)

    def __str__(self):
        return "VM: {pid: %d, id: %s, cpu_mask: %x}" % \
               (self.pid, self.idx, self.cpu_mask)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
