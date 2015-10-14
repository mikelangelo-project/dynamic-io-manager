#!/usr/bin/python
import logging
from utils.vhost import vhost_write, Vhost

LATENCY = "latency"
THROUGHPUT = "throughput"
LOW_USAGE = "low_usage"
HIGH_USAGE = "high_usage"


class VirtualQueueClassifier:
    def __init__(self, classifier_info):
        # the amount of bytes that has to pass through the queue to be
        # considered active
        self.active_threshold = classifier_info["active_threshold"]  # 1 << 20

    @staticmethod
    def initialize():
        queues = Vhost.INSTANCE.queues
        devices = Vhost.INSTANCE.devices

        for vq in queues.values():
            vq["bytes_total"] = 0
            vq["classification"] = LOW_USAGE
        for dev in devices.values():
            dev["classification"] = LOW_USAGE

    def update_classifications(self, can_update):
        queues = Vhost.INSTANCE.queues
        devices = Vhost.INSTANCE.devices

        possible_low_usage_devices = set()
        for vq in queues.values():
            bytes_total = vq["notif_bytes"] + vq["poll_bytes"]
            bytes_total_last_epoch = vq["bytes_total_last_epoch"] = \
                vq["bytes_total"]
            vq["bytes_total"] = bytes_total

            if not can_update:
                continue

            delta = bytes_total - bytes_total_last_epoch
            if (delta > self.active_threshold) and \
                    (vq["classification"] == LOW_USAGE):
                vq["classification"] = HIGH_USAGE
                devices[vq["dev"]]["classification"] = HIGH_USAGE
                continue

            if (delta < self.active_threshold) and \
                    (vq["classification"] != LOW_USAGE):
                vq["classification"] = LOW_USAGE
                possible_low_usage_devices.add(vq["dev"])

        # go over all the devices suspected as low usage and mark the ones that
        # all their virtual queues are marked as low usage
        for dev_id in possible_low_usage_devices:
            dev = devices[dev_id]
            for vq_id in dev["vq_list"]:
                if queues[vq_id]["classification"] != LOW_USAGE:
                    continue
            dev["classification"] = LOW_USAGE

