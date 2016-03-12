import logging
from utils.backing_device import BackingDevice

__author__ = 'eyalmo'


class BackingDeviceManager:
    def __init__(self, backing_devices_info, backing_devices_policy):
        self.backing_devices = {bd_info["id"]: BackingDevice(bd_info)
                                for bd_info in backing_devices_info}

        self.backing_devices_policy = backing_devices_policy

    def initialize(self, io_workers, vm_manager):
        logging.info("\x1b[37mBackingDeviceManager initialize\x1b[39m")
        self.backing_devices_policy.initialize(self.backing_devices,
                                               io_workers, vm_manager)

    def balance(self, io_workers):
        # logging.info("\x1b[37mUpdating backing devices\x1b[39m")
        self.backing_devices_policy.balance(io_workers)

    def update(self):
        for bd in self.backing_devices.values():
            bd.next_cpu()
