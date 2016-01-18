#!/usr/bin/python
import re
import sys
import os
import getopt


from cpus import CPU
from aux import syscmd, ls, msg, warn, print_stuff, print_selected_stuff, Timer
from vhost_light import VhostLight, ProcessCPUUsageCounterBase
from affinity_entity import parse_cpu_mask_from_pid, set_cpu_mask_to_pid


def usage(program_name):
    print('%s [OPTIONS]' % (program_name, ))
    print('-w, --workers - display worker data')
    print('-d, --devices - display device data')
    print('-q, --queues - display virtual queue data')
    print('-s, --short - short version')
    print('-l, --long - long version')
    print('default flags: -w, -s')
    sys.exit()

MOUNT_POINT = "/sys/class/vhost"


def get_cpus_per_sockets():
    # return 8
    return int(syscmd('lscpu | grep "Core(s) per socket" | rev | cut -c1'))


def vhost_write(elem, key, value):
    file_path = os.path.join(elem["path"], key)
    with open(file_path, "w") as f:
        f.write(str(value))


def vhost_read(elem, key):
    file_path = os.path.join(elem["path"], key)
    with open(file_path, "r") as f:
        return f.read()


def vhost_worker_set_cpu_mask(worker, cpu_mask):
    pid = vhost_read(worker, "pid")
    set_cpu_mask_to_pid(pid, cpu_mask)


def vhost_worker_get_cpu_mask(worker):
    pid = int(vhost_read(worker, "pid"))
    return parse_cpu_mask_from_pid(pid)


def get_cpu_usage(pid):
    path = "/proc/%s/stat" % (pid,)
    if not os.path.exists(path):
        warn("A process with that pid %d was not found." % (pid,))
        return 0

    with open(path, "r") as f:
        for line in f:
            res = line.split()
            return int(res[13]) + int(res[14])


class ProcessCPUUsageCounter(ProcessCPUUsageCounterBase):
    def __init__(self, pid):
        ProcessCPUUsageCounterBase.__init__(self, pid)
        # gets both user and kernel cpu ticks.
        self.path = "/proc/%s/stat" % (pid,)
        self.current = self._parse_output()

    def _parse_output(self):
        if not os.path.exists(self.path):
            warn("A process with that pid %d was not found. update "
                 "vm pids file and run again" % (self.pid,))
            return 0

        with open(self.path, "r") as f:
            for line in f:
                res = line.split()
                return int(res[13]) + int(res[14])

    def update(self):
        value = self._parse_output()
        self.delta = value - self.current
        self.current = value


class VhostCounter:
    def __init__(self, name, element_name=None):
        self.name = name
        self.element_name = element_name if element_name is not None else name

        self.total = "total_%s" % (self.name,)
        self.last_epoch = "%s_last_epoch" % (self.name,)

        self.delta = 0

    def initialize(self, vhost, initial_value=0):
        vhost[self.total] = initial_value

    def update(self, vhost, elements):
        total = sum(e[self.element_name] for e in elements)
        last_epoch = vhost[self.last_epoch] = vhost[self.total]
        vhost[self.total] = total

        self.delta = total - last_epoch
        return self.delta


