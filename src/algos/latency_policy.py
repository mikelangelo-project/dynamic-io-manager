#!/usr/bin/python
import logging

from utils.vhost import Vhost


class LatencyPolicy:
    def __init__(self, balancer_info):
        pass
        # self.cooling_off_period = 0
        # self.epochs_last_action = 0
        #
        # # the ratio between the total work cycles available and the amount of
        # # stuck cycles in latency sensitive queues.
        # self.add_ratio = balancer_info["add_ratio"]  # 0.5
        # # the ratio between the total work cycles available and the amount of
        # # stuck cycles in latency sensitive queues.
        # self.remove_ratio = balancer_info["remove_ratio"]  # 0.01
        #
        # self.last_action = None

    @staticmethod
    def initialize():
        pass
        # for vq in Vhost.INSTANCE.queues.values():
        #     vq["stuck_cycles_last_epoch"] = vq["stuck_cycles"]

    def update_io_core_number(self, shared_workers):
        return "stay"

        # vhost = Vhost.INSTANCE
        #
        # if self.epochs_last_action < self.cooling_off_period:
        #     self.epochs_last_action += 1
        #
        #     for vq in vhost.queues.values():
        #         vq["stuck_cycles_last_epoch"] = vq["stuck_cycles"]
        #     return "stay"
        #
        # total_latency_sensitive_stuck_cycles = 0
        # latency_sensitive_queues = 0
        # for vq in vhost.queues.values():
        #     if vq["poll"] == 1 and vq["classification"] == "latency":
        #         poll_stuck_cycles_delta = vq["stuck_cycles"] - \
        #             vq["stuck_cycles_last_epoch"]
        #         total_latency_sensitive_stuck_cycles += poll_stuck_cycles_delta
        #         latency_sensitive_queues += 1
        #
        # # check if we need to change the number of I/O cores in the system
        # # calculate the number of stuck cycles per workers with devices
        # # (consider them as one queue)
        #
        # cycles_this_epoch = vhost.vhost["cycles_this_epoch"]
        # if latency_sensitive_queues > 0:
        #     latency_ratio = total_latency_sensitive_stuck_cycles / \
        #         float(cycles_this_epoch) / latency_sensitive_queues
        # else:
        #     return "stay"
        #
        # logging.info("total_latency_sensitive_stuck_cycles: %d" %
        #              (total_latency_sensitive_stuck_cycles, ))
        # logging.info("latency_sensitive_queues: %d" %
        #              (latency_sensitive_queues, ))
        # logging.info("cycles_this_epoch: %d" % (cycles_this_epoch, ))
        # logging.info("qos_ratio: %d" % (latency_ratio, ))
        #
        # if latency_ratio > self.add_ratio:
        #     return "add"
        #
        # if latency_ratio < self.remove_ratio:
        #     return "remove"
        #
        # return "stay"