from utils.affinity_entity import Thread, \
    parse_cpu_mask_from_cpu_list
from utils.vhost import Vhost, vhost_read

__author__ = 'eyalmo'


class IOWorker(Thread):
    def __init__(self, worker_info):
        self.id = worker_info["id"]
        self.cpu = int(worker_info["cpu"])

        workers = Vhost.INSTANCE.workers
        self.pid = int(vhost_read(workers[self.id], "pid"))
        # only works dif there is only one cpu and it is an integer
        cpu_mask = 1 << self.cpu

        Thread.__init__(self, self.pid, 0, cpu_mask)

    def __str__(self):
        return "id: %s, cpus: %s" % (self.id, self.cpu)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
