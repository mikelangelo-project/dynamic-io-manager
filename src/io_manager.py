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
    BackingDevicesPreConfiguredBalancePolicy, BackingDevicesPolicy
from algos.io_cores_rebalance_policy import IOCoresPreConfiguredBalancePolicy
from algos.vms_rebalance_policy import VmsPreConfiguredBalancePolicy
from algos.removal_policy import LastAddedPolicy
from algos.throughput_policy import VMCoreAdditionPolicy, \
    IOWorkerThroughputPolicy, ThroughputRegretPolicy
from algos.latency_policy import LatencyPolicy
from algos.vq_classifier import VirtualQueueClassifier

from utils.cpuusage import CPUUsage
from utils.vhost import Vhost
from utils.aux import msg, Timer, LoggerWriter
from utils.daemon import Daemon

IO_MANAGER_PID = "/tmp/io_manager_pid.txt"
IO_MANAGER_INTERVAL = 1.0


def usage(program_name, error):
    print('Error: %s' % (str(error), ))
    print('USAGE: %s OPTIONS' % (program_name, ))
    print('I/O Manager')
    print('')
    print('OPTIONS:')
    print('-s/--setup <io manager configuration>: starts io manager with '
          'configuration.')
    print('-k/--kill: kills an io manager that runs in a daemon.')
    print('-p/--process: run as a process and direct all output to '
          'stdout+stderr.')
    print('')
    print('Configuration file example:')
    configuration_example = os.path.join(os.path.dirname(program_name), "..",
                                         "confs", "configuration_template.json")
    with open(configuration_example, 'r') as ce_file:
        print(ce_file.read())
    sys.exit()


class IOManagerDaemon(Daemon):
    def __init__(self, io_workers_manager, vm_manager, backing_device_manager,
                 interval):
        Daemon.__init__(self, IO_MANAGER_PID)
        self.vm_manager = vm_manager
        self.interval = interval
        self.io_workers_manager = io_workers_manager
        self.backing_device_manager = backing_device_manager
        CPUUsage.initialize()

    def run(self):
        # timer = Timer("Timer IOManager")
        Vhost.INSTANCE.update(light_update=False, update_epoch=True)
        CPUUsage.INSTANCE.update()
        # print_all(self.vhost)
        self.io_workers_manager.initialize()
        self.vm_manager.update()

        i = li = 0
        # lis = 20  # int(1.0 / self.interval) + 1

        while True:
            time.sleep(self.interval)
            logging.info("round %d" % (i,))
            # timer.checkpoint("round %d" % (i,))
            Vhost.INSTANCE.update()
            # timer.checkpoint("Vhost.INSTANCE.update()")
            CPUUsage.INSTANCE.update()
            # timer.checkpoint("CPUUsage.INSTANCE.update()")
            self.vm_manager.update()
            # timer.checkpoint("self.vm_manager.update()")
            # logging.info("cycles: %d" %
            #              (Vhost.INSTANCE.vhost["cycles"], ))
            # logging.info("cycles_last_epoch: %d" %
            #              (Vhost.INSTANCE.vhost["cycles_last_epoch"], ))
            # logging.info("cycles_this_epoch: %d" %
            #              (Vhost.INSTANCE.vhost["cycles_this_epoch"], ))

            self.io_workers_manager.update_vq_classifications()
            # timer.checkpoint("vq_classifier update_classification")
            self.io_workers_manager.update_io_core_number()
            # timer.checkpoint("io_workers_manager update_io_core_number")
            self.io_workers_manager.update_balance()
            # timer.checkpoint("io_workers_manager update_balance")
            self.io_workers_manager.update_polling()
            # timer.checkpoint("io_workers_manager update_polling")
            self.backing_device_manager.update()
            # timer.checkpoint("backing_device_manager update")
            i += 1
            # if i - li > lis:
            #     timer.done()
            #     li = i

        logging.info("*****Done****")


