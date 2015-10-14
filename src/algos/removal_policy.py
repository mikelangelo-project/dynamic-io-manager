import logging

from utils.aux import parse_user_list
from utils.cpuusage import CPUUsage
from utils.vhost import Vhost

__author__ = 'eyalmo'


class PreconfiguredAddPolicy:
    @staticmethod
    def create_vm_policy(vms_info):
        initial_cpus = set()
        for vm in vms_info:
            # msg("vm: %s cpu:%s parsed: %s set: %s" %
            #     (vm["id"], vm["cpu"], parse_user_list(vm["cpu"]),
            #      set(parse_user_list(vm["cpu"]))))
            initial_cpus.update(set(parse_user_list(vm["cpu"])))
        # msg("initial_cpus: %s" % (initial_cpus,))
        return LastAddedPolicy(initial_cpus)

    @staticmethod
    def create_io_cores_policy(workers_info):
        initial_cpus = list(set([int(w["cpu"]) for w in workers_info]))
        return LastAddedPolicy(initial_cpus)

    def __init__(self, initial_cpus):
        self.cpus = list(initial_cpus)

    def add(self, cpu_id):
        self.cpus.append(int(cpu_id))

    def remove(self):
        return self.cpus.pop()


class LastAddedPolicy:
    @staticmethod
    def create_vm_policy(vms_info):
        initial_cpus = set()
        for vm in vms_info:
            # msg("vm: %s cpu:%s parsed: %s set: %s" %
            #     (vm["id"], vm["cpu"], parse_user_list(vm["cpu"]),
            #      set(parse_user_list(vm["cpu"]))))
            initial_cpus.update(set(parse_user_list(vm["cpu"])))
        # msg("initial_cpus: %s" % (initial_cpus,))
        initial_cpus = sorted(initial_cpus, cmp=lambda x, y: x < y)
        logging.info("vm initial cpus: %s" % (initial_cpus,))
        return LastAddedPolicy(initial_cpus)

    @staticmethod
    def create_io_cores_policy(workers_info):
        initial_cpus = list(set([int(w["cpu"]) for w in workers_info]))
        initial_cpus = sorted(initial_cpus, cmp=lambda x, y: x > y)
        logging.info("io cores initial cpus: %s" % (initial_cpus,))
        return LastAddedPolicy(initial_cpus)

    def __init__(self, initial_cpus):
        self.cpus = list(initial_cpus)

    def add(self, cpu_id):
        self.cpus.append(int(cpu_id))

    def remove(self):
        return self.cpus.pop()


class MinCPUUsagePolicy:
    def __init__(self, initial_cpus=()):
        self.cpus = set([int(cpu) for cpu in initial_cpus])

    def add(self, cpu_id):
        self.cpus.add(int(cpu_id))

    def remove(self):
        cpu_id = CPUUsage.INSTANCE.get_min_used_cpu(self.cpus)
        self.cpus.remove(cpu_id)
        return cpu_id


class MinElementsServedPolicy:
    def __init__(self):
        self.cpus_ration = {}

    def update_ratio(self, elements_to_cpus):
        self.cpus_ration = {}
        for _, cpus in elements_to_cpus.items():
            for cpu in cpus:
                if cpu in self.cpus_ration:
                    self.cpus_ration[cpu] += 1/len(cpus)
                else:
                    self.cpus_ration[cpu] = 1/len(cpus)

    def add(self, cpu_id):
        pass

    def remove(self):
        return min(self.cpus_ration, key=lambda x: x[1])


class MinDevicesServedPolicy(MinElementsServedPolicy):
    def __init__(self, io_cores):
        MinElementsServedPolicy.__init__(self)
        self.io_cores = io_cores

    def remove(self):
        vhost = Vhost.INSTANCE
        # mapping devices to io_cores
        devices_to_cpus = {dev_id: vhost.workers[dev["worker"]]["cpu"]
                           for dev_id, dev in vhost.devices.items()}
        self.update_ratio(devices_to_cpus)
        return MinElementsServedPolicy.remove(self)
