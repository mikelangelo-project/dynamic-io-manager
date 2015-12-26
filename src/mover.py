#!/usr/bin/python
import json
import logging
import os
import sys
import time
import getopt

from io_workers_manager import IOWorkersManager
from backing_device_manager import BackingDeviceManager
from poll_policy import NullPollPolicy
from vm_manager import VMManager

from algos.backing_devices_rebalance_policy import \
    BackingDevicesPreConfiguredBalancePolicy
from algos.io_cores_rebalance_policy import IOCoresPreConfiguredBalancePolicy
from algos.vms_rebalance_policy import VmsPreConfiguredBalancePolicy
from algos.removal_policy import LastAddedPolicy
from algos.throughput_policy import VMCoreAdditionPolicy, \
    IOWorkerThroughputPolicy, ThroughputRegretPolicy
from algos.latency_policy import LatencyPolicy
from algos.vq_classifier import VirtualQueueClassifier

from utils.cpuusage import CPUUsage
from utils.get_cycles.get_cycles import Cycles
from utils.vhost import Vhost
from utils.aux import msg, Timer
from utils.daemon import Daemon


def usage(program_name, error):
    print('Error: %s' % (str(error), ))
    print('USAGE: %s <io manager configuration> OPTIONS' % (program_name, ))
    print('Reconfigures the environment to match each configuration every given'
          'interval')
    print('OPTIONS:')
    print('-s/--setup <io manager configuration>: starts mover with '
          'configuration.')
    print('-k/--kill: kills the mover that runs in a daemon.')
    sys.exit()

MOVER_PID = "/tmp/io_manager_pid.txt"
MOVER_INTERVAL = 1


class MoverDaemon(Daemon):
    def __init__(self, io_workers_manager, vm_manager, backing_device_manager,
                 interval):
        Daemon.__init__(self, MOVER_PID)
        self.vm_manager = vm_manager
        self.interval = interval
        self.io_workers_manager = io_workers_manager
        self.backing_device_manager = backing_device_manager
        CPUUsage.initialize()
        Cycles.initialize()
        self.interval_in_cycles = self.interval * Cycles.cycles_per_second

    def run(self):
        timer = Timer("Timer Mover")
        Vhost.INSTANCE.update()
        CPUUsage.INSTANCE.update()
        # print_all(self.vhost)
        self.io_workers_manager.initialize()
        self.vm_manager.update()

        vm_balance_policy = \
            self.vm_manager.vm_balance_policy
        workers_balance_policy = \
            self.io_workers_manager.balance_policy
        backing_device_manager = \
            self.backing_device_manager.backing_devices_policy
        configuration_ids = vm_balance_policy.vms_configurations.keys()

        i = 0
        # while i < 15:
        while True:
            for conf_id in configuration_ids:
                if self.interval >= 0.1:
                    time.sleep(self.interval)
                else:
                    # we don't sleep here just delay until its time
                    Cycles.delay(self.interval_in_cycles)
                logging.info("round %d" % (i,))
                timer.checkpoint("round %d" % (i,))

                vm_balance_policy.balance_by_configuration(conf_id,
                                                           self.vm_manager.vms)
                backing_device_manager.balance_by_configuration(
                    conf_id, self.io_workers_manager.io_workers)
                balance_changes = \
                    workers_balance_policy.balance_by_configuration(
                        conf_id, self.io_workers_manager.io_workers)
                self.io_workers_manager.move_devices(balance_changes)
                i += 1

        logging.info("*****Done****")


