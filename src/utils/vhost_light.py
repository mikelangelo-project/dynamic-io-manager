import logging

import kernel_mapper

from get_cycles.get_cycles import Cycles
from aux import Timer

from vhost_raw import VhostWorker, VhostDevice, VhostVirtqueue

# RAW_FIELD_SIZE = 8


class ProcessCPUUsageCounterBase:
    def __init__(self, pid):
        self.pid = pid

        self.current = None
        self.delta = 0

    def __str__(self):
        return "%s(pid=%s, current=%d, delta=%d)" % \
                (self.__class__, self.pid, self.current, self.delta)


class ProcessCPUUsageCounterRaw(ProcessCPUUsageCounterBase):
    file_path = "/sys/class/stats/pidstat"

    def __init__(self, pid):
        ProcessCPUUsageCounterBase.__init__(self, pid)
        # logging.info("pid: %s" % (pid,))
        with open(ProcessCPUUsageCounterRaw.file_path, "w") as f:
            f.write("%d\n" % (pid,))
        utime_addr, stime_addr = None, None
        with open(ProcessCPUUsageCounterRaw.file_path, "r") as f:
            for line in f:
                utime_addr, stime_addr = line.strip().split()
                utime_addr, stime_addr = \
                    long(utime_addr, 16), long(stime_addr, 16)
        # logging.info("kernel_address: %lx" % (utime_addr,))
        self.readers = [kernel_mapper.Counter(utime_addr),
                        kernel_mapper.Counter(stime_addr)]

        self.current = self.readers[0].read() + self.readers[1].read()

    def update(self):
        value = self.readers[0].read() + self.readers[1].read()
        self.delta = value - self.current
        logging.info("%d: value: %d delta: %d" % (self.pid, value, self.delta))
        self.current = value
        return self.delta


class VhostLight:
    def __init__(self, vhost):
        self.vhost = vhost
        self.workers = {}
        self.devices = {}
        self.queues = {}

        self.cycles = VhostCyclesCounter("cycles")
        self.work_cycles = VhostWorkCyclesCounter("work_cycles")
        self.softirq_interference = \
            VhostSoftirqInterferenceCounter("softirq_interference")

        self.per_worker_counters = {
            "cpu_usage_counter": VhostCPUUsageCounter("cpu_usage_counter")
        }
        self.per_queue_counters = \
            {"handled_bytes": VhostHandledBytesCounter("handled_bytes")}

        self._initialize()

        self.work_cycles.initialize(self.vhost.vhost,
                                    self.vhost.vhost["cycles"])
        self.cycles.initialize(self.vhost.vhost, self.vhost.vhost["cycles"])
        self.softirq_interference.initialize(self.vhost.vhost,
                                             self.vhost.vhost["cycles"])

        for c in self.per_worker_counters.values():
            c.initialize(self.vhost.vhost)

        for c in self.per_queue_counters.values():
            c.initialize(self.vhost.vhost)

    def _initialize(self):
        # timer = Timer("Timer vhost light _initialize")

        for w_id in self.vhost.workers.keys():
            self.workers[w_id] = VhostWorker(w_id)
        # timer.checkpoint("initialize workers")

        for d_id in self.vhost.devices.keys():
            self.devices[d_id] = VhostDevice(d_id)
        # timer.checkpoint("initialize devices")

        for vq_id in self.vhost.queues.keys():
            self.queues[vq_id] = VhostVirtqueue(vq_id)
        # timer.checkpoint("initialize queues")
        # timer.checkpoint("done")

    def update(self, rescan=False):
        # timer = Timer("Timer vhost light update")
        if rescan:
            self.workers = {}
            self.devices = {}
            self.queues = {}
            self._initialize()
            for c in self.per_worker_counters.values():
                c.update_workers(self.vhost.workers.values())
            # timer.checkpoint("rescan")

        self.cycles.update(self.vhost.vhost, [self.vhost.vhost])
        self.work_cycles.update(self.vhost.vhost, self.workers.values())
        self.softirq_interference.update(self.vhost.vhost,
                                         self.workers.values())
        # timer.checkpoint("misc")

        for c in self.per_worker_counters.values():
            c.update(self.vhost.vhost, self.workers.values())
        # timer.checkpoint("per_worker_counters")
        for c in self.per_queue_counters.values():
            c.update(self.vhost.vhost, self.queues.values())
        # timer.checkpoint("per_queue_counters")
        # timer.done()


class VhostCounterBase:
    def __init__(self, name, element_name=None):
        self.name = name
        self.element_name = element_name if element_name is not None else name

        self.total = "total_%s" % (self.name,)
        self.last_epoch = "%s_last_epoch" % (self.name,)

        self.last_value = 0
        self.delta = 0

    def initialize(self, vhost, initial_value=0):
        Cycles.initialize()
        vhost[self.total] = initial_value

    def update(self, vhost, total):
        last_epoch = vhost[self.last_epoch] = vhost[self.total]
        vhost[self.total] = total

        self.delta = total - last_epoch
        return self.delta


class VhostCyclesCounter(VhostCounterBase):
    def __init__(self, name, element_name=None):
        VhostCounterBase.__init__(self, name, element_name)

    def update(self, vhost, elements):
        return VhostCounterBase.update(self, vhost, Cycles.get_cycles())


class VhostWorkCyclesCounter(VhostCounterBase):
    def __init__(self, name):
        VhostCounterBase.__init__(self, name, "total_work_cycles")

    def update(self, vhost, elements):
        total = sum(e.total_work_cycles for e in elements)
        return VhostCounterBase.update(self, vhost, total)


class VhostSoftirqInterferenceCounter(VhostCounterBase):
    def __init__(self, name):
        VhostCounterBase.__init__(self, name, "ksoftirqs")

    def update(self, vhost, elements):
        total = sum(e.ksoftirqs for e in elements)
        return VhostCounterBase.update(self, vhost, total)


class VhostCPUUsageCounter(VhostCounterBase):
    def __init__(self, name):
        VhostCounterBase.__init__(self, name, "cpu_usage_counter")
        self.workers_cpu_usage = {}

    def update_workers(self, workers):
        self.workers_cpu_usage = {
            ProcessCPUUsageCounterRaw(w["pid"]) for w in workers
        }
        for c in self.workers_cpu_usage:
            c.update()

    def update(self, vhost, elements):
        total = sum(c.update() for c in self.workers_cpu_usage)
        return VhostCounterBase.update(self, vhost, total)


class VhostHandledBytesCounter(VhostCounterBase):
    def __init__(self, name):
        VhostCounterBase.__init__(self, name, "handled_bytes")

    def update(self, vhost, elements):
        total = sum(e.handled_bytes for e in elements)
        return VhostCounterBase.update(self, vhost, total)
