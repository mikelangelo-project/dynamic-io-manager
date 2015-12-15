import re
import logging

from utils.aux import spilt_output_into_rows
from utils.aux import syscmd, err


class UpTimeCounter:
    regex = re.compile("\s*(\d+.?\d*)\s+(\d+.?\d*)\s*")
    file_path = "/proc/uptime"

    @staticmethod
    def _parse():
        with open(UpTimeCounter.file_path, "r") as up_time_file:
            for row in spilt_output_into_rows(up_time_file):
                # logging.info(row)
                r = UpTimeCounter.regex.match(row)
                if r:
                    # logging.info("found up time!")
                    g = r.groups()
                    return float(g[0]), float(g[1])

        err("failed to find up time!")

    def __init__(self):
        self.up_time, self.idle = UpTimeCounter._parse()
        self.up_time_diff = 0
        self.idle_diff = 0

    def update(self):
        old_up_time, old_idle = self.up_time, self.idle
        self.up_time, self.idle = UpTimeCounter._parse()
        self.up_time_diff = self.up_time - old_up_time
        self.idle_diff = self.idle - old_idle


class IRQCounter:
    irq_regexp = re.compile("\s*\d+\s*:\s*")
    file_path = "/proc/interrupts"

    @staticmethod
    def _parse(cpus):
        interrupts = [0 for _ in xrange(cpus)]
        with open(IRQCounter.file_path, "r") as up_time_file:
            iterator = iter(spilt_output_into_rows(up_time_file))
            next(iterator)
            for row in iterator:
                # logging.info(row)
                values = row.split()
                if not IRQCounter.irq_regexp.match(values[0]):
                    continue
                for i in xrange(len(interrupts)):
                    interrupts[i] += int(values[i+1])

        return interrupts

    def __init__(self, cpus):
        self.cpus = cpus
        self.interrupts = IRQCounter._parse(self.cpus)
        self.interrupts_diff = self.interrupts

    def update(self):
        old = self.interrupts
        self.interrupts = IRQCounter._parse(self.cpus)
        self.interrupts_diff = [e - s for e, s in zip(self.interrupts, old)]

    def __iter__(self):
        return self.interrupts_diff.__iter__()

    def __getitem__(self, index):
        return self.interrupts_diff[index]

    def __len__(self):
        return len(self.interrupts_diff)