def main(argv):
    if len(argv) < 2:
        usage(argv[0], "Wrong number of arguments, expected at least 1 got %d"
              % (len(argv) - 1,))

    opts = None
    try:
        opts, args = getopt.getopt(argv[1:], "s:kh",
                                   ["start=", "kill", "help"])
    except getopt.GetoptError:
        usage(argv[0], "Illegal Argument!")

    configuration_filename = None
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(argv[0], "Help")
        elif opt in ("-s", "--start"):
            msg("configuration file: %s" % (arg, ))
            configuration_filename = arg
            break
        elif opt in ("-k", "--kill"):
            msg("kills an mover that runs in a daemon.")
            Daemon(MOVER_PID).stop()
            sys.exit()

    if not os.path.exists(configuration_filename):
        usage(argv[0], "Configuration file doesn't exists!")

    with open(configuration_filename) as f:
        config = json.load(f)

    # start the log file if exists
    if "log" in config and config["log"]:
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.expanduser(config["log"])
        timestamp_log_file = log_file + ".%s.txt" % (timestamp,)
        log_format = "[%(filename)s:%(lineno)s] %(message)s"
        logging.basicConfig(filename=timestamp_log_file,
                            format=log_format, level=logging.INFO)
        # logging.basicConfig(stream=sys.stdout, format=log_format,
        #                     level=logging.INFO)
        logging.info("****** start of a new run: %s ******" %
                     (timestamp,))
        if os.path.exists(log_file):
            os.unlink(log_file)
        os.symlink(timestamp_log_file, log_file)

    # set the interval in which the IO manager works
    interval = float(config["interval"]) if "interval" in config \
        else MOVER_INTERVAL
    logging.info(interval)

    # initialize vhost
    Vhost.initialize()
    Vhost.INSTANCE.update(True)

    # get backing devices info
    backing_devices_policy = \
        BackingDevicesPreConfiguredBalancePolicy(
            config["backing_devices_balance_policy"])
    bdm = BackingDeviceManager(config["backing_devices"],
                               backing_devices_policy)

    # start the vm manager
    vm_policy = LastAddedPolicy.create_vm_policy(config["vms"])
    vm_balance_policy = \
        VmsPreConfiguredBalancePolicy(config["vms_balance_policy"],
                                      vm_policy.cpus)
    # vm_balance_policy = VmsRunEverywhereBalancePolicy()
    vm_core_addition_policy = \
        VMCoreAdditionPolicy(config["vms"], config["vm_core_addition_policy"])
    vm_manager = VMManager(config["vms"], bdm.backing_devices,
                           vm_policy, vm_core_addition_policy,
                           vm_balance_policy)
    # get devices
    devices = [dev for vm in vm_manager.vms for dev in vm.devices]

    # set up manager policies
    vq_classifier = VirtualQueueClassifier(config["virtual_queue_classifier"])
    # poll_policy = PollPolicy(config["poll_policy"])
    poll_policy = NullPollPolicy()
    io_core_policy = LastAddedPolicy.create_io_cores_policy(config["workers"])
    io_core_balance_policy = \
        IOCoresPreConfiguredBalancePolicy(config["io_cores_balance_policy"],
                                          devices)
    # io_core_balance_policy = BalanceByDeviceNumberPolicy()
    throughput_policy = IOWorkerThroughputPolicy(config["throughput_policy"])
    latency_policy = LatencyPolicy(config["latency_policy"])
    regret_policy = ThroughputRegretPolicy(config["throughput_regret_policy"])

    # setup the io core controller
    io_workers_manager = IOWorkersManager(devices, vm_manager, bdm,
                                          config["workers"],
                                          vq_classifier,
                                          poll_policy,
                                          throughput_policy,
                                          latency_policy,
                                          io_core_policy,
                                          io_core_balance_policy,
                                          regret_policy)

    daemon = MoverDaemon(io_workers_manager, vm_manager, bdm, interval)
    if "daemon" in config:
        if 'start' == config["daemon"]:
            daemon.start()
        elif 'stop' == config["daemon"]:
            daemon.stop()
        elif 'restart' == config["daemon"]:
            daemon.restart()
        elif 'no' == config["daemon"]:
            logging.info("running without daemon")
            daemon.run()
        else:
            usage(argv[0], "Unknown daemon command!")
    else:
        logging.info("running without daemon")
        daemon.run()

if __name__ == '__main__':
    main(sys.argv)
