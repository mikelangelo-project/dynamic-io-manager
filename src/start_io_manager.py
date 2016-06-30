#!/usr/bin/python
import json
import os
import subprocess
from utils.aux import msg, err, __live_execute

__author__ = 'yossiku'

def usage(program_name, error):
    print("%s <configuration_filename>" % (program_name, ))
    sys.exit(0)


def main(argv):
    euid = os.geteuid()
    if euid != 0:
        print("Script did not started as root, running sudo..")
        args = ['sudo', sys.executable] + argv + [os.environ]
        # the next row replaces the currently-running process with the sudo
        os.execlpe('sudo', *args)

    # parse command line options
    if len(argv) < 1:
        usage(argv[0], "Not enough arguments!")

    config_filename = os.path.expanduser(sys.argv[1])
    if not os.path.exists(config_filename):
        usage(argv[0], "configuration file %s not found " %
              (config_filename,))

    with open(config_filename, "r") as f:
        conf = json.load(f)

    scripts_path = os.path.dirname(os.path.abspath(__file__))
    interval = conf["interval"]

    out = __live_execute([os.path.join(scripts_path, 'reconfigure.py'),
                           config_filename,
                           "-p", "interval:%s" % interval])
    out = __live_execute([os.path.join(scripts_path, 'io_manager.py'),
                           "-s", config_filename,
                           "-p"])

# ------------------
# Entry point
# -----------------
if __name__ == '__main__':
    import sys
    main(sys.argv)
