import logging

from utils.vm import VM
from utils.vhost import ProcessCPUUsageCounter

class VMManager:
    def __init__(self, vms_info, backing_devices, vm_policy,
                 vm_core_addition_policy, vm_balance_policy):
        self.vms = [VM(vm_info, backing_devices) for vm_info in vms_info]
        # logging.info(self.vms)
        self.backing_devices = backing_devices

        self.vm_policy = vm_policy
        self.vm_core_addition_policy = vm_core_addition_policy
        self.vm_balance_policy = vm_balance_policy

        self.vms_cpuusage = [ProcessCPUUsageCounter(vm.pid) for vm in self.vms]

    def update(self):
        for idx, c in enumerate(self.vms_cpuusage):
            c.update()
            logging.info("vm %s: %s" % (self.vms[idx].idx, str(c)))

    def should_update_core_number(self):
        return self.vm_core_addition_policy.should_update_core_number()

    def remove_core(self):
        logging.info("\x1b[33mVM Manager: remove an VM core\x1b[39m")
        cpu_id = self.vm_policy.remove()
        self.vm_core_addition_policy.remove(cpu_id)
        logging.info("cpu_id = %s" % (str(cpu_id),))

        self.vm_balance_policy.balance_before_removal(self.vms, cpu_id)
        return cpu_id

    def add_core(self, cpu_id):
        logging.info("\x1b[33mVM Manager: add a VM core on core %s.\x1b["
                     "39m" % (cpu_id, ))
        self.vm_policy.add(cpu_id)
        self.vm_core_addition_policy.add(cpu_id)
        self.vm_balance_policy.balance_after_addition(self.vms, cpu_id)

    def disable_shared_workers(self):
        logging.info("\x1b[33mVM Manager: going to no IO core state.\x1b[39m")
        for bd in self.backing_devices.values():
            bd.zero_cpu_mask()

        for vm in self.vms:
            vm.disable_shared_workers()

        for bd in self.backing_devices.values():
            bd.apply_cpu_mask()

    def __str__(self):
        return "VMs: %s" % (self.vms, )

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())
