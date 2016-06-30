#!/usr/bin/python

from inspect import currentframe, getframeinfo
import os
import stat
import re
import logging
import sys
from subprocess import Popen, PIPE, STDOUT
from os import popen

from utils.get_cycles.get_cycles import Cycles

class bcolors:
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    DARKCYAN = '\033[36m'
    BLUE = '\033[34m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    WARNING = YELLOW
    FAIL = RED
    INFO = BLUE
    ENDC = '\033[0m'


def syscmd(s):
    res = ''.join(popen(s).readlines()).strip()
#     msg("%s -> %s" % (s, res))
    return res

def __live_execute(cmd):
    cmd = " ".join(cmd)
    info(cmd)
    p = Popen(cmd, bufsize=-1, stdin=PIPE, stdout=PIPE, shell=True)
    for line in iter(p.stdout.readline, ''):
         print line.rstrip('\n')
    if p.wait() != 0:
        if p.stderr:
            warn(p.stderr, step_back=2)
        err(cmd + " failed!", step_back=2)
    return p.stdout


# prints a message to stdout + stderr, adds the source file + line number.
# use this instead of echo
def msg(s, step_back=1, end_of_line="\n"):
    frame = currentframe()
    for _ in xrange(step_back):
        frame = frame.f_back
    frame_info = getframeinfo(frame)
    f = os.path.basename(frame_info.filename)
    l = frame_info.lineno
    sys.stdout.write("[" + bcolors.BLUE + "%s:%d" % (f, l) + bcolors.ENDC + "] %s" % (s,) + end_of_line)
    # Flushes the output buffer to achieve real time traces
    sys.stdout.flush()


# prints an info message to stdout + stderr
def info(s, step_back=1):
    msg(bcolors.INFO + "info: %s" % (s, ) + bcolors.ENDC, step_back+1)


# prints a warning message to stdout + stderr
def warn(s, step_back=1):
    msg(bcolors.WARNING + "warning: " + bcolors.ENDC + "%s" % (s, ), step_back+1)


# print an error message to stdout + stderr and exit
def err(s, step_back=1):
    msg(bcolors.FAIL + "error: " + bcolors.ENDC + "%s" % (s, ), step_back+1)
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

    res = filter(lambda _f: _f not in ["power", "subsystem", "uevent"], res)
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
        self.checkpoints = [(Cycles.get_cycles(), "START")]

    @staticmethod
    def check_resolution():
        timer = Timer("Timer resolution check")
        timer.checkpoint("check point")
        timer.done()

    def checkpoint(self, text):
        now = Cycles.get_cycles()
        self.checkpoints.append((now, text))

    def done(self):
        now = Cycles.get_cycles()
        self.checkpoints.append((now, "DONE"))
        start = prev = self.checkpoints[0][0]
        output = "\n"
        for cp in self.checkpoints:
            output += "%s(%d, %d): %s\n" % \
                      (self._tag, cp[0] - start, cp[0] - prev, cp[1])
            prev = cp[0]
        logging.info(output)


class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message != '\n':
            logging.log(self.level, message)

    def flush(self):
        self.level(sys.stderr)
