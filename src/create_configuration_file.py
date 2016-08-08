#!/usr/bin/python
import json
import os
import subprocess
from utils.aux import msg, err, ls

__author__ = 'yossiku'

def usage(program_name, error):
    print("%s <num_of_cores> <network_if_name_1> [network_if_name_2]" % (program_name, ))
    sys.exit(0)

class IOManager:
    MOUNT_POINT = "/sys/class/vhost"

    def __init__(self,  num_of_cores, if_names):
        self.num_of_cores = num_of_cores
        self.if_names = if_names
        self.devices = self.vhost_get_devices()
    
        self.vcpu_affinity = self.expandrange("0-%d" % (self.num_of_cores-1))

    def expandrange(self, s):
        r = []
        for i in s.split(','):
            if '-' not in i:
                r.append(int(i))
            else:
                l,h = map(int, i.split('-'))
                r += range(l, h+1)
        return r

    def get_vms_pids(self):
        pids = []
        for row in subprocess.check_output(["/bin/ps", "-Ao", "pid,cmd",
                                            "--no-headers"]).split("\n"):
            parsed_line = row.strip().split()
            if not parsed_line:
                continue
            pid = int(parsed_line[0])
            cmd = parsed_line[1:]
            if 'qemu' in " ".join(cmd):
                pids.append(pid)
        return pids

    def vhost_get_devices(self):
        return [dev_id for dev_id in ls(os.path.join(self.MOUNT_POINT, "dev"))
                if dev_id not in ["power", "subsystem", "uevent"]]

    def get_config_file(self):
        vms_pids = self.get_vms_pids()
        config = {}

        config["daemon"] = "restart"
        config["poll_policy"] = {
            "stop_idle": "17179869184",
            "start_rate": "4194304"
        }

        config["log"] = "/tmp/io_manager.log"
        config["throughput_policy"] = {
            "configurations": [
                {
                    "min_average_byte_per_packet": 0,
                    "can_remove_ratio": 0.0,
                    "add_ratio": 0.4,
                    "id": "elvis-0",
                    "vhost_workers": 0
                },
                {
                    "min_average_byte_per_packet": 0,
                    "can_remove_ratio": 0.8,
                    "add_ratio": 0.05,
                    "id": "elvis-1",
                    "vhost_workers": 1
                },
                {
                    "min_average_byte_per_packet": 0,
                    "can_remove_ratio": 0.5,
                    "add_ratio": 0.05,
                    "id": "elvis-2",
                    "vhost_workers": 2
                },
                {
                    "min_average_byte_per_packet": 0,
                    "can_remove_ratio": 0.8,
                    "add_ratio": 0.05,
                    "id": "elvis-3",
                    "vhost_workers": 3
                },
                {
                    "min_average_byte_per_packet": 0,
                    "can_remove_ratio": 1.0,
                    "add_ratio": -0.05,
                    "id": "elvis-4",
                    "vhost_workers": 4
                }
            ]
        }
        config["interval"] = "0.1"
        config["vm_core_addition_policy"] = {
            "add_ratio": "0.05",
            "can_remove_ratio": "1.0"
        }
        config["latency_policy"] = {}
        config["workers"] = []
        config["virtual_queue_classifier"] = {
            "items_threshold": "50",
            "throughput_min_processed_data_limit": "32768",
            "latency_threshold": "10",
            "throughput_max_processed_data_limit": "524288",
            "throughput_threshold": "10",
            "active_threshold": "1048576",
            "latency_max_processed_data_limit": "65536",
            "work_list_max_stuck_cycles": "16384",
            "latency_min_processed_data_limit": "8192",
            "max_stuck_cycles": "16384"
        }
        config["path"] = os.path.dirname(os.path.abspath(__file__))
        config["use_mover"] = False
        config["throughput_regret_policy"] = {
            "interval": "0.05"
        }

        config["vms"] = [
            {
                "id": str(idx),
                "pid": str(pid),
                "cpu": ",".join(str(x) for x in self.vcpu_affinity),
                "devices": [],
            } for idx, pid in enumerate(vms_pids, 1)
        ]

        # handling only one device per virtual machines
        if len(vms_pids) != len(self.devices):
            err("vms_pids size (%d) != self.devices size (%d)" % (len(vms_pids), len(self.devices)))

        for idx, (vm_info, dev_name) in enumerate(zip(config["vms"], self.devices), 1):
            dev = {
                      "id": dev_name,
                      "vhost_worker": "w.{0}".format(idx)
                  }
            vm_info["devices"].append(dev)

        config["io_cores_balance_policy"] = {
            "id": "preconfigured",
            "configurations": [
                {
                    "vms": [
                        {
                            "id": vm["id"],
                            "vhost_worker": "w.{0}".format((idx % x)+1)
                        } for idx, vm in enumerate(config["vms"])
                    ],
                    "id": "elvis-{0}".format(x),
                    "vhost_workers": [
                        {
                            "id": "w.{0}".format(w)
                        } for w in xrange(1, x+1, 1)
                    ]
                } for x in xrange(1, 4+1, 1)
            ]
        }

        config["vms_balance_policy"] = {
            "id": "preconfigured",
            "configurations": [
                {
                    "cores": str(self.num_of_cores-x),
                    "id": "elvis-{0}".format(x),
                    "vms": [
                        {
                            "id": vm["id"],
                            "cpu": "{0}-{1}".format(x, self.num_of_cores-1)
                        } for vm in config["vms"]
                    ]
                } for x in xrange(0, 4+1, 1)
            ]
        }

        config["backing_devices"] = [
            {
                "interrupts": [
                    {
                        "irq_prefix": if_name
                    }
                ],
                "type": "physical",
                "id": "bd.{0}".format(idx+1)
            } for idx, if_name in enumerate(self.if_names)
        ]

        config["backing_devices_balance_policy"] = {
            "id": "preconfigured",
            "configurations": [
                {
                    "backing_devices": [
                        {
                            "id": "bd.{0}".format(idx+1),
                            "cpu": "{0}".format(idx % (x+1))
                        } for idx in xrange(0, len(self.if_names), 1)
                    ],
                    "id": "elvis-{0}".format(x),
                    "vhost_workers": x
                } for x in xrange(0, 4+1, 1)
            ]
        }
        return config


def main(argv):
    # parse command line options
    if len(argv) < 3:
        usage(argv[0], "Not enough arguments!")

    num_of_cores = int(argv[1])
    if num_of_cores <= 4:
        err("num_of_cores must be greater than 4")

    if_names = [argv[2]]
    if len(argv) > 3:
        if_names.append(argv[3])

    io_manager = IOManager(num_of_cores, if_names)

    configuration_file = "/tmp/io_manager_configuration.json"
    conf = io_manager.get_config_file()
    with open(configuration_file, "w") as f:
        json.dump(conf, f, indent=2)

    msg("Configuration file written to %s" % configuration_file)

# ------------------
# Entry point
# -----------------
if __name__ == '__main__':
    import sys
    main(sys.argv)
