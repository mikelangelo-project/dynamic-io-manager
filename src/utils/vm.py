#!/usr/bin/python

import os
import logging

from aux import ls
from affinity_entity import Thread, parse_cpu_mask_from_cpu_list
from device import Device


class VM:
    def __init__(self, vm_info, backing_devices):
        self.pid = int(vm_info["pid"])
        self.idx = vm_info["id"]

        logging.info(self.idx)
        logging.info(self.pid)
        self.vcpus = [Thread(tid, idx,
                             parse_cpu_mask_from_cpu_list(vm_info["cpu"]))
                      for idx, tid in enumerate(ls(os.path.join("/proc",
                                                                str(self.pid),
                                                                "task")))]
        self.devices = [Device(self, dev_info, backing_devices)
                        for dev_info in vm_info["devices"]]

    def remove_core(self, cpu_id):
        for t in self.vcpus:
            t.remove_cpu(cpu_id)
            t.apply_cpu_mask()

    def add_core(self, cpu_id):
        for t in self.vcpus:
            t.add_cpu(cpu_id)
            t.apply_cpu_mask()

    def set_cpu_mask(self, cpu_mask):
        for t in self.vcpus:
            t.set_cpu_mask(cpu_mask=cpu_mask)
            t.apply_cpu_mask()

    def __str__(self):
        return "VM: {pid: %d, id: %s}" % (self.pid, self.idx)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
