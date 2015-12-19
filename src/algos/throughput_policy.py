#!/usr/bin/python
import logging
import time

from utils.vhost import Vhost
from utils.cpuusage import CPUUsage
from utils.aux import parse_user_list, Timer


class ThroughputRegretPolicy:
    def __init__(self, policy_info):
        self.interval = float(policy_info["interval"])

    def initialize(self):
        pass

    def should_regret(self):
        logging.info("should regret")
        timer = Timer("Timer ThroughputRegretPolicy")
        vhost_inst = Vhost.INSTANCE
        # vhost = Vhost.INSTANCE.vhost
        handled_bytes = vhost_inst.per_queue_counters["notif_bytes"].delta + \
            vhost_inst.per_queue_counters["poll_bytes"].delta
        cycles = vhost_inst.cycles.delta
        ratio_before = handled_bytes / float(cycles)
        logging.info("cycles:       %d", cycles)
        logging.info("handled_bytes:%d", handled_bytes)
        logging.info("ratio_before: %.2f", ratio_before)
        logging.info("throughput:   %.2fGbps", ratio_before * 2.2 * 8)

        timer.checkpoint("before sleep")
        time.sleep(self.interval)
        timer.checkpoint("after sleep")
        vhost_inst.update()
        timer.checkpoint("vhost_inst.update()")

        ratio_after = 0
        # for _ in xrange(5):
        for _ in xrange(1):
            time.sleep(self.interval)
            vhost_inst.update()

            handled_bytes = \
                vhost_inst.per_queue_counters["notif_bytes"].delta + \
                vhost_inst.per_queue_counters["poll_bytes"].delta
            cycles = vhost_inst.cycles.delta
            ratio_after = handled_bytes / float(cycles)

            logging.info("cycles:       %d", cycles)
            logging.info("handled_bytes:%d", handled_bytes)
            logging.info("ratio_after:  %.2f", ratio_after)
            logging.info("throughput:   %.2fGbps", ratio_after * 2.2 * 8)

        timer.done()
        return ratio_before > ratio_after


class AdditionPolicy:
    def __init__(self, policy_info):
        # The ratio of total empty cycles to cycles this epoch
        self.add_ratio = float(policy_info["add_ratio"])  # 0.05

        # The ratio of total empty cycles to cycles this epoch
        self.can_remove_ratio = float(policy_info["can_remove_ratio"])  # 1.05

    def initialize(self):
        pass

    def _should_update_core_number(self, ratio):
        add = (self.add_ratio > ratio)
        can_remove = (self.can_remove_ratio < ratio)
        return add, can_remove