class Vhost:
    workersGlobalPattern = re.compile('worker')

    workerPattern = re.compile('w\.[0-9]+')
    queuePattern = re.compile('vq\.[0-9]+\.[0-9]+')
    devicePattern = re.compile('d\.[0-9]+')

    INSTANCE = None

    @staticmethod
    def initialize(path=MOUNT_POINT):
        """
        initialize the CPU usage object if one is not running yet.
        :param path: vhost mount path

        :return True if the CPU usage object was initialized successfully,
        False otherwise
        Note; returns false if the CPU usage object is already running)
        """
        if Vhost.INSTANCE is not None:
            return False
        Vhost.INSTANCE = Vhost(path)
        return True

    """ A parser for vhost/status """
    def __init__(self, path=MOUNT_POINT):
        self.path = path
        self.vhost = {}
        self.workersGlobal = {}
        self.workers = {}
        self.devices = {}
        self.queues = {}

        self.cores_per_socket = get_cpus_per_sockets()
        self.cpus = CPU.parse_cpus()
        self.sockets = len(self.cpus) / self.cores_per_socket

        self.cycles = VhostCounter("cycles")
        self.work_cycles = VhostCounter("work_cycles", "total_work_cycles")
        self.softirq_interference = VhostCounter("softirq_interference",
                                                 "ksoftirqs")

        # self.per_worker_counters = {
        #     n: VhostCounter(n)
        #     for n in ["empty_polls", "empty_works", "loops",
        # "cpu_usage_counter"]
        # }
        self.per_worker_counters = {
            n: VhostCounter(n) for n in ["cpu_usage_counter"]
        }
        # self.per_queue_counters = {
        #     n: VhostCounter(n) for n in
        #     ["handled_bytes", "notif_bytes", "notif_cycles", "notif_limited",
        #      "notif_wait", "notif_works", "poll_cycles", "poll_bytes",
        #      "poll_empty", "poll_empty_cycles", "poll_limited",
        #      "poll_pending_cycles", "poll_wait"]  # , "sendmsg_calls"]
        # }
        self.per_queue_counters = {
            n: VhostCounter(n) for n in ["handled_bytes"]
        }

        self._initialize()

        self.vhost_light = VhostLight(self)

    @staticmethod
    def is_workers_global(key, value):
        return Vhost.workersGlobalPattern.match(key) and not value

    @staticmethod
    def is_worker(key):
        return Vhost.workerPattern.match(key)

    @staticmethod
    def is_device(key):
        return Vhost.devicePattern.match(key)

    @staticmethod
    def is_virtual_queue(key):
        return Vhost.queuePattern.match(key)

    @staticmethod
    def parse_value(key, value):
        value = value.strip()
        # msg("value: %s" % (value,))
        if key.endswith("_list"):
            if value:
                value = value.split("\t")
            else:
                value = []
        elif value.isdigit():
            value = int(value)

        # msg("end")
        return value

    @staticmethod
    def update_all_entries(dictionary):
        dir_path = dictionary["path"]
        # msg("dir_path: %s" % (dir_path,))
        if "status" in dictionary["keys"]:
            file_path = os.path.join(dir_path, "status")
            # msg("file_path: %s" % (file_path,))
            with open(file_path, "r") as f:
                for line in f:
                    key, value = line.split(":")
                    dictionary[key] = Vhost.parse_value(key, value)
            return

        for key in dictionary["keys"]:
            # msg("key: %s" % (key,))
            file_path = os.path.join(dir_path, key)
            # msg("file_path: %s" % (file_path,))
            with open(file_path, "r") as f:
                # msg("file opened successfully")
                value = f.read().strip()
            dictionary[key] = Vhost.parse_value(key, value)

    def update_all_entries_with_id(self, elem_id):
        directory = ""
        parent = None
        if Vhost.is_worker(elem_id):
            directory = "worker"
            parent = self.workers
        elif Vhost.is_device(elem_id):
            directory = "dev"
            parent = self.devices
        elif Vhost.is_virtual_queue(elem_id):
            directory = "vq"
            parent = self.queues
        dir_path = os.path.join(self.path, directory, elem_id)
        elem = parent[elem_id] = {
            "id": elem_id, "path": dir_path,
            "keys": ls(dir_path, show_dirs=False, show_files=True,
                       show_only_readable=True)}
        Vhost.update_all_entries(elem)

    def _initialize(self):
        # timer = Timer("Timer vhost _initialize")
        self.vhost["path"] = self.path
        self.vhost["keys"] = ls(self.path, show_dirs=False, show_files=True,
                                show_only_readable=True)
        Vhost.update_all_entries(self.vhost)
        # timer.checkpoint("vhost")

        self.workersGlobal["path"] = os.path.join(self.path, "worker")
        self.workersGlobal["keys"] = ls(self.workersGlobal["path"],
                                        show_dirs=False, show_files=True,
                                        show_only_readable=True)
        Vhost.update_all_entries(self.workersGlobal)
        # timer.checkpoint("workersGlobal")

        for w_id in ls(os.path.join(self.path, "worker")):
            w_id = w_id.strip()
            # msg("w_id: %s" % (w_id,))
            dir_path = os.path.join(self.path, "worker", w_id)
            w = self.workers[w_id] = {"id": w_id, "path": dir_path,
                                      "keys": ls(dir_path, show_dirs=False,
                                                 show_files=True,
                                                 show_only_readable=True)}
            Vhost.update_all_entries(w)
            w["cpu_usage_counter"] = get_cpu_usage(w["pid"])
            # w["cpu_usage_counter"] = ProcessCPUUsageCounter(w["pid"])
        # timer.checkpoint("worker")

        for d_id in ls(os.path.join(self.path, "dev")):
            d_id = d_id.strip()
            dir_path = os.path.join(self.path, "dev", d_id)
            dev = self.devices[d_id] = \
                {"id": d_id, "path": dir_path,
                 "keys": ls(dir_path, show_dirs=False, show_files=True,
                            show_only_readable=True)}
            Vhost.update_all_entries(dev)
        # timer.checkpoint("dev")

        for vq_id in ls(os.path.join(self.path, "vq")):
            vq_id = vq_id.strip()
            dir_path = os.path.join(self.path, "vq", vq_id)
            queue = self.queues[vq_id] = \
                {"id": vq_id, "path": dir_path,
                 "keys": ls(dir_path, show_dirs=False, show_files=True,
                            show_only_readable=True)}
            Vhost.update_all_entries(queue)
            queue["notif_works_last_epoch"] = queue["notif_works"]
        # timer.checkpoint("vq")

        self.vhost["cycles_last_epoch"] = self.vhost["cycles"]

        self.work_cycles.initialize(self.vhost, self.vhost["cycles"])
        self.cycles.initialize(self.vhost, self.vhost["cycles"])
        self.softirq_interference.initialize(self.vhost, self.vhost["cycles"])
        # timer.checkpoint("misc")

        for c in self.per_worker_counters.values():
            c.initialize(self.vhost)
        # timer.checkpoint("per_worker_counters")
        for c in self.per_queue_counters.values():
            c.initialize(self.vhost)
        # timer.checkpoint("per_queue_counters")
        # timer.checkpoint("done")

    def update(self, light_update=True, update_epoch=False, rescan_files=False):
        # timer = Timer("Timer vhost update")
        self.vhost_light.update()
        # timer.checkpoint("vhost_light")
        if light_update:
            # timer.done()
            return
        if rescan_files:
            self._initialize()
            # timer.checkpoint("_initialize")
        if update_epoch:
            vhost_write(self.vhost, "epoch", "1")
            # timer.checkpoint("update_epoch")

        Vhost.update_all_entries(self.vhost)
        cycles_this_epoch = self.vhost["cycles"] - \
            self.vhost["cycles_last_epoch"]
        self.vhost["cycles_last_epoch"] = self.vhost["cycles"]
        self.vhost["cycles_this_epoch"] = cycles_this_epoch
        # timer.checkpoint("vhost")
        Vhost.update_all_entries(self.workersGlobal)
        # timer.checkpoint("workersGlobal")

        for w in self.workers.values():
            Vhost.update_all_entries(w)
            w["cpu_usage_counter"] = get_cpu_usage(w["pid"])
            # w["cpu_usage_counter"].update()
        # timer.checkpoint("workers")

        for dev in self.devices.values():
            Vhost.update_all_entries(dev)
        # timer.checkpoint("devices")

        for vq in self.queues.values():
            Vhost.update_all_entries(vq)
            notif_works_this_epoch = vq["notif_works"] - \
                vq["notif_works_last_epoch"]
            vq["notif_works_last_epoch"] = vq["notif_works"]
            vq["notif_works_this_epoch"] = notif_works_this_epoch
        # timer.checkpoint("queues")

        self.cycles.update(self.vhost, [self.vhost])
        self.work_cycles.update(self.vhost, self.workers.values())
        self.softirq_interference.update(self.vhost, self.workers.values())
        # timer.checkpoint("misc")

        for c in self.per_worker_counters.values():
            c.update(self.vhost, self.workers.values())
        # timer.checkpoint("per_worker_counters")
        for c in self.per_queue_counters.values():
            c.update(self.vhost, self.queues.values())
        # timer.checkpoint("per_queue_counters")
        self.vhost_light.update(rescan=True)
        # timer.done()


