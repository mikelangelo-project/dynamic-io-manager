import logging
import pprint
from utils.aux import parse_user_list, Timer

__author__ = 'eyalmo'


class VmsPreConfiguredBalancePolicy:
    def __init__(self, balancer_info, initial_cpus):
        self.vms_configurations = {
            conf["id"]: {
                vm["id"]: list(parse_user_list(vm["cpu"]))
                for vm in conf["vms"]
            }
            for conf in balancer_info["configurations"]
        }
        # logging.info("\x1b[37mvms_configurations:\x1b[39m \n%s" %
        #              (pprint.pformat(self.vms_configurations, indent=2,
        #                              width=80, depth=4),))
        self.cpu_configuration = {
            c: list(set([cpu for cpus in vms.values() for cpu in cpus]))
            for c, vms in self.vms_configurations.items()
        }
        # logging.info("\x1b[37mcpu_configuration:\x1b[39m \n%s" %
        #              (pprint.pformat(self.cpu_configuration, indent=2,
        #                              width=80, depth=4),))
        self.cpus = list(initial_cpus)
        # logging.info("\x1b[37mcpus:\x1b[39m \n%s" %
        #              (pprint.pformat(self.cpus, indent=2, width=80,
        #                              depth=4),))

        self.configuration_mapping = \
            {int(conf["cores"]): conf["id"]
             for conf in balancer_info["configurations"]}
        # logging.info("\x1b[37mconfiguration_mapping:\x1b[39m \n%s" %
        #              (pprint.pformat(self.configuration_mapping, indent=2,
        #                              width=80, depth=4),))

    def _balance(self, vms):
        conf_id = self.configuration_mapping[len(self.cpus)]
        self.balance_by_configuration(conf_id, vms)

    def balance_by_configuration(self, conf_id, vms):
        # timer = Timer("Timer VmsPreConfiguredBalancePolicy")
        # logging.info("\x1b[37mcpus:\x1b[39m \n%s" %
        #              (pprint.pformat(self.cpus, indent=2, width=80,
        #                              depth=4),))
        vms_conf = self.vms_configurations[conf_id]
        cpus_conf = self.cpu_configuration[conf_id]
        cpu_mapping = {cpu_conf: cpu
                       for cpu_conf, cpu in zip(cpus_conf, self.cpus)}
        # logging.info("\x1b[37mcpu_mapping:\x1b[39m \n%s" %
        #              (pprint.pformat(cpu_mapping, indent=2, width=80,
        #                              depth=4),))

        # moving vms to the correct cpu cores
        # logging.info("\x1b[37mmoving vms to the correct cpu cores\x1b[39m")
        for vm in vms:
            # timer.checkpoint("vm %s" % (vm.idx,))
            # new_cpu_sequence = [cpu_mapping[c] for c in vms_conf[vm.idx]]
            # logging.info("\x1b[37mvm %s: %s\x1b[39m" % (vm.idx,
            #                                             new_cpu_sequence))
            cpu_mask = 0
            for c in vms_conf[vm.idx]:
                cpu_mask += (1 << cpu_mapping[c])
            if cpu_mask == vm.cpu_mask:
                continue
            # timer.checkpoint("vm %s before set_cpu_mask" % (vm.idx,))
            vm.set_cpu_mask(cpu_mask)
            # timer.checkpoint("vm %s after set_cpu_mask" % (vm.idx,))
        # timer.done()

    def balance_after_addition(self, vms, new_cpu_id):
        """
        Re-balance the system after adding a new cpu to VMs
        :param vms: The vms in the system
        :param new_cpu_id: The newly added cpu id
        """
        # logging.info("\x1b[37mbalance_after_addition:\x1b[39m new_cpu_id %s" %
        #              (new_cpu_id,))
        self.cpus.append(new_cpu_id)
        self._balance(vms)

    def balance_before_removal(self, vms, cpu_ids):
        """
        Re-balance the system after removing cpu cores from VMs
        :param vms: The vms in the system
        :param cpu_ids: The cpu ids for removal
        """
        # logging.info("\x1b[mbalance_before_removal:\x1b[39m cpu_ids %s" %
        #              (cpu_ids,))
        for cpu_id in cpu_ids:
            self.cpus.remove(cpu_id)
        self._balance(vms)

    @staticmethod
    def balance():
        pass


class VmsRunEverywhereBalancePolicy:
    def __init__(self):
        pass

    @staticmethod
    def balance_after_addition(vms, new_cpu_id):
        """
        Re-balance the system after adding a new cpu to VMs
        :param vms: The vms in the system
        :param new_cpu_id: The newly added cpu id
        """
        for vm in vms:
            vm.add_core(new_cpu_id)

    @staticmethod
    def balance_before_removal(vms, cpu_ids):
        """
        Re-balance the system after removing cpu cores from VMs
        :param vms: The vms in the system
        :param cpu_ids: The worker thread id for removal
        """
        for cpu_id in cpu_ids:
            for vm in vms:
                vm.remove_core(cpu_id)

    @staticmethod
    def balance():
        pass