class IOWorkerThroughputPolicy(AdditionPolicy):
    def __init__(self, policy_info):
        AdditionPolicy.__init__(self, policy_info)
        # The ratio of total empty cycles to cycles this epoch
        self.stop_shared_ratio = float(policy_info["stop_shared_ratio"])  # 0.3
        # The ratio of total empty cycles to cycles this epoch
        self.start_shared_ratio = float(policy_info["start_shared_ratio"])

        self.average_bytes_per_packet = None
        self.ratio = None
        self.overall_io_ratio = None
        self.io_cores = None
        self.shared_workers = False

        self.effective_io_ratio = None

    def initialize(self):
        pass

    def calculate_load(self, shared_workers):
        timer = Timer("Timer IOWorkerThroughputPolicy.calculate_load")
        vhost_inst = Vhost.INSTANCE
        workers = Vhost.INSTANCE.workers

        cycles_this_epoch = vhost_inst.cycles.delta

        self.io_cores = len(workers) if shared_workers else 1
        self.shared_workers = shared_workers

        total_cycles_this_epoch = cycles_this_epoch * self.io_cores
        empty_cycles = total_cycles_this_epoch - vhost_inst.work_cycles.delta

        logging.info("\x1b[37mcycles.delta      %d.\x1b[39m" %
                     (vhost_inst.cycles.delta,))
        logging.info("\x1b[37mwork_cycles       %d.\x1b[39m" %
                     (vhost_inst.work_cycles.delta,))
        logging.info("\x1b[37mio_cores          %d.\x1b[39m" %
                     (self.io_cores,))
        logging.info("\x1b[37mcycles_this_epoch %d.\x1b[39m" %
                     (cycles_this_epoch,))
        logging.info("\x1b[37mempty_cycles      %d.\x1b[39m" %
                     (empty_cycles,))

        handled_bytes = vhost_inst.per_queue_counters["notif_bytes"].delta + \
            vhost_inst.per_queue_counters["poll_bytes"].delta
        cycles = vhost_inst.cycles.delta
        ratio_before = handled_bytes / float(cycles)
        logging.info("cycles:       %d", cycles)
        logging.info("handled_bytes:%d", handled_bytes)
        logging.info("ratio_before: %.2f", ratio_before)
        logging.info("throughput:   %.2fGbps", ratio_before * 2.2 * 8)

        softirq_cpu_ratio = 0
        if shared_workers:
            io_cores_cpus = [w["cpu"] for w in workers.values()]
            logging.info("\x1b[37mio_cores_cpus %s.\x1b[39m" %
                         (str(io_cores_cpus),))
            softirq_cpu = CPUUsage.INSTANCE.get_softirq_cpu(io_cores_cpus)
            logging.info("\x1b[37msoftirq_cpu %.2f.\x1b[39m" % (softirq_cpu,))
            total_interrupts = CPUUsage.INSTANCE.get_interrupts(io_cores_cpus)
            logging.info("\x1b[37mtotal_interrupts %d.\x1b[39m" %
                         (total_interrupts,))
            logging.info("\x1b[37msoftirq_interference_this_epoch %d.\x1b[39m" %
                         (vhost_inst.softirq_interference.delta,))
            # ksoftirq thread is scheduled on our iocores, and worse yet it
            # preempts the iocores thread. We measure the iocores activity and
            # CPU usage using rdtsc assuming it is never preempts. softirq_cpu_
            # ratio is the CPU usage of the softirq thread that didn't occur
            # during a preemption of the thread in the iocore. 1 means a full
            # core was used.
            if float(total_interrupts) > 0:
                softirq_cpu_ratio = \
                    float(softirq_cpu) - float(softirq_cpu) * \
                    float(vhost_inst.softirq_interference.delta) / \
                    float(total_interrupts)
            logging.info("\x1b[37msoftirq cpu %.2f.\x1b[39m" %
                         (softirq_cpu_ratio,))

        # the idle cycles ratio in the iocores not including the ksoftirq
        # activity (which is a useful work). 1 means a full core was wasted.
        self.ratio = float(empty_cycles) / float(cycles_this_epoch) - \
            softirq_cpu_ratio
        # this the ratio of cycles used to handle virtual IO.
        self.effective_io_ratio = \
            float(vhost_inst.work_cycles.delta) / \
            float(vhost_inst.cycles.delta) + \
            softirq_cpu_ratio

        logging.info("\x1b[37mempty ratio is %.2f.\x1b[39m" % (self.ratio,))
        logging.info("\x1b[37meffective io ratio is %.2f.\x1b[39m" %
                     (self.effective_io_ratio,))

        logging.info("----------------")
        for c in sorted(vhost_inst.per_worker_counters.values(),
                        key=lambda x: x.name):
            logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))
        self.overall_io_ratio = \
            vhost_inst.per_worker_counters["cpu_usage_counter"].delta / \
            float(CPUUsage.INSTANCE.get_ticks())
        if self.overall_io_ratio == 0:
            self.overall_io_ratio = 0.0000001
        logging.info("\x1b[37moverall workers cpu %.2f.\x1b[39m" %
                     (self.overall_io_ratio,))
        logging.info("----------------")
        for c in sorted(vhost_inst.per_queue_counters.values(),
                        key=lambda x: x.name):
            logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))
        logging.info("----------------")
        if int(vhost_inst.per_worker_counters["loops"].delta) != 0:
            empty_polls = \
                float(vhost_inst.per_worker_counters["empty_polls"].delta)
            empty_works = \
                float(vhost_inst.per_worker_counters["empty_works"].delta)
            loops = float(vhost_inst.per_worker_counters["loops"].delta)
            logging.info("empty_polls ratio: %.2f." % (empty_polls / loops,))
            logging.info("empty_works ratio: %.2f." % (empty_works / loops,))
        else:
            logging.info("empty_polls ratio: 0.0.")
            logging.info("empty_works ratio: 0.0.")

        self.average_bytes_per_packet = 0
        # if vhost_inst.per_queue_counters["sendmsg_calls"].delta > 0:
        #     self.average_bytes_per_packet = \
        #         float(vhost_inst.per_queue_counters["notif_bytes"].delta +
        #               vhost_inst.per_queue_counters["poll_cycles"].delta) / \
        #         vhost_inst.per_queue_counters["sendmsg_calls"].delta

        logging.info("efficient io ratio: %.2f" %
                     (self.effective_io_ratio / self.overall_io_ratio,))
        timer.done()

    def should_update_core_number(self):
        vhost_inst = Vhost.INSTANCE
        add, can_remove = self._should_update_core_number(self.ratio)
        if add:
            logging.info("\x1b[37mshould add IO workers, empty cycles "
                         "ratio is %.2f.\x1b[39m" % (self.ratio,))

            cycles_this_epoch = vhost_inst.cycles.delta
            logging.info("\x1b[37mcycles_this_epoch: %d.\x1b[39m" %
                         (cycles_this_epoch,))

            total_cycles_this_epoch = cycles_this_epoch * self.io_cores
            empty_cycles = \
                total_cycles_this_epoch - vhost_inst.work_cycles.delta
            logging.info("\x1b[37mempty_cycles: %d.\x1b[39m" %
                         (empty_cycles,))
            logging.info("\x1b[37mcycles_this_epoch: %d.\x1b[39m" %
                         (cycles_this_epoch,))
        return add, can_remove

    def should_start_shared_worker(self):
        if self.shared_workers:
            return False, 0
        full_ratio = self.overall_io_ratio  # 1 - self.ratio
        if self.start_shared_ratio >= full_ratio:
            return False, 0
        logging.info("\x1b[mstart_shared_ratio: %0.2f.\x1b[39m" %
                     (self.start_shared_ratio,))

        logging.info("\x1b[mfull ratio: %0.2f.\x1b[39m" % (full_ratio,))
        # suggested number of io cores, we are always rounding up
        return True, int(self.effective_io_ratio + .9)

    def should_stop_shared_worker(self):
        if not self.shared_workers or self.io_cores > 1:
            return False
        full_ratio = self.overall_io_ratio  # 1 - self.ratio
        if self.stop_shared_ratio <= full_ratio:
            return False

        logging.info("\x1b[37mshould disable shared workers.\x1b[39m")
        logging.info("\x1b[37mshared_workers: %s.\x1b[39m" %
                     (self.shared_workers,))
        logging.info("\x1b[37mio_cores: %d.\x1b[39m" % (self.io_cores,))
        logging.info("\x1b[37mstop_shared_ratio: %.3f.\x1b[39m" %
                     (self.stop_shared_ratio,))
        logging.info("\x1b[37mfull_ratio: %.3f.\x1b[39m" % (full_ratio,))
        return True


