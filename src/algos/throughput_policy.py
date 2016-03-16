#!/usr/bin/python
import logging
import time

from utils.vhost import Vhost
from utils.cpuusage import CPUUsage
from utils.aux import parse_user_list, Timer


class ThroughputRegretPolicy:
    def __init__(self, policy_info, backing_device_manager):
        self.backing_device_manager = backing_device_manager
        self.interval = float(policy_info["interval"])
        self.regret_penalty_factor = 3
        self.initial_regret_penalty = 100
        self.epoch = 0

        self.failed_moves_history = {}

        self.last_good_action = 0

        self.requested_actions = {}
        self.cooling_off_period = 10

        self.current_ratio = 0.0
        self.current_cycles = 0
        self.current_handled_bytes = 0

        self.history_length = 5
        self.history = []

    def initialize(self):
        pass

    def update(self):
        self.epoch += 1
        self.current_ratio, self.current_handled_bytes, self.current_cycles = \
            ThroughputRegretPolicy._calc_cycles_to_bytes_ratio()

        if len(self.history) == self.history_length:
            self.history = self.history[1:self.history_length]
        self.history.append((self.epoch, self.current_ratio,
                             self.current_handled_bytes, self.current_cycles))

        self.requested_actions = \
            {move: (epochs, False)
             for move, (epochs, requested_this_epoch) in
             self.requested_actions.items() if requested_this_epoch}

    def can_do_move(self, move):
        # logging.info("can_do_move: %s", move)
        if move not in self.requested_actions:
            self.requested_actions[move] = (1, True)
            return False

        epochs, requested_this_epoch = self.requested_actions[move]
        self.requested_actions[move] = (epochs + 1, True)
        if epochs < self.cooling_off_period:
            return False

        if move not in self.failed_moves_history:
            # logging.info("can do move")
            return True

        regret_penalty = \
            self.failed_moves_history[move]["regret_penalty"]
        last_failed_move_epoch = \
            self.failed_moves_history[move]["last_failed_move_epoch"]

        return self.epoch > last_failed_move_epoch + regret_penalty

    @staticmethod
    def _calc_cycles_to_bytes_ratio():
        vhost_inst = Vhost.INSTANCE.vhost_light  # Vhost.INSTANCE
        handled_bytes = vhost_inst.per_queue_counters["notif_bytes"].delta + \
            vhost_inst.per_queue_counters["poll_bytes"].delta
        cycles = vhost_inst.cycles.delta
        ratio = handled_bytes / float(cycles)
        return ratio, handled_bytes, cycles

    def is_move_good(self, move):
        vhost_inst = Vhost.INSTANCE.vhost_light  # Vhost.INSTANCE
        logging.info("is_move_good %s", move)

        for rec in self.history:
            logging.info("")
            logging.info("epoch:        %d", rec[0])
            logging.info("cycles:       %d", rec[3])
            logging.info("handled_bytes:%d", rec[2])
            logging.info("ratio_before: %.2f", rec[1])
            logging.info("throughput:   %.2fGbps", rec[1] * 2.2 * 8)
        ratio_before = sum(rec[1] for rec in self.history) / len(self.history)

        ratio_after_sum = 0
        ratio_after = 0
        iterations = 20
        grace_period = 5
        for i in xrange(iterations):
            time.sleep(self.interval)
            # refresh all counters
            CPUUsage.INSTANCE.update()
            vhost_inst.update()
            self.backing_device_manager.update()

            ratio, handled_bytes, cycles = \
                ThroughputRegretPolicy._calc_cycles_to_bytes_ratio()

            logging.info("")
            logging.info("cycles:       %d", cycles)
            logging.info("handled_bytes:%d", handled_bytes)
            logging.info("ratio_after: %.2f", ratio)
            logging.info("throughput:   %.2fGbps", ratio * 2.2 * 8)
            logging.info("ratio_after [%d]:%.2f", i, ratio)
            ratio_after_sum += ratio
            ratio_after = ratio_after_sum / (i + 1)

            if i < grace_period:
                continue

            if ratio_before > ratio_after * 1.3:
                break

        if ratio_before < ratio_after:
            self.last_good_action = self.epoch

            if move in self.failed_moves_history:
                self.failed_moves_history[move]["regret_penalty"] = \
                    self.initial_regret_penalty
            return True

        # logging.info("regret")
        if move not in self.failed_moves_history:
            self.failed_moves_history[move] = \
                {"regret_penalty": self.initial_regret_penalty}
        else:
            self.failed_moves_history[move]["regret_penalty"] *= \
                self.regret_penalty_factor
        self.failed_moves_history[move]["last_failed_move_epoch"] = self.epoch

        logging.info("last_failed_move_epoch: %d",
                     self.failed_moves_history[move]["last_failed_move_epoch"])
        logging.info("regret_penalty:    %d",
                     self.failed_moves_history[move]["regret_penalty"])
        # timer.done()
        return False


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

        self.history_rounds = 0
        self.history = {"average_bytes_per_packet": [0, 0, 0],
                        "ratio": [0, 0, 0],
                        "overall_io_ratio": [0, 0, 0],
                        "effective_io_ratio": [0, 0, 0]}
        self._init_history()

    def initialize(self):
        pass

    def print_load(self):
        vhost_inst = Vhost.INSTANCE.vhost_light  # Vhost.INSTANCE

        logging.info("\x1b[37mempty ratio is %.2f.\x1b[39m" % (self.ratio,))
        logging.info("\x1b[37meffective io ratio is %.2f.\x1b[39m" %
                     (self.effective_io_ratio,))

        logging.info("----------------")
        for c in sorted(vhost_inst.per_worker_counters.values(),
                        key=lambda x: x.name):
            logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))
        logging.info("\x1b[37mticks %.2f.\x1b[39m" %
                     (float(CPUUsage.INSTANCE.get_ticks()),))

        logging.info("\x1b[37moverall workers cpu %.2f.\x1b[39m" %
                     (self.overall_io_ratio,))
        logging.info("----------------")
        for c in sorted(vhost_inst.per_queue_counters.values(),
                        key=lambda x: x.name):
            logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))

        logging.info("efficient io ratio: %.2f" %
                     (self.effective_io_ratio / self.overall_io_ratio,))

    def _init_history(self):
        self.history_rounds = 0
        self.history = {key: [0, 0, 0] for key in self.history.keys()}

    def print_history(self):
        if self.history_rounds == 0:
            logging.info("\x1b[37mno history recorded.\x1b[39m")
            return

        logging.info("----------------")
        for key, (sum_ratio, min_ratio, max_ratio) in self.history.items():
            logging.info("\x1b[37m %s: avg: %3.2f, max: %3.2f, "
                         "min: %3.2f.\x1b[39m" %
                         (key, sum_ratio / self.history_rounds, min_ratio,
                          max_ratio))

    def update_history(self):
        logging.info("\x1b[37mggggggggggggggggrrrrrrrrrrrrrrrr2.\x1b[39m")
        self.history_rounds += 1

        def update(field, new_val):
            if self.history_rounds == 1:
                self.history[field][0] = self.history[field][1] = \
                    self.history[field][2] = new_val
                return

            self.history[field][0] += new_val
            self.history[field][1] = min(new_val, self.history[field][1])
            self.history[field][2] = max(new_val, self.history[field][2])

        # update("average_bytes_per_packet", self.average_bytes_per_packet)
        update("ratio", self.ratio)
        update("overall_io_ratio", self.overall_io_ratio)
        update("effective_io_ratio", self.effective_io_ratio)

        if self.history_rounds == 100:
            self.print_history()
            self._init_history()

    def calculate_load(self, shared_workers):
        # timer = Timer("Timer IOWorkerThroughputPolicy.calculate_load")
        vhost_inst = Vhost.INSTANCE.vhost_light  # Vhost.INSTANCE
        workers = Vhost.INSTANCE.workers

        cycles_this_epoch = vhost_inst.cycles.delta

        self.io_cores = len(workers) if shared_workers else 1
        self.shared_workers = shared_workers

        total_cycles_this_epoch = cycles_this_epoch * self.io_cores
        empty_cycles = total_cycles_this_epoch - vhost_inst.work_cycles.delta

        # logging.info("\x1b[37mcycles.delta      %d.\x1b[39m" %
        #              (vhost_inst.cycles.delta,))
        # logging.info("\x1b[37mwork_cycles       %d.\x1b[39m" %
        #              (vhost_inst.work_cycles.delta,))
        # logging.info("\x1b[37mio_cores          %d.\x1b[39m" %
        #              (self.io_cores,))
        # logging.info("\x1b[37mcycles_this_epoch %d.\x1b[39m" %
        #              (cycles_this_epoch,))
        # logging.info("\x1b[37mempty_cycles      %d.\x1b[39m" %
        #              (empty_cycles,))

        # handled_bytes = vhost_inst.per_queue_counters["notif_bytes"].delta + \
        #     vhost_inst.per_queue_counters["poll_bytes"].delta
        # cycles = vhost_inst.cycles.delta
        # ratio_before = handled_bytes / float(cycles)
        # logging.info("cycles:       %d", cycles)
        # logging.info("handled_bytes:%d", handled_bytes)
        # logging.info("ratio_before: %.2f", ratio_before)
        # logging.info("throughput:   %.2fGbps", ratio_before * 2.2 * 8)

        softirq_cpu_ratio = 0
        if shared_workers:
            io_cores_cpus = [workers[w_id]["cpu"] for w_id in workers.keys()]
            # logging.info("\x1b[37mio_cores_cpus %s.\x1b[39m" %
            #              (str(io_cores_cpus),))
            softirq_cpu = CPUUsage.INSTANCE.get_softirq_cpu(io_cores_cpus)
            # logging.info("\x1b[37msoftirq_cpu %.2f.\x1b[39m" % (softirq_cpu,))
            total_interrupts = CPUUsage.INSTANCE.get_interrupts(io_cores_cpus)
            # logging.info("\x1b[37mtotal_interrupts %d.\x1b[39m" %
            #              (total_interrupts,))
            # logging.info("\x1b[37msoftirq_interference_this_epoch %d."
            #              "\x1b[39m" %
            #              (vhost_inst.softirq_interference.delta,))
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
            # logging.info("\x1b[37msoftirq cpu %.2f.\x1b[39m" %
            #              (softirq_cpu_ratio,))

        # the idle cycles ratio in the iocores not including the ksoftirq
        # activity (which is a useful work). 1 means a full core was wasted.
        self.ratio = float(empty_cycles) / float(cycles_this_epoch) - \
            softirq_cpu_ratio
        # this the ratio of cycles used to handle virtual IO.
        self.effective_io_ratio = \
            float(vhost_inst.work_cycles.delta) / \
            float(vhost_inst.cycles.delta) + \
            softirq_cpu_ratio

        # logging.info("\x1b[37mempty ratio is %.2f.\x1b[39m" % (self.ratio,))
        # logging.info("\x1b[37meffective io ratio is %.2f.\x1b[39m" %
        #              (self.effective_io_ratio,))

        # logging.info("----------------")
        # for c in sorted(vhost_inst.per_worker_counters.values(),
        #                 key=lambda x: x.name):
        #     logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))
        # logging.info("\x1b[37mticks %.2f.\x1b[39m" %
        #              (float(CPUUsage.INSTANCE.get_ticks()),))
        self.overall_io_ratio = \
            vhost_inst.per_worker_counters["cpu_usage_counter"].delta / \
            float(CPUUsage.INSTANCE.get_ticks())
        if self.overall_io_ratio == 0:
            self.overall_io_ratio = 0.0000001

        # logging.info("\x1b[37moverall workers cpu %.2f.\x1b[39m" %
        #              (self.overall_io_ratio,))
        # logging.info("----------------")
        # for c in sorted(vhost_inst.per_queue_counters.values(),
        #                 key=lambda x: x.name):
        #     logging.info("\x1b[37m%s %d.\x1b[39m" % (c.name, c.delta,))
        # logging.info("----------------")
        # if int(vhost_inst.per_worker_counters["loops"].delta) != 0:
        #     empty_polls = \
        #         float(vhost_inst.per_worker_counters["empty_polls"].delta)
        #     empty_works = \
        #         float(vhost_inst.per_worker_counters["empty_works"].delta)
        #     loops = float(vhost_inst.per_worker_counters["loops"].delta)
        #     logging.info("empty_polls ratio: %.2f." % (empty_polls / loops,))
        #     logging.info("empty_works ratio: %.2f." % (empty_works / loops,))
        # else:
        #     logging.info("empty_polls ratio: 0.0.")
        #     logging.info("empty_works ratio: 0.0.")

        # self.average_bytes_per_packet = 0
        # if vhost_inst.per_queue_counters["sendmsg_calls"].delta > 0:
        #     self.average_bytes_per_packet = \
        #         float(vhost_inst.per_queue_counters["notif_bytes"].delta +
        #               vhost_inst.per_queue_counters["poll_cycles"].delta) / \
        #         vhost_inst.per_queue_counters["sendmsg_calls"].delta

        # logging.info("efficient io ratio: %.2f" %
        #              (self.effective_io_ratio / self.overall_io_ratio,))
        # timer.done()

    def should_update_core_number(self):
        # vhost_inst = Vhost.INSTANCE.vhost_light  # Vhost.INSTANCE
        add, can_remove = self._should_update_core_number(self.ratio)
        # if add:
        #     logging.info("\x1b[37mshould add IO workers, empty cycles "
        #                  "ratio is %.2f.\x1b[39m" % (self.ratio,))
        #
        #     cycles_this_epoch = vhost_inst.cycles.delta
        #     logging.info("\x1b[37mcycles_this_epoch: %d.\x1b[39m" %
        #                  (cycles_this_epoch,))
        #
        #     total_cycles_this_epoch = cycles_this_epoch * self.io_cores
        #     empty_cycles = \
        #         total_cycles_this_epoch - vhost_inst.work_cycles.delta
        #     logging.info("\x1b[37mempty_cycles: %d.\x1b[39m" %
        #                  (empty_cycles,))
        #     logging.info("\x1b[37mcycles_this_epoch: %d.\x1b[39m" %
        #                  (cycles_this_epoch,))
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
        return True, max(int(self.effective_io_ratio + .9), 1)

    def should_stop_shared_worker(self):
        if not self.shared_workers or self.io_cores > 1:
            return False
        full_ratio = 1.0 - self.ratio
        if self.stop_shared_ratio <= full_ratio:
            return False
        #
        # logging.info("\x1b[37mshould disable shared workers.\x1b[39m")
        # logging.info("\x1b[37mshared_workers: %s.\x1b[39m" %
        #              (self.shared_workers,))
        # logging.info("\x1b[37mio_cores: %d.\x1b[39m" % (self.io_cores,))
        # logging.info("\x1b[37mstop_shared_ratio: %.3f.\x1b[39m" %
        #              (self.stop_shared_ratio,))
        # logging.info("\x1b[37mfull_ratio: %.3f.\x1b[39m" % (full_ratio,))
        # return True


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

        self.ratio = 0.0

        self.history_rounds = None
        self.history = None
        self._init_history()

    def _init_history(self):
        self.history_rounds = 0
        self.history = {cpu: [0, 0, 0] for cpu in self.cpus}

    def print_history(self):
        if self.history_rounds == 0:
            logging.info("\x1b[37mno history recorded.\x1b[39m")
            return

        logging.info("----------------")
        for cpu, empty_cpu_ratio in self.history.items():
            min_ratio, max_ratio, sum_ratio = empty_cpu_ratio
            logging.info("\x1b[37mvm cores [%2d] empty cycles ratio: "
                         "avg: %3.2f, max: %3.2f, min: %3.2f.\x1b[39m" %
                         (cpu, sum_ratio / self.history_rounds, min_ratio,
                          max_ratio))

    def update_history(self):
        logging.info("\x1b[37mggggggggggggggggrrrrrrrrrrrrrrrr.\x1b[39m")
        self.history_rounds += 1
        for cpu, empty_cpu_ratio in self.history.items():
            ratio = CPUUsage.INSTANCE.get_empty_cpu((cpu,))
            if self.history_rounds == 1:
                empty_cpu_ratio[0] = empty_cpu_ratio[1] = \
                    empty_cpu_ratio[2] = ratio
                continue

            # min ratio
            empty_cpu_ratio[0] = min(empty_cpu_ratio[0], ratio)
            # max ratio
            empty_cpu_ratio[1] = max(empty_cpu_ratio[1], ratio)
            # sum ratio
            empty_cpu_ratio[2] += ratio

        if self.history_rounds == 100:
            self.print_history()
            self._init_history()

    def add(self, cpu_id):
        self.cpus.append(int(cpu_id))
        self._init_history()

    def remove(self, cpu_ids):
        for cpu_id in cpu_ids:
            self.cpus.remove(int(cpu_id))
        self._init_history()

    def print_load(self):
        logging.info("----------------")
        logging.info("\x1b[37mvm cores empty cycles ratio is %.2f.\x1b[39m" %
                     (self.ratio,))

    def should_update_core_number(self):
        self.ratio = CPUUsage.INSTANCE.get_empty_cpu(self.cpus)
        add, can_remove = self._should_update_core_number(self.ratio)
        # logging.info("\x1b[37mcan%s remove a VM core, empty cycles ratio is "
        #              "%.2f.\x1b[39m" % ("" if can_remove else "not", ratio))
        # logging.info("\x1b[37mcan_remove_ratio: %.2f.\x1b[39m" %
        #              (self.can_remove_ratio,))
        # logging.info("\x1b[37mcan remove: %s.\x1b[39m" %
        #              (self.can_remove_ratio < ratio,))
        #
        # logging.info("\x1b[37mshould%s add VM cores, empty cycles ratio is "
        #              "%.2f.\x1b[39m" % ("" if add else " not", ratio))
        # logging.info("\x1b[37madd_ratio: %.2f.\x1b[39m" % (self.add_ratio,))
        # logging.info("\x1b[37mVM cores are %s.\x1b[39m" % (self.cpus, ))
        return add, can_remove
