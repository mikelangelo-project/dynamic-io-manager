#!/usr/bin/python

from inspect import currentframe, getframeinfo
import os
import stat
import re
import logging
from os import popen

from utils.get_cycles.get_cycles import Cycles


def syscmd(s):
    res = ''.join(popen(s).readlines()).strip()
#     msg("%s -> %s" % (s, res))    
    return res


# prints a message to stdout + stderr, adds the source file + line number.
# use this instead of echo
def msg(s):
    frame_info = getframeinfo(currentframe().f_back)
    f = os.path.basename(frame_info.filename)
    l = frame_info.lineno
    print("[\x1b[33m%s:%d\x1b[39m] %s" % (f, l, s))


# prints a warning message to stdout + stderr
def warn(s):
    msg("warning: %s" % (s, ))


# print an error message to stdout + stderr and exit
def err(s):
    msg("error: %s" % (s, ))
    exit(1)


def print_selected_stuff(prefix, d, selected_keys):
    logging.info("\x1b[35m%ss:\x1b[39m" % (prefix, ))
    for elem_id, item in sorted(d.iteritems()):
        logging.info("\t%s %s" % (prefix, elem_id))
        for key, value in item.iteritems():
            if key not in selected_keys:
                continue            
            logging.info("\t\t%s: %s" % (key, value))


def print_stuff(prefix, d):
    logging.info("\x1b[35m%ss:\x1b[39m" % (prefix, ))
    for elem_id, item in sorted(d.iteritems()):
        logging.info("\t%s %s" % (prefix, elem_id))
        for key, value in item.iteritems():            
            logging.info("\t\t%s: %s" % (key, value))


def print_all(state):
    logging.info("\x1b[35mvhost:\x1b[39m %s" % (state.vhost, ))

    logging.info("\x1b[35mworkers global:\x1b[39m %s" % (state.workersGlobal, ))

    logging.info("\x1b[35mvms:\x1b[39m")
    for pid, vm in state.vms.iteritems():
        logging.info("\t{ vm: %s, cpus: %s}" % (pid, ", ".join(vm)))

    print_stuff("worker", state.workers)
    print_stuff("device", state.devices)
    print_stuff("queue", state.queues)


def is_readable(file_path):
    return bool(os.stat(file_path).st_mode & stat.S_IREAD)


def ls(path, show_dirs=True, show_files=False, show_symlinks=False,
       show_only_readable=False):
    res = []
    if show_dirs:
        res += [f for f in os.walk(os.path.expanduser(path),
                followlinks=False).__iter__().next()[1]]
    if show_files:
        res += [f for f in os.walk(os.path.expanduser(path),
                followlinks=False).__iter__().next()[2]]
    if not show_symlinks:
        res = filter(lambda _f: not os.path.islink(os.path.join(path, _f)), res)
    if show_only_readable:
        res = filter(lambda _f: is_readable(os.path.join(path, _f)), res)
    return res


def spilt_output_into_rows(output):
    return output.split("\n") if isinstance(output, str) else output


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


class Timer:
    def __init__(self, tag):
        Cycles.initialize()

        self._tag = tag
        # self._checkpoint = self._start = \
        #     Cycles.get_cycles()
        # logging.info("%s(0, 0): START" % (self._tag, ))

        self.checkpoints = [(Cycles.get_cycles(), "START")]

    @staticmethod
    def check_resolution():
        timer = Timer("Timer resolution check")
        timer.checkpoint("check point")
        timer.done()

    def checkpoint(self, text):
        now = Cycles.get_cycles()
        self.checkpoints.append((now, text))
        # logging.info("%s(%d, %d): %s" % (self._tag, now - self._start,
        #                                  now - self._checkpoint, text))
        # self._checkpoint = now

    def done(self):
        now = Cycles.get_cycles()
        self.checkpoints.append((now, "DONE"))
        # logging.info("%s(%d, %d): DONE" %
        #              (self._tag, float(now - self._start),
        #               float(now - self._checkpoint)))
        # self._start = self._checkpoint = now

        start = prev = self.checkpoints[0][0]
        for cp in self.checkpoints:
            logging.info("%s(%d, %d): %s" %
                         (self._tag, cp[0] - start, cp[0] - prev, cp[1]))
            prev = cp[0]
