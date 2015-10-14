import logging
from utils.device import BackingDevice

__author__ = 'eyalmo'


class BackingDeviceManager:
    def __init__(self, backing_devices_info):
        self.backing_devices = {bd_info["id"]: BackingDevice(bd_info)
                                for bd_info in backing_devices_info}

    def initialize(self):
        logging.info("\x1b[37mBackingDeviceManager initialize\x1b[39m")

    def clear_affinity(self):
        logging.info("\x1b[37mClear the affinity of the backing "
                     "devices\x1b[39m")
        for bd in self.backing_devices.values():
            bd.zero_cpu_mask()

    def devices_moved(self, change_list):
        logging.info("\x1b[37mUpdating backing devices\x1b[39m")
        for dev_id, (old_cpu_id, new_cpu_id) in change_list.items():
            logging.info("dev_id: %s, old_cpu_id: %s, new_cpu_id: %s" %
                         (dev_id, old_cpu_id, new_cpu_id))
            for bd in self.backing_devices.values():
                if dev_id not in bd.devices:
                    continue
                logging.info("bd_id: %s" % (bd.id,))
                bd.update_cpu_mask(dev_id, old_cpu_id, new_cpu_id)

    def update(self):
        for bd in self.backing_devices.values():
            bd.next_cpu()
