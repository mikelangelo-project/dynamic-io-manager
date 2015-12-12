import os

import logging

from utils.aux import syscmd, ls, parse_user_list


__author__ = 'eyalmo'

MAX_CPUS = 32


def number_of_set_bits(i):
    # assuming no more then 32 bits
    i -= (i >> 1) & 0x55555555
    i = (i & 0x33333333) + ((i >> 2) & 0x33333333)
    return (((i + (i >> 4) & 0xF0F0F0F) * 0x1010101) & 0xffffffff) >> 24


class AffinityEntity:
    def __init__(self, cpu_mask=None, cpu_sequence=None):
        self.cpu_mask = None
        self.set_cpu_mask(cpu_mask=cpu_mask, cpu_sequence=cpu_sequence)

    def set_cpu_mask(self, cpu_mask=None, cpu_sequence=None):
        if cpu_mask is not None:
            self.cpu_mask = cpu_mask
        elif cpu_sequence is not None:
            self.cpu_mask = sum([1 << c for c in cpu_sequence])
        else:
            self.zero_cpu_mask()

    def zero_cpu_mask(self):
        self.cpu_mask = 0

    def merge_cpu_mask(self, cpu_mask):
        # logging.info("merge_cpu_mask: START")
        # logging.info("cpu_mask: %x" % (cpu_mask,))
        # logging.info("self.cpu_mask: %x" % (self.cpu_mask,))
        self.cpu_mask |= cpu_mask
        # logging.info("self.cpu_mask: %x" % (self.cpu_mask,))
        # logging.info("merge_cpu_mask: END")

    @property
    def cpu_list(self):
        return [c for c in self]

    def __str__(self):
        return "cpu_mask: %d" % (self.cpu_mask, )

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())

    def add_cpu(self, cpu):
        self.cpu_mask |= (1 << cpu)

    def remove_cpu(self, cpu):
        self.cpu_mask &= ~(1 << cpu)

    def first_cpu(self):
        cpu = 0
        # msg ("cpu_mask: %s, tmp_cpu: %d, tmp_cpu_mask: %s" % \
        #        (bin(self.cpu_mask), cpu, bin(1 << cpu)))
        while (self.cpu_mask & (1 << cpu)) == 0:
            if cpu >= MAX_CPUS:
                return -1
            # msg ("cpu_mask: %s, tmp_cpu: %d, tmp_cpu_mask: %s" % \
            #    (bin(self.cpu_mask), cpu, bin(1 << cpu)))
            cpu += 1
        return cpu

    def next_cpu(self, cpu):
        tmp_cpu = cpu + 1
        # msg ("cpu_mask: %s, tmp_cpu: %d, tmp_cpu_mask: %s" % \
        #        (bin(self.cpu_mask), tmp_cpu, bin(1 << tmp_cpu)))
        while (self.cpu_mask & (1 << tmp_cpu)) == 0:
            if tmp_cpu >= MAX_CPUS:
                return -1
            tmp_cpu += 1
            # msg ("cpu_mask: %s, tmp_cpu: %d, tmp_cpu_mask: %s" % \
            #    (bin(self.cpu_mask), tmp_cpu, bin(1 << tmp_cpu)))
        return tmp_cpu

    def __iter__(self):
        class CPUIterator:
            def __init__(self, ae):
                self.ae = ae
                self.cpu = ae.first_cpu()

            def next(self):
                if self.cpu == -1:
                    raise StopIteration
                temp_cpu = self.cpu
                self.cpu = self.ae.next_cpu(self.cpu)
                return temp_cpu

        return CPUIterator(self)

    def __contains__(self, cpu):
        return self.cpu_mask & (1 << cpu) != 0

    def __len__(self):
        return number_of_set_bits(self.cpu_mask)


def parse_cpu_mask_from_cpu_list(cpu_list):
    cpu_mask = 0
    for cpu in parse_user_list(cpu_list):
        cpu_mask += (1 << cpu)
    return cpu_mask


def parse_cpu_mask_from_pid(pid):
    return int(syscmd("taskset -ap %d" % (pid, )).split(":")[1].strip(), 16)


def set_cpu_mask_to_pid(pid, cpu_mask):
    syscmd("taskset -ap %x %s" % (cpu_mask, pid))


class Thread(AffinityEntity):
    def __init__(self, pid, idx, cpu_mask):
        AffinityEntity.__init__(self, cpu_mask=cpu_mask)
        self.pid = int(pid)
        self.idx = idx
        logging.info(str(self))

    def apply_cpu_mask(self):
        logging.info(str(self))
        # for tid in ls(os.path.join("/proc", str(self.pid), "task")):
        #    syscmd("taskset -p %x %s" % (self.cpu_mask, tid))
        syscmd("taskset -ap %x %s" % (self.cpu_mask, str(self.pid)))

    def __str__(self):
        return "pid: %d, cpus: %s" % (self.pid, AffinityEntity.__str__(self))

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