def main(argv):
    workers = True
    devices = False
    queues = False

    short = True

    opts = None
    try:
        opts, args = getopt.getopt(argv[1:], "wdqvslh",
                                   ["workers", "devices", "queues",
                                    "short", "long", "help"])
    except getopt.GetoptError:
        msg("Error: unknown option")
        usage(argv[0])

    for opt, _ in opts:
        if opt in ("-h", "--help"):
            usage(argv[0])
        elif opt in ("-w", "--worker"):
            workers = True
        elif opt in ("-d", "--devices"):
            devices = True
        elif opt in ("-q", "--queues"):
            queues = True
        elif opt in ("-s", "--short"):
            short = True
        elif opt in ("-l", "--long"):
            short = False

    vhost = Vhost()
    vhost.update(False)

    if not short:
        msg("\x1b[35mvhost:\x1b[39m %s" % (vhost.vhost, ))

        msg("\x1b[35mworkers global:\x1b[39m %s" % (vhost.workersGlobal, ))

    if short:
        if workers:
            print_selected_stuff("worker", vhost.workers,
                                 ("id", "pid", "cpu", "dev_list"))
        if devices:
            print_selected_stuff("device", vhost.devices,
                                 ("id", "worker", "owner"))
        if queues:
            print_selected_stuff("queue", vhost.queues, ("id", "poll"))
    else:
        if workers:
            print_stuff("worker", vhost.workers)
        if devices:
            print_stuff("device", vhost.devices)
        if queues:
            print_stuff("queue", vhost.queues)


if __name__ == '__main__':
    main(sys.argv[0])
