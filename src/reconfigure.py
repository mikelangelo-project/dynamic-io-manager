#!/usr/bin/python
import getopt
import json
import sys
import os

import time

from utils.affinity_entity import parse_cpu_mask_from_cpu_list, \
    set_cpu_mask_to_pid
from utils.aux import msg
from utils.vhost import Vhost, vhost_write, vhost_worker_set_cpu_mask, \
    vhost_read


def usage(program_name, error):
    print('Error: %s' % (str(error), ))
    print('USAGE: %s <io manager configuration> OPTIONS' % (program_name, ))
    print('Reconfigures the environment to match configuration')
    print('OPTIONS:')
    print('-p/--param "<parameter name>:<value>"')
    print('EXAMPLE: %s io_manager_configuration.json -p '
          '\"vm_core_addition_policy.add_ratio:0.45\" -p '
          '\"vm_core_addition_policy.can_remove_ratio:1.0\"' %
          (program_name, ))
    sys.exit()


def vhost_worker_create():
    workers_global = Vhost.INSTANCE.workersGlobal
    vhost_write(workers_global, "create", 0)


def vhost_remove_worker(removed_worker):
    workers_global = Vhost.INSTANCE.workersGlobal
    vhost_write(removed_worker, "locked", 1)
    vhost_write(workers_global, "remove", removed_worker["id"])

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage(sys.argv[0], "Wrong number of arguments, expected 1 got %d" %
              (len(sys.argv) - 1,))

    config_filename = os.path.expanduser(sys.argv[1])
    if not os.path.exists(config_filename):
        usage(sys.argv[0], "configuration file %s not found " %
              (config_filename,))

    # load configuration
    config = None
    with open(config_filename, "r") as f:
        config = json.load(f)

    opts = None
    try:
        opts, args = getopt.getopt(sys.argv[2:], "p:h",
                                   ["param=", "help"])
    except getopt.GetoptError:
        usage(sys.argv[0], "Illegal Argument!")

    configuration_filename = None
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(sys.argv[0], "Help")
        elif opt in ("-p", "--param"):
            msg("parameter: %s" % (arg, ))
            key, value = arg.split(":")
            keys = [k.strip() for k in key.split(".")]

            entry = config
            for key in keys[:-1]:
                entry = entry[key]
            entry[keys[-1]] = value

    # initialize vhost
    Vhost.initialize()
    Vhost.INSTANCE.update(light_update=False, update_epoch=False,
                          rescan_files=True)

    vms_conf = config["vms"]
    workers_conf = sorted(config["workers"],
                          key=lambda _w: int(_w["id"].split(".")[1]))
    # msg([w["id"] for w in workers_conf])
    workers = sorted(Vhost.INSTANCE.workers.values(),
                     key=lambda _w: int(_w["id"].split(".")[1]))
    # msg([w["id"] for w in workers])
    devices = Vhost.INSTANCE.devices
    queues = Vhost.INSTANCE.queues

    # fix vms affinity
    msg("fix vms affinity")
    for vm in vms_conf:
        cpu_mask = parse_cpu_mask_from_cpu_list(vm["cpu"])
        pid = int(vm["pid"])
        msg("vm: id: %s, pid: %d, cpu_mask: %x" % (vm["id"], pid, cpu_mask))
        set_cpu_mask_to_pid(pid, cpu_mask)

    shared_workers = len(workers_conf) > 0
    if shared_workers:
        workers_for_addition = len(workers_conf) - len(workers)
    else:
        workers_for_addition = len(devices) - len(workers)

    # add workers to match the number of workers in the configuration
    if workers_for_addition > 0:
        msg("workers_for_addition: %d" % (workers_for_addition,))
        for _ in xrange(workers_for_addition):
            vhost_worker_create()
        Vhost.INSTANCE.update(light_update=False, update_epoch=False,
                              rescan_files=True)
        workers = sorted(Vhost.INSTANCE.workers.values(),
                         key=lambda _w: int(_w["id"].split(".")[1]))
        msg("we have %d workers now: {%s}" %
            (len(workers), ",".join(w["id"] for w in workers)))

    if shared_workers:
        msg("shared_workers: %s" % (shared_workers,))
        worker_mapping = {worker_conf["id"]: worker["id"]
                          for worker_conf, worker in zip(workers_conf, workers)}
        msg(worker_mapping)

        # fix io workers affinity
        msg("fix io workers affinity")
        for worker_conf in workers_conf:
            cpu_mask = parse_cpu_mask_from_cpu_list(worker_conf["cpu"])
            worker = Vhost.INSTANCE.workers[worker_mapping[worker_conf["id"]]]
            msg("io worker: worker_conf: %s, worker: %s, cpu_mask: %x" %
                (worker_conf["id"], worker["id"], cpu_mask))
            vhost_worker_set_cpu_mask(worker, cpu_mask)

        # move devices to the correct workers and fix workers affinity
        msg("move devices to the correct workers and fix workers affinity")
        for vm in vms_conf:
            for dev in vm["devices"]:
                # move devices to the correct workers
                if dev["vhost_worker"] != worker_mapping[dev["vhost_worker"]]:
                    dev["vhost_worker"] = worker_mapping[dev["vhost_worker"]]

                # msg(dev["vhost_worker"])
                vhost_write(devices[dev["id"]], "worker", dev["vhost_worker"])

        # update the configuration file
        for worker in config["workers"]:
            worker["id"] = worker_mapping[worker["id"]]

        # start polling
        msg("start polling")
        for q in queues.values():
            can_poll = vhost_read(q, "can_poll")
            if can_poll == "0":
                continue
            vhost_write(q, "poll", "1")

        workers_for_removal = len(workers) - len(workers_conf)
        msg(workers_for_removal)
    else:
        msg("shared_workers: %s" % (shared_workers,))
        msg("move devices to the correct workers:")
        # move devices to the correct workers
        i = 0
        for vm in vms_conf:
            cpu_mask = parse_cpu_mask_from_cpu_list(vm["cpu"])
            msg("vm: %s, cpu:%s, cpu_mask:0x%x" %
                (vm["id"], vm["cpu"], cpu_mask))
            for dev in vm["devices"]:
                msg("dev: %s, old worker: %s, new worker: %s" %
                    (dev["id"], dev["vhost_worker"], workers[i]["id"]))

                dev["vhost_worker"] = workers[i]["id"]
                for _ in xrange(10):
                    try:
                        vhost_write(devices[dev["id"]], "worker",
                                    dev["vhost_worker"])
                    except IOError:
                        msg("device still in transfer waiting 1 second.")
                        time.sleep(1)

                # fix affinity
                msg("io worker: worker: %s, cpu_mask: 0x"
                    "%x" %
                    (workers[i]["id"], cpu_mask))
                vhost_worker_set_cpu_mask(workers[i], cpu_mask)

                i += 1

        # stop polling
        msg("stop polling")
        for q in queues.values():
            can_poll = vhost_read(q, "can_poll")
            if can_poll == "0":
                continue
            vhost_write(q, "poll", "0")

        workers_for_removal = len(workers) - len(devices)

    # remove workers to match the number of workers in the configuration
    if workers_for_removal > 0:
        # msg([w["id"] for w in workers[len(workers_conf):]])
        for worker in workers[-workers_for_removal:]:
            # msg(worker["id"])
            vhost_remove_worker(worker)

    # save configuration
    with open(config_filename, "w+") as f:
        json.dump(config, f, indent=2)