# class VirtualQueueClassifier:
#     def __init__(self, classifier_info):
#         # maximum number of pending items to consider the queue as stuck
#         self.items_threshold = classifier_info["items_threshold"]  # 50
#         # maximum number of cycles a queue can be stuck without service
#         self.max_stuck_cycles = classifier_info["max_stuck_cycles"]  # 1 << 14
#         # the number of time a queue needs to be stuck during an epoch to be
#         # considered latency sensitive
#         self.latency_threshold = classifier_info["latency_threshold"]  # 10
#         # the number of time a queue needs to be limited during an epoch to be
#         # considered throughput oriented
#         self.throughput_threshold = \
#             classifier_info["throughput_threshold"]  # 10
#
#         self.latency_min_processed_data_limit = \
#             classifier_info["latency_min_processed_data_limit"]  # 1 << 13
#         self.latency_max_processed_data_limit = \
#             classifier_info["latency_max_processed_data_limit"]  # 1 << 16
#
#         self.throughput_min_processed_data_limit = \
#             classifier_info["throughput_min_processed_data_limit"]  # 1 << 15
#         self.throughput_max_processed_data_limit = \
#             classifier_info["throughput_max_processed_data_limit"]  # 1 << 19
#
#         # the maximum number of cycles the worker work list can with pending
#         # items without service
#         self.work_list_max_stuck_cycles = \
#             classifier_info["work_list_max_stuck_cycles"]  # 1 << 14
#
#         # the amount of bytes that has to pass through the queue to be
#         # considered active
#         self.active_threshold = classifier_info["active_threshold"]  # 1 << 20
#
#     def initialize(self):
#         vhost = Vhost.INSTANCE
#         for w in vhost.workers.values():
#             w["work_list_max_stuck_cycles"] = self.work_list_max_stuck_cycles
#             vhost_write(w, "work_list_max_stuck_cycles",
#                         w["work_list_max_stuck_cycles"])
#
#         for vq in vhost.queues.values():
#             vq["min_processed_data_limit"] = \
#                 self.throughput_min_processed_data_limit
#             vhost_write(vq, "min_processed_data_limit",
#                         vq["min_processed_data_limit"])
#             vq["max_processed_data_limit"] = \
#                 self.throughput_max_processed_data_limit
#             vhost_write(vq, "max_processed_data_limit",
#                         vq["max_processed_data_limit"])
#             vq["max_stuck_pending_items"] = self.items_threshold
#             vhost_write(vq, "max_stuck_pending_items",
#                         vq["max_stuck_pending_items"])
#             vq["max_stuck_cycles"] = self.max_stuck_cycles
#             vhost_write(vq, "max_stuck_cycles", vq["max_stuck_cycles"])
#             vq["classification"] = LOW_USAGE
#
#             vq["stuck_times_last_epoch"] = vq["stuck_times"]
#             vq["poll_limited_last_epoch"] = vq["poll_limited"]
#             vq["stuck_cycles_last_epoch"] = vq["stuck_cycles"]
#
#     def update_classifications(self):
#         vhost = Vhost.INSTANCE
#         if self.epochs_last_action < self.cooling_off_period:
#             self.epochs_last_action += 1
#
#             for vq in vhost.queues.values():
#                 vq["stuck_times_last_epoch"] = vq["stuck_times"]
#                 vq["poll_limited_last_epoch"] = vq["poll_limited"]
#                 vq["stuck_cycles_last_epoch"] = vq["stuck_cycles"]
#             return None
#
#         for vq in vhost.queues.values():
#             stuck_times_delta = vq["stuck_times"] - \
#                                 vq["stuck_times_last_epoch"]
#             vq["stuck_times_last_epoch"] = vq["stuck_times"]
#             poll_limited_delta = vq["poll_limited"] - \
#                 vq["poll_limited_last_epoch"]
#             vq["poll_limited_last_epoch"] = vq["poll_limited"]
#             vq["stuck_cycles_last_epoch"] = vq["stuck_cycles"]
#
#             # classify the queue as latency sensitive
#             if vq["poll"] == 1 and vq["classification"] != LATENCY and \
#                     stuck_times_delta > self.latency_threshold:
#                 logging.info("\x1b[37mvq=%s classified as latency sensitive, "
#                              "stuck_times_delta: %d.\x1b[39m" %
#                              (vq["id"], stuck_times_delta))
#
#                 # vq["min_processed_data_limit"] = \
#                 #     self.latency_min_processed_data_limit
#                 # vhost_write(vq, "min_processed_data_limit",
#                 #             vq["min_processed_data_limit"])
#                 # vq["max_processed_data_limit"] = \
#                 #     self.latency_max_processed_data_limit
#                 # vhost_write(vq, "max_processed_data_limit",
#                 #             vq["max_processed_data_limit"])
#                 vq["classification"] = LATENCY
#                 continue
#
#             # classify the queue as throughput oriented
#             if vq["poll"] == 1 and \
#                     poll_limited_delta > self.throughput_threshold:
#                 logging.info("\x1b[37mvq=%s classified as throughput "
#                              "oriented, poll_limited_delta: %d.\x1b[39m" %
#                              (vq["id"], poll_limited_delta))
#
#                 # vq["min_processed_data_limit"] = \
#                 #     self.throughput_min_processed_data_limit
#                 # vhost_write(vq, "min_processed_data_limit",
#                 #             vq["min_processed_data_limit"])
#                 # vq["max_processed_data_limit"] = \
#                 #     self.throughput_max_processed_data_limit
#                 # vhost_write(vq, "max_processed_data_limit",
#                 #             vq["max_processed_data_limit"])
#                 vq["classification"] = THROUGHPUT
#                 continue
#
#             # the queue stopped polling so we have no need to classify it as
#             # unknown
#             if vq["poll"] == 0 and vq["classification"] != LOW_USAGE:
#                 logging.info("\x1b[37mvq=%s classified as unknown.\x1b[39m" %
#                              (vq["id"],))
#
#                 # vq["min_processed_data_limit"] = \
#                 #     self.throughput_min_processed_data_limit
#                 # vhost_write(vq, "min_processed_data_limit",
#                 #             vq["min_processed_data_limit"])
#                 # vq["max_processed_data_limit"] = \
#                 #     self.throughput_max_processed_data_limit
#                 # vhost_write(vq, "max_processed_data_limit",
#                 #             vq["max_processed_data_limit"])
#                 vq["classification"] = LOW_USAGE