class VMCoreAdditionPolicy(AdditionPolicy):
    @staticmethod
    def get_initial_cpus(vms_info):
        initial_cpus = set()
        for vm in vms_info:
            initial_cpus.update(set(parse_user_list(vm["cpu"])))
        return list(initial_cpus)

    def __init__(self, vms_info, policy_info):
        AdditionPolicy.__init__(self, policy_info)
        self.cpus = VMCoreAdditionPolicy.get_initial_cpus(vms_info)

    def add(self, cpu_id):
        self.cpus.append(int(cpu_id))

    def remove(self, cpu_ids):
        for cpu_id in cpu_ids:
            self.cpus.remove(int(cpu_id))

    def should_update_core_number(self):
        ratio = CPUUsage.INSTANCE.get_empty_cpu(self.cpus)
        add, can_remove = self._should_update_core_number(ratio)
        logging.info("\x1b[37mcan%s remove a VM core, empty cycles ratio is "
                     "%.2f.\x1b[39m" % ("" if can_remove else "not", ratio))
        logging.info("\x1b[37mcan_remove_ratio: %.2f.\x1b[39m" %
                     (self.can_remove_ratio,))
        logging.info("\x1b[37mcan remove: %s.\x1b[39m" %
                     (self.can_remove_ratio < ratio,))

        logging.info("\x1b[37mshould%s add VM cores, empty cycles ratio is "
                     "%.2f.\x1b[39m" % ("" if add else " not", ratio))
        logging.info("\x1b[37madd_ratio: %.2f.\x1b[39m" % (self.add_ratio,))
        logging.info("\x1b[37VM cores are %s.\x1b[39m" % (self.cpus, ))
        return add, can_remove

# class ThroughputPolicyOld():
#     def __init__(self, policy_info):
#         # The threshold where we stop handling multiple devices in a single
#         # worker.
#         self.stop_shared_ratio = float(policy_info["stop_shared_ratio"]) # 0.3
#         # The threshold where we stop handling multiple devices in a single
#         # worker. 0.45
#         self.start_shared_ratio = float(policy_info["start_shared_ratio"])
#
#         # the ratio between the total work cycles available and the amount
#         # spent performing work.
#         self.add_ratio = float(policy_info["add_ratio"])  # 0.9
#         # the ratio between total empty cycles in the vhost workers, and the
#         # amount of cycles available to one worker.
#         self.remove_ratio = float(policy_info["remove_ratio"])  # 1.5
#
#         self.cooling_off_period = 30  # 6
#         self.epochs_last_action = 0
#
#     @staticmethod
#     def initialize():
#         Vhost.INSTANCE.vhost["total_work_cycles"] = \
#             Vhost.INSTANCE.vhost["cycles"]
#
#     @staticmethod
#     def calculate_load(vhost, devices, queues):
#         total_work_cycles = 0
#         for dev in devices.values():
#             dev["total_work_cycles"] = 0
#             for vq in [queues[vq_id] for vq_id in dev["vq_list"]]:
#                 dev["total_work_cycles"] += vq["poll_cycles"] + \
#                     vq["notif_cycles"]
#             total_work_cycles += dev["total_work_cycles"]
#         vhost["total_work_cycles_last_epoch"] = vhost["total_work_cycles"]
#         vhost["total_work_cycles"] = total_work_cycles
#
#     def update_io_core_number(self, shared_workers):
#         vhost = Vhost.INSTANCE
#         cycles_this_epoch = vhost.vhost["cycles_this_epoch"]
#         ThroughputPolicyOld.calculate_load(vhost.vhost, vhost.devices,
#                                            vhost.queues)
#
#         self.epochs_last_action += 1
#         if self.epochs_last_action <= self.cooling_off_period:
#             return "stay"
#
#         io_cores = len(vhost.workers) if shared_workers else 0
#         total_work_cycles_delta = vhost.vhost["total_work_cycles"] - \
#             vhost.vhost["total_work_cycles_last_epoch"]
#
#         total_cycles_this_epoch = cycles_this_epoch * max(io_cores, 1)
#         empty_cycles = total_cycles_this_epoch - total_work_cycles_delta
#
#         if total_cycles_this_epoch * self.add_ratio < \
#                 total_work_cycles_delta:
#             logging.info("\x1b[33mthroughtput: should add I/O core\x1b[39m")
#             logging.info("io_cores: %d" %
#                          (io_cores, ))
#             logging.info("cycles_this_epoch: %d" %
#                          (cycles_this_epoch, ))
#             logging.info("total_cycles_this_epoch: %d" %
#                          (total_cycles_this_epoch, ))
#             logging.info("total_work_cycles_delta: %d" %
#                          (total_work_cycles_delta, ))
#             logging.info("ratio: %f" %
#                          (total_work_cycles_delta /
#                           float(total_cycles_this_epoch), ))
#             self.epochs_last_action = 0
#             return "add"
#
#         if (io_cores == 0) and \
#                 (total_cycles_this_epoch * self.start_shared_ratio <
#                     total_work_cycles_delta):
#             logging.info("\x1b[33mthroughtput: start shared workers\x1b[39m")
#             logging.info("total_cycles_this_epoch: %d" %
#                          (total_cycles_this_epoch, ))
#             logging.info("total_work_cycles_delta: %d" %
#                          (total_work_cycles_delta, ))
#             logging.info("ratio: %f" %
#                          (total_work_cycles_delta /
#                           float(total_cycles_this_epoch), ))
#             self.epochs_last_action = 0
#             return "add"
#
#         if (cycles_this_epoch * self.remove_ratio < empty_cycles) and \
#                 (io_cores > 1):
#             logging.info("\x1b[33mthroughtput: should remove an I/O core"
#                          "\x1b[39m")
#             logging.info("empty_cycles: %d, cycles_this_epoch: %d" %
#                          (empty_cycles, cycles_this_epoch))
#             logging.info("ratio: %f" %
#                          (empty_cycles / float(cycles_this_epoch), ))
#             self.epochs_last_action = 0
#             return "remove"
#
#         if (cycles_this_epoch * self.stop_shared_ratio < empty_cycles) and \
#                 (io_cores == 1):
#             logging.info("\x1b[33mthroughtput: stop shared workers\x1b[39m")
#             logging.info("empty_cycles: %d, cycles_this_epoch: %d" %
#                          (empty_cycles, cycles_this_epoch))
#             logging.info("ratio: %f" %
#                          (empty_cycles / float(cycles_this_epoch), ))
#             self.epochs_last_action = 0
#             return "remove"
#
#         return "stay"
