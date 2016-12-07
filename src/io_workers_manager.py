import logging

from utils.vhost import Vhost, vhost_write, vhost_read, \
    vhost_worker_set_cpu_mask, get_cpu_usage
from utils.io_worker import IOWorker
from utils.aux import Timer

__author__ = 'eyalmo'


class IOWorkersManager:
    def __init__(self, devices, vm_manager, backing_devices_manager,
                 io_workers_info, iocores_restrictions,
                 vq_classifier, poll_policy, throughput_policy, latency_policy,
                 io_core_policy=None, balance_policy=None, regret_policy=None):
        self.io_workers = [IOWorker(w_info) for w_info in io_workers_info]
        self.backing_devices_manager = backing_devices_manager

        self.vq_classifier = vq_classifier
        self.poll_policy = poll_policy
        self.throughput_policy = throughput_policy
        self.latency_policy = latency_policy

        self.io_core_policy = io_core_policy
        self.balance_policy = balance_policy
        self.regret_policy = regret_policy

        self.min_iocores = iocores_restrictions["min"]
        self.max_iocores = iocores_restrictions["max"]
        logging.info("iocores restrictions - min: {0}, max: {1}".format(self.min_iocores, self.max_iocores))

        self.devices = devices

        self.vm_manager = vm_manager

    def initialize(self):
        logging.info("\x1b[37mIOWorkersManager initialize\x1b[39m")
        shared_workers = len(self.io_workers) > 0

        self.vq_classifier.initialize()
        self.poll_policy.initialize(shared_workers)
        self.throughput_policy.initialize()
        self.latency_policy.initialize()
        self.backing_devices_manager.initialize(self.io_workers,
                                                self.vm_manager)
        self.regret_policy.initialize()

    def _add_io_core(self):
        logging.info("\x1b[33madd a new IOcore\x1b[39m")
        cpu_id = self.vm_manager.remove_cores(number=1)[0]
        logging.info("\x1b[33mcpu id: %d\x1b[39m" % (cpu_id,))
        self.io_core_policy.add(cpu_id)
        new_worker_id = self._add_io_worker(cpu_id)
        self.io_workers.append(IOWorker({"id": new_worker_id, "cpu": cpu_id}))
        logging.info("Added Worker: {id: %s, cpu: %d}" %
                     (new_worker_id, cpu_id))
        balance_changes = \
            self.balance_policy.balance_after_addition(self.io_workers,
                                                       [new_worker_id])
        self.move_devices(balance_changes, balance_backing_device=True)

    def _remove_io_core(self):
        logging.info("\x1b[33mremove an IO core\x1b[39m")
        # remove an IO core
        cpu_id = self.io_core_policy.remove(number=1)[0]
        removed_worker = [w for w in Vhost.INSTANCE.workers.values()
                          if w["cpu"] == cpu_id][0]
        removed_worker_id = removed_worker["id"]

        balance_changes = \
            self.balance_policy.balance_before_removal(self.io_workers,
                                                       removed_worker_id)

        self.io_workers = [w for w in self.io_workers
                           if w.id != removed_worker_id]
        self.move_devices(balance_changes, balance_backing_device=True)
        self._remove_io_worker(removed_worker)
        logging.info("Removed Worker: {id: %s, cpu: %d}" %
                     (removed_worker["id"], cpu_id))

        self.vm_manager.add_core(cpu_id)

    def update_io_core_number(self, iteration=0):
        shared_workers = len(self.io_workers) > 0

        self.throughput_policy.calculate_load(shared_workers)
        self.regret_policy.update()

        self.throughput_policy.update_history()
        self.vm_manager.vm_core_addition_policy.update_history()

        # if len(self.io_workers) == 1:
        #    return False

        if not shared_workers:
            should_start, suggested_io_cores = \
                self.throughput_policy.should_start_shared_worker()

            if self.min_iocores > 0:
                should_start = True
                suggested_io_cores = self.min_iocores

            if suggested_io_cores > self.max_iocores:
                suggested_io_cores = self.max_iocores

            if self.min_iocores == 0 and \
                    (not should_start or not self.regret_policy.can_do_move("start_shared_worker")):
                return False
            logging.info("round %d" % (iteration,))
            logging.info("\x1b[33menable shared IO workers.\x1b[39m")
            logging.info("\x1b[33madd a new IOcore\x1b[39m")

            cpu_ids = self.vm_manager.remove_cores(number=suggested_io_cores)
            for cpu_id in cpu_ids:
                self.io_core_policy.add(cpu_id)
            self.enable_shared_workers(cpu_ids)
            return True
            # if suggested_io_cores > 1 or \
            #         self.regret_policy.is_move_good("start_shared_worker"):
            #     return True
            #
            # cpu_id = self.io_core_policy.remove()[0]
            # self.vm_manager.add_core(cpu_id)
            # self.disable_shared_workers()
            # return False

        if self.throughput_policy.should_stop_shared_worker() and \
                        self.min_iocores == 0:
            if not self.regret_policy.can_do_move("stop_shared_worker"):
                return False
            logging.info("round %d" % (iteration,))
            logging.info("\x1b[33mdisable shared IO workers.\x1b[39m")
            logging.info("\x1b[33mremove IOcore\x1b[39m")
            # remove the IO core
            cpu_id = self.io_core_policy.remove()[0]
            self.vm_manager.add_core(cpu_id)
            self.disable_shared_workers()

            # if self.regret_policy.is_move_good("stop_shared_worker"):
            #     return True
            #
            # cpu_ids = self.vm_manager.remove_cores(number=1)
            # for cpu_id in cpu_ids:
            #     self.io_core_policy.add(cpu_id)
            # self.enable_shared_workers(cpu_ids)
            # return False
            return True

        add_io_core, can_remove_io_core = \
            self.throughput_policy.should_update_core_number()
        remove_io_core, can_add_io_core = \
            self.vm_manager.should_update_core_number()
        batching_remove_io_core = \
            self.throughput_policy.batching_should_reduce_core_number()

        if self.throughput_policy.ratio > 1.3:
            remove_io_core = True

        if self.min_iocores > len(self.io_workers):
            add_io_core = can_add_io_core = True

        if self.min_iocores >= len(self.io_workers):
            remove_io_core = can_remove_io_core = False

        if self.max_iocores == len(self.io_workers):
            add_io_core = can_add_io_core = False

        if batching_remove_io_core and \
                self.regret_policy.can_do_move("batching_remove_io_core"):
            self._remove_io_core()
            if self.regret_policy.is_move_good("batching_remove_io_core"):
                return True
            self._add_io_core()
            return False

        if add_io_core and can_add_io_core and \
                self.regret_policy.can_do_move("add_io_core"):
            logging.info("round %d" % (iteration,))
            self.throughput_policy.print_load()
            self.vm_manager.vm_core_addition_policy.print_load()
            self._add_io_core()
            if self.regret_policy.is_move_good("add_io_core"):
                return True
            self._remove_io_core()
            return False

        if not remove_io_core or not can_remove_io_core or \
                not self.regret_policy.can_do_move("remove_io_core"):
            # we don't want or can't remove an IO core
            return False

        logging.info("round %d" % (iteration,))
        self.throughput_policy.print_load()
        self.vm_manager.vm_core_addition_policy.print_load()
        self._remove_io_core()
        if self.regret_policy.is_move_good("remove_io_core"):
            return True
        self._add_io_core()
        return False

    def update_balance(self):
        if not self.regret_policy.can_do_move("update_balance"):
            return False

        balance_changes = self.balance_policy.balance()
        if not balance_changes:
            return
        self.move_devices(balance_changes)
        if not self.regret_policy.is_move_good("update_balance"):
            revert_balance_changes = {}
            for dev_id, (old_worker, new_worker) in balance_changes.items():
                revert_balance_changes[dev_id] = (new_worker, old_worker)

    def update_polling(self):
        if not self.regret_policy.can_do_move("update_polling"):
            return False

        self.poll_policy.update_polling()

    def update_vq_classifications(self):
        can_update = self.regret_policy.can_do_move("update_vq_classifications")
        self.vq_classifier.update_classifications(can_update)

    def move_devices(self, balance_changes, balance_backing_device=True):
        # timer = Timer("Timer move_devices")
        # logging.info("\x1b[37mMoving devices:\x1b[39m")
        if not balance_changes:
            # logging.info("no balance changes")
            return

        for dev_id, (old_worker, new_worker) in balance_changes.items():
            # logging.info("\x1b[37mdev: %s from worker: %s to worker: %s"
            #              "\x1b[39m\n" %
            #              (dev_id, old_worker["id"], new_worker["id"]))
            # timer.checkpoint("dev %s" % (dev_id,))
            vhost_write(Vhost.INSTANCE.devices[dev_id], "worker",
                        new_worker["id"])
            # timer.checkpoint("dev %s vhost_write" % (dev_id,))
            Vhost.INSTANCE.devices[dev_id]["worker"] = new_worker["id"]

            new_worker["dev_list"].append(dev_id)
            old_worker["dev_list"].remove(dev_id)
            # timer.checkpoint("dev %s end" % (dev_id,))

        # timer.checkpoint("before backing_devices_manager.balance")
        if balance_backing_device:
            self.backing_devices_manager.balance(self.io_workers)
            self.backing_devices_manager.update()
        # timer.done()

    def enable_shared_workers(self, io_cores):
        vhost = Vhost.INSTANCE
        worker_ids = \
            sorted(vhost.workers.keys(),
                   key=lambda w_id: int(w_id.split(".")[1]))[:len(io_cores)]

        # initialize the io workers
        logging.info("initialize the io workers")
        self.io_workers = []
        for worker_id, io_core in zip(worker_ids, io_cores):
            self.io_workers.append(IOWorker({"id": worker_id, "cpu": io_core}))
            vhost_worker_set_cpu_mask(vhost.workers[worker_id], 1 << io_core)
            vhost.workers[worker_id]["cpu"] = io_core

        # move all devices to the workers
        logging.info("move all devices to the workers")
        balance_changes = \
            self.balance_policy.balance_after_addition(self.io_workers,
                                                       worker_ids)
        self.move_devices(balance_changes)

        # notify poll policy that we moved to shared worker configuration
        logging.info("notify poll policy that we moved to shared worker "
                     "configuration")
        self.poll_policy.enable_shared_workers()

        # remove all workers except the ones in use
        logging.info("remove all workers except the ones in use")
        for worker in vhost.workers.values():
            if worker["id"] in worker_ids:
                continue
            self._remove_io_worker(worker)
        vhost.vhost_light.update(rescan=True)

        self.backing_devices_manager.balance(self.io_workers)
        self.backing_devices_manager.update()

    def disable_shared_workers(self):
        self.poll_policy.disable_shared_workers()
        self.io_workers = []
        vhost = Vhost.INSTANCE
        # create a worker for each device
        for dev in self.devices[1:]:
            worker_id = self._add_io_worker()
            vhost_write(vhost.devices[dev.id], "worker", worker_id)
            vhost_worker_set_cpu_mask(vhost.workers[worker_id], 0xFF)
        vhost.vhost_light.update(rescan=True)

        self.backing_devices_manager.balance(self.io_workers)
        self.backing_devices_manager.update()

    @staticmethod
    def _add_io_worker(new_io_core=0):
        # add a new worker to the I/O cores
        vhost = Vhost.INSTANCE

        vhost_write(vhost.workersGlobal, "create", new_io_core)
        new_worker_id = vhost_read(vhost.workersGlobal, "create").strip()
        vhost.update_all_entries_with_id(new_worker_id)
        vhost.workers[new_worker_id]["cpu_usage_counter"] = \
            get_cpu_usage(vhost.workers[new_worker_id]["pid"])
        # vhost.workers[new_worker_id]["cpu_usage_counter"] = \
        #     ProcessCPUUsageCounter(new_worker_id)
        vhost_worker_set_cpu_mask(vhost.workers[new_worker_id],
                                  1 << new_io_core)
        # logging.info("Added Worker: {id: %s, cpu: %d}" % (new_worker_id,
        #                                                   new_io_core))
        vhost.vhost_light.update(rescan=True)
        return new_worker_id

    @staticmethod
    def _remove_io_worker(removed_worker):
        # logging.info("removed_worker: %s" % (removed_worker["id"],))
        # remove the worker from the cores
        vhost = Vhost.INSTANCE
        workers = vhost.workers

        # lock the worker
        vhost_write(removed_worker, "locked", 1)
        removed_worker["locked"] = 1

        # remove the worker from the workers dictionary
        # removed_worker_dev_ids = vhost_read(removed_worker,
        #                                     "dev_list").strip().split("\t")
        # logging.info("removed_worker_dev_ids: %s" % (removed_worker_dev_ids,))
        # assert not removed_worker_dev_ids

        del workers[removed_worker["id"]]
        vhost_write(vhost.workersGlobal, "remove", removed_worker["id"])
        vhost.vhost_light.update(rescan=True)
