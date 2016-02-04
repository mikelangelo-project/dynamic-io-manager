#!/usr/bin/python

import os
import sys
import getopt
import json
import re
from time import sleep
from utils.aux import msg
from utils.daemon import Daemon
from utils.affinity_entity import AffinityEntity

IRQ_DIRECTORY = "/proc/irq"
IRQ_FILENAME = "/proc/interrupts"


class IRQ(AffinityEntity):
    def __init__(self, irq_id, cpu_mask):
        AffinityEntity.__init__(self, cpu_mask)
        self.id = int(irq_id)
        self.current_cpu = self.first_cpu()
        self.apply_cpu_mask()

    def apply_cpu_mask(self):
        # msg("assigning IRQ %d to CPU %d" % (self.id, self.current_cpu))
        with open(os.path.join(IRQ_DIRECTORY, str(self.id),
                               "smp_affinity_list"), "w") as affinity_file:
            affinity_file.write(str(self.current_cpu))

    def next_cpu(self, cpu=None):
        self.current_cpu = AffinityEntity.next_cpu(self,
                                                   self.current_cpu
                                                   if cpu is None else cpu)
        if self.current_cpu == -1:
            self.current_cpu = self.first_cpu()
        self.apply_cpu_mask()


class IRQSprinkler:
    def __init__(self, _rules):
        # msg(rules)
        self.irqs = [IRQ(irq_id, cpu_mask) for irq_ids, cpu_mask in _rules
                     for irq_id in irq_ids]

    # msg(str(len(self.irqs)))
    #         for irq in self.irqs:
    #             msg("irq_id: %d cpu_mask: %x" % (irq.id, irq.cpu_mask))

    def move_next(self):
        for irq in self.irqs:
            irq.next_cpu()


def get_irq_numbers(_irq_prefix):
    # get interrupt number from name
    with open(IRQ_FILENAME, "r") as irq_file:
        for line in irq_file:
            if _irq_prefix not in line:
                continue
            yield line.split(":", 1)[0].strip()


def parse_user_list(user_list):
    for elements in user_list.split(","):
        elem = re.match(r"^(\d+)$", elements)
        if elem is not None:
            yield int(elem.group(0))
            continue
        start, end, step = \
            re.match(r"^(\d+)\-(\d+):?(\d+)?$", elements).groups()
        if step is None:
            step = 1
        for elem in xrange(int(start), int(end) + 1, int(step)):
            yield elem


def parse_cpu_mask(_cpu_list):
    _cpu_mask = 0
    for cpu in parse_user_list(_cpu_list):
        _cpu_mask += (1 << cpu)
    return _cpu_mask


def parse_irq_numbers(numbers_list):
    return parse_user_list(numbers_list)


class IRQDaemon(Daemon):
    pid_file = "/tmp/irq_sprinkler_pid.txt"

    def __init__(self, _rules, _interval):
        Daemon.__init__(self, IRQDaemon.pid_file)
        self.rules = _rules
        self.interval = _interval

    def run(self, once=False):
        if not self.rules:
            usage(sys.argv[0], "Error: no rules specified")
        for idx, (irq_ids, cpumask) in enumerate(self.rules):
            if (cpumask is None) or (irq_ids is None):
                usage(sys.argv[0],
                      "Error: cpumask: %s, irq_ids: %s" % (cpumask, irq_ids))

            msg("Rule %d:" % (idx,))
            msg("Interrupt numbers: %s" % (str([irq_id for irq_id in
                                                irq_ids]),))
            msg("Hex interrupt cores mask: %x" % (cpumask, ))

        msg("IRQ switch interval: %f" % (self.interval, ))
        sprinkler = IRQSprinkler(self.rules)

        # if we are on the "once" mode of operation then run once and exit
        if once:
            sprinkler.move_next()
            return

        while True:
            sleep(self.interval)
            # msg("***** step *****")
            sprinkler.move_next()