def main(argv):
    if len(argv) < 2:
        usage(argv[0], "Expected more arguments, got %d." %
              (len(argv),))

    opts = None
    try:
        opts, args = getopt.getopt(argv[1:], "s:kph",
                                   ["start=", "kill", "process", "help"])
    except getopt.GetoptError:
        usage(argv[0], "Illegal Argument!")

    configuration_filename = None
    no_daemon = False
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(argv[0], "Help")
        elif opt in ("-s", "--start"):
            msg("configuration file: %s" % (arg, ))
            configuration_filename = arg
        elif opt in ("-k", "--kill"):
            msg("kills an io manager that runs in a daemon.")
            Daemon(IO_MANAGER_PID).stop()
            sys.exit()
        elif opt in ("-p", "--process"):
            msg("run io manager with all output to stdout and stderr.")
            no_daemon = True

    # if not configuration_filename:
    #     usage(argv[0], "No configuration file provided.")

    if not os.path.exists(configuration_filename):
        usage(argv[0], "Configuration file doesn't exists!")

    with open(configuration_filename) as f:
        conf = json.load(f)

    # a way to run the manager not as daemon regardless of configuration file
    if no_daemon:
        conf["daemon"] = "no"

    # start the log file if exists
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    log_format = "[%(filename)s:%(lineno)s] %(message)s"
    if "log" in conf and conf["log"] and not no_daemon:
        log_file = os.path.expanduser(conf["log"])
        timestamp_log_file = log_file + ".%s.txt" % (timestamp,)
        logging.basicConfig(filename=timestamp_log_file,
                            format=log_format, level=logging.INFO)
        if os.path.exists(log_file):
            os.unlink(log_file)
        os.symlink(timestamp_log_file, log_file)
    else:
        logging.basicConfig(stream=sys.stdout, format=log_format,
                            level=logging.INFO)
        sys.stdout = LoggerWriter(logging.INFO)
        sys.stderr = LoggerWriter(logging.ERROR)
    logging.info("****** start of a new run: %s ******" % (timestamp,))

    # set the interval in which the IO manager works
    interval = float(conf["interval"]) if "interval" in conf \
        else IO_MANAGER_INTERVAL
    logging.info(interval)

    # initialize vhost
    Vhost.initialize()
    Vhost.INSTANCE.update(light_update=False, update_epoch=True,
                          rescan_files=False)

    # get backing devices info
    if "preconfigured" in conf["backing_devices_balance_policy"]["id"]:
        backing_devices_policy = \
            BackingDevicesPreConfiguredBalancePolicy(
                conf["backing_devices_balance_policy"])
    else:
        backing_devices_policy = BackingDevicesPolicy()
    bdm = BackingDeviceManager(conf["backing_devices"],
                               backing_devices_policy)

    # start the vm manager
    vm_policy = LastAddedPolicy.create_vm_policy(conf["vms"])
    vm_balance_policy = \
        VmsPreConfiguredBalancePolicy(conf["vms_balance_policy"],
                                      vm_policy.cpus)
    # vm_balance_policy = VmsRunEverywhereBalancePolicy()
    vm_core_addition_policy = \
        VMCoreAdditionPolicy(conf["vms"], conf["vm_core_addition_policy"])
    vm_manager = VMManager(conf["vms"], bdm.backing_devices,
                           vm_policy, vm_core_addition_policy,
                           vm_balance_policy)
    # get devices
    devices = [dev for vm in vm_manager.vms for dev in vm.devices]

    # set up manager policies
    vq_classifier = VirtualQueueClassifier(conf["virtual_queue_classifier"])
    # poll_policy = PollPolicy(conf["poll_policy"])
    poll_policy = NullPollPolicy()
    io_core_policy = LastAddedPolicy.create_io_cores_policy(conf["workers"])
    io_core_balance_policy = \
        IOCoresPreConfiguredBalancePolicy(conf["io_cores_balance_policy"],
                                          devices)
    # io_core_balance_policy = BalanceByDeviceNumberPolicy()
    throughput_policy = IOWorkerThroughputPolicy(conf["throughput_policy"])
    latency_policy = LatencyPolicy(conf["latency_policy"])
    regret_policy = ThroughputRegretPolicy(conf["throughput_regret_policy"])

    # setup the io core controller
    io_workers_manager = IOWorkersManager(devices, vm_manager, bdm,
                                          conf["workers"],
                                          vq_classifier,
                                          poll_policy,
                                          throughput_policy,
                                          latency_policy,
                                          io_core_policy,
                                          io_core_balance_policy,
                                          regret_policy)

    daemon = IOManagerDaemon(io_workers_manager, vm_manager, bdm, interval)
    if "daemon" in conf:
        if 'start' == conf["daemon"]:
            daemon.start()
        elif 'stop' == conf["daemon"]:
            daemon.stop()
        elif 'restart' == conf["daemon"]:
            daemon.restart()
        elif 'no' == conf["daemon"]:
            logging.info("running without daemon")
            daemon.run()
        else:
            usage(argv[0], "Unknown daemon command!")
    else:
        logging.info("running without daemon")
        daemon.run()

if __name__ == '__main__':
    main(sys.argv)