class CPUStatCounter:
    global_cpu_regex = \
        re.compile("cpu\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                   "(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")
    per_cpu_regex = \
        re.compile("cpu(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+"
                   "(\d+)\s+(\d+)\s+(\d+)\s+(\d+)")
    context_switches_regex = \
        re.compile("ctxt\s+(\d+)")

    common_fields = ["user", "nice", "system", "idle", "iowait", "irq",
                     "softirq", "steal", "guest", "guest_nice"]
    per_cpu_fields = ["id"] + common_fields
    global_cpu_fields = common_fields + ["ctxt"]

    def __init__(self, raw_str=None):
        self.per_cpu_counters = []
        self.global_cpu_counters = \
            [0 for _ in xrange(len(CPUStatCounter.global_cpu_fields))]
        if not raw_str:
            return

        for row in spilt_output_into_rows(raw_str):
            # logging.info(row)
            r = CPUStatCounter.global_cpu_regex.match(row)
            if r:
                # logging.info("global cpu counters, len = %d" %
                #     (len(CPUStatCounter.global_cpu_fields),))
                g = r.groups()
                # logging.info(g)
                self.global_cpu_counters = \
                    [int(g[i])
                     for i in xrange(len(CPUStatCounter.global_cpu_fields) - 1)]
                continue

            r = CPUStatCounter.per_cpu_regex.match(row)
            if r:
                # logging.info("per cpu counters")
                g = r.groups()
                # logging.info(g)
                self.per_cpu_counters.append([int(g[i]) for i in xrange(len(
                    CPUStatCounter.per_cpu_fields))])
                continue

            r = CPUStatCounter.context_switches_regex.match(row)
            if r:
                # logging.info("context switches counter")
                g = r.groups()
                # logging.info(g)
                self.global_cpu_counters.append(int(g[0]))
                continue
        # logging.info(self.per_cpu_counters)
        # logging.info(self.global_cpu_counters)

    def diff(self, cpu_stat_counter):
        d = CPUStatCounter()
        d.global_cpu_counters = \
            [a - b for a, b in zip(self.global_cpu_counters,
                                   cpu_stat_counter.global_cpu_counters)]

        d.per_cpu_counters = \
            [[a_list[0]] + [a - b for a, b in zip(a_list[1:], b_list[1:])]
             for a_list, b_list in zip(self.per_cpu_counters,
                                       cpu_stat_counter.per_cpu_counters)]
        return d

    def __str__(self):
        return "{global_cpu_counters: %s, per_cpu_counters: %s}" % \
               (self.global_cpu_counters, self.per_cpu_counters)


class CPUUsage:
    cmd = "/bin/cat /proc/stat"
    INSTANCE = None

    @staticmethod
    def initialize(historesis=0):
        """
        historesis the rate of historesis
        initialize the CPU usage object if one is not running yet.

        return True if the CPU usage object was initialized successfully,
        False otherwise
        Note; returns false if the CPU usage object is already running)
        """
        if CPUUsage.INSTANCE is not None:
            return False
        CPUUsage.INSTANCE = CPUUsage(historesis=historesis)
        return True

    def __init__(self, hysteresis=0.0):
        # gets both user and kernel cpu ticks.
        self.current = CPUStatCounter(syscmd(CPUUsage.cmd))
        self.projected = {c[0]: 0 for c in self.current.per_cpu_counters}
        self.softirqs = {c[0]: 0 for c in self.current.per_cpu_counters}
        self.interrups_counters = IRQCounter(len(self.current.per_cpu_counters))

        self.uptime = UpTimeCounter()
        self.hysteresis = hysteresis

    def update(self):
        self.uptime.update()
        old = self.current
        self.current = CPUStatCounter(syscmd(CPUUsage.cmd))

        h = self.hysteresis
        t_diff = 100.0 * float(self.uptime.up_time_diff)
        logging.info(self.uptime.up_time_diff)
        for c in self.current.diff(old).per_cpu_counters:
            # logging.info(str(c))
            self.projected[c[0]] = self.projected[c[0]] * h + \
                (1.0 - h) * (1.0 - float(c[4]) / t_diff)
            self.softirqs[c[0]] = float(c[7]) / float(t_diff)

            cpu_usage_str = "%s: " % (c[0],)
            for i, f in enumerate(CPUStatCounter.per_cpu_fields[1:]):
                cpu_usage_str += "%s: %.2f " % (f, float(c[i+1])/ t_diff)
            logging.info(cpu_usage_str)

            # logging.info("raw: cpu %s: idle: %.2f softirqs: %.2f" %
            #        (c[0], c[4], c[7]))
            # logging.info("cpu %s: projected: %.2f softirqs: %.2f" %
            #        (c[0], self.projected[c[0]], self.softirqs[c[0]]))

        self.interrups_counters.update()

    def get_min_used_cpu(self, requested_cpus):
        if not requested_cpus:
            return None

        # return next(iter(requested_cpus))
        return min({k: v for k, v in self.projected.items()
                    if k in requested_cpus},
                   cmp=lambda x, y: x[1] - y[1])[0]

    def get_cpus_by_usage(self, requested_cpus):
        if not requested_cpus:
            return None

        sorted_cpus = sorted({k: v for k, v in self.projected.items()
                              if k in requested_cpus},
                             cmp=lambda x, y: x[1] - y[1])
        logging.info("CPUUsage.get_cpus_by_usage: requested_cpus: %s, "
                     "sorted_cpus: %s" % (requested_cpus, sorted_cpus))
        return sorted_cpus.keys()

    def get_empty_cpu(self, requested_cpus):
        if not requested_cpus:
            return None

        return sum(1 - v for k, v in self.projected.items()
                   if k in requested_cpus)

    def get_softirq_cpu(self, requested_cpus):
        # logging.info("requested_cpus: %s." % (str(requested_cpus), ))
        if not requested_cpus:
            return None

        # logging.info("softirqs:")
        # for k, v in self.softirqs.items():
        #     logging.info("%s: %d" % (k, v))

        return sum(v for k, v in self.softirqs.items()
                   if k in requested_cpus)

    def get_interrupts(self, requested_cpus):
        return sum(self.interrups_counters[k] for k in requested_cpus)

    def get_ticks(self):
        # in jiffies rather then seconds
        logging.info(self.uptime.up_time_diff)
        return self.uptime.up_time_diff * 100