def usage(program_name, error):
    print(error)
    print('')
    print('%s [OPTIONS]' % (program_name, ))
    print("A simple IRQ balancer. The program has two modes of configuration "
          "trough the command line. Specifying rules and mode of operation. or "
          "trough a json configuration file.")
    print('')
    print('OPTIONS:')
    print('-h/--help: print help')
    print('-r/--rule "<irq prefix> <cpu_list>": an IRQ rule')
    print('-t/--interval <seconds>: the interval in which the daemon works, '
          'default is 0.1.')
    print('-d/--daemon <start/restart/stop/once>: set the mode of operation, '
          'when unspecified the balancer run in the foreground.')

    print('-c/--config <configuration file>: set the configuration file. all '
          'other command line configurations are ignored.')
    print('')
    print('Command line examples:')
    print('%s -r "eth2 0-6:2" -r "eth1 2,3"' % (program_name, ))
    print('%s -r "eth2 0" -d restart -t 0.1' % (program_name, ))
    print('%s -d stop' % (program_name, ))
    print('%s -c conf.json' % (program_name, ))
    print('')
    print('Configuration file example:')
    print('{\n'''
          '\t"daemon":"restart",\n'
          '\t"rules":[\n'
          '\t\t{\n'
          '\t\t\t"irq_prefix": "eth1",\n'
          '\t\t\t"cpu_list": "0"\n'
          '\t\t},\n'
          '\t\t{\n'
          '\t\t\t"irq_prefix": "eth2",\n'
          '\t\t\t"cpu_list": "1-7"\n'
          '\t\t}\n'
          '\t]\n'
          '}')
    sys.exit(0)


def parse_rule(_irq_prefix, _cpu_list):
    msg("irq_prefix: %s" % (_irq_prefix, ))
    irq_ids = [irq_id for irq_id in get_irq_numbers(_irq_prefix)]
    msg("cpu_list: %s" % (_cpu_list, ))
    cpu_mask = parse_cpu_mask(_cpu_list)
    return irq_ids, cpu_mask

if __name__ == '__main__':
    daemon_command = None
    interval = 0.1

    # msg("Number of arguments: %d arguments." % (len(sys.argv),))
    #     msg("Argument List: %s" % (str(sys.argv), ))
    opts = None
    try:
        opts, args = getopt.getopt(sys.argv[1:], "r:d:c:t:h",
                                   ["rule=", "daemon=", "config=", "interval="])
    except getopt.GetoptError:
        msg("Error")
        usage(sys.argv[0], "Illegal arguments!")

    rules = []

    for opt, arg in opts:
        if opt == '-h':
            usage(sys.argv[0], "Help")
        elif opt in ("-r", "--rule"):
            irq_prefix, cpu_list = arg.split()
            rules.append(parse_rule(irq_prefix, cpu_list))
        elif opt in ("-d", "--daemon"):
            msg("daemon: %s" % (arg, ))
            daemon_command = arg
        elif opt in ("-t", "--interval"):
            msg("interval: %s" % (arg, ))
            interval = float(arg)
        elif opt in ("-c", "--config"):
            msg("JSON configuration file: %s" % (arg, ))

            conf = None
            # try:
            with open(arg, "r") as f:
                conf = json.load(f)
            # except:
            #     usage(sys.argv[0], "The configuration file is not valid.")

            rules = [parse_rule(r["irq_prefix"], r["cpu_list"]) for
                     r in conf["rules"]]
            if "daemon" in conf:
                daemon_command = conf["daemon"]
            if "interval" in conf:
                interval = float(conf["interval"])

            break

    daemon = IRQDaemon(rules, interval)
    if daemon_command:
        if 'start' == daemon_command:
            daemon.start()
        elif 'stop' == daemon_command:
            daemon.stop()
        elif 'restart' == daemon_command:
            daemon.restart()
        elif 'once' == daemon_command:
            daemon.run(once=True)
        else:
            usage(sys.argv[0], "Unknown daemon command")
    else:
        daemon.run()
