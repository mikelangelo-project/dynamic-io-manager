#!/usr/bin/python
import logging

from utils.vhost import Vhost, vhost_write


class PollPolicy:
    def __init__(self, poll_info):
        # cycles per work
        self.poll_start_rate = long(poll_info["start_rate"])  # 1 << 22

        # cycles since last work
        self.poll_stop_idle = long(poll_info["stop_idle"])  # 1 << 34

        self.cooling_off_period = 6
        self.vqs_data = {}
        self.shared_workers = False

    def initialize(self, shared_workers):
        self.vqs_data = {vq_id: {"epochs_last_action": 0}
                         for vq_id in Vhost.INSTANCE.queues.keys()}
        self.shared_workers = shared_workers

    def update_polling(self):
        if not self.shared_workers:
            return

        cycles_this_epoch = Vhost.INSTANCE.vhost["cycles_this_epoch"]
        cycles = Vhost.INSTANCE.vhost["cycles"]

        for vq_id, vq in Vhost.INSTANCE.queues.items():
            if self.vqs_data[vq_id]["epochs_last_action"] < \
                    self.cooling_off_period:
                self.vqs_data[vq_id]["epochs_last_action"] += 1
                continue

            if vq["can_poll"] == 0 and vq["poll"] == 0:
                continue

            poll_idle = cycles - vq["last_poll_cycles"]
            if vq["poll"] == 1 and poll_idle > self.poll_stop_idle:
                logging.info("vq: %s" % (vq_id, ))
                # logging.info("poll: %d" % (vq["poll"], ))
                logging.info("poll_cycles: %s" % (vq["poll_cycles"], ))
                logging.info("last_poll_cycles: %d" %
                             (vq["last_poll_cycles"], ))
                logging.info("cycles: %d" % (cycles, ))
                logging.info("\x1b[37mvq=%s stop polling, poll_idle: "
                             "%d.\x1b[39m" % (vq_id, poll_idle))
                vhost_write(vq, "poll", 0)
                continue

            # checking for start rate
            notif_works_this_epoch = vq["notif_works_this_epoch"]
            cycles_per_work = cycles_this_epoch / notif_works_this_epoch \
                if notif_works_this_epoch != 0 else float("inf")
            if vq["poll"] == 0 and cycles_per_work < self.poll_start_rate:
                logging.info("vq: %s" % (vq_id, ))
                # logging.info("poll: %d" % (vq["poll"], ))
                logging.info("\x1b[37mvq=%s start polling, "
                             "cycles_per_work: %d.\x1b[39m" %
                             (vq_id, cycles_per_work))
                vhost_write(vq, "poll", 1)

    def enable_shared_workers(self):
        logging.info("\x1b[37menable shared IO workers.\x1b[39m\n")
        self.initialize(True)

    def disable_shared_workers(self):
        logging.info("\x1b[37mdisable shared IO workers.\x1b[39m\n")
        self.shared_workers = False
        self._stop_polling()

    @staticmethod
    def _stop_polling():
        for vq_id, vq in Vhost.INSTANCE.queues.items():
            if vq["can_poll"] == 0 and vq["poll"] == 0:
                continue
            # logging.info("\x1b[37mvq=%s stop polling.\x1b[39m" % (vq_id,))
            vhost_write(vq, "poll", 0)


class NullPollPolicy:
    def __init__(self):
        pass

    def initialize(self, shared_workers):
        pass

    def update_polling(self):
        pass

    @staticmethod
    def enable_shared_workers():
        logging.info("\x1b[37menable shared IO workers - start polling."
                     "\x1b[39m\n")
        for vq_id, vq in Vhost.INSTANCE.queues.items():
            if vq["can_poll"] == 0 or vq["poll"] == 1:
                continue
            # logging.info("\x1b[37mvq=%s start polling.\x1b[39m" % (vq_id,))
            vhost_write(vq, "poll", 1)

    @staticmethod
    def disable_shared_workers():
        logging.info("\x1b[37mdisable shared IO workers - stop polling."
                     "\x1b[39m\n")
        for vq_id, vq in Vhost.INSTANCE.queues.items():
            if vq["can_poll"] == 0 and vq["poll"] == 0:
                continue
            # logging.info("\x1b[37mvq=%s stop polling.\x1b[39m" % (vq_id,))
            vhost_write(vq, "poll", 0)
