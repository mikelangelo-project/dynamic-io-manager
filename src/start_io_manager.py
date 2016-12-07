#!/usr/bin/python
import json
import os
import getopt
import subprocess
from utils.aux import msg, err, __live_execute

__author__ = 'yossiku'

def usage(program_name, error):
    print('Error: %s' % (str(error), ))
    print('USAGE: %s [OPTIONS]' % (program_name,))
    print('')
    print('OPTIONS:')
    print('-c/--config=<configuration file>')
    print('-p/--process: run as a process and direct all output to '
          'stdout+stderr.')
    sys.exit(0)


def main(argv):
    euid = os.geteuid()
    if euid != 0:
        print("Script did not started as root, running sudo..")
        args = ['sudo', sys.executable] + argv + [os.environ]
        # the next row replaces the currently-running process with the sudo
        os.execlpe('sudo', *args)

    opts = None
    try:
        opts, args = getopt.getopt(argv[1:], "c:hp",
                                   ["config=", "process", "help"])
    except getopt.GetoptError:
        usage(argv[0], "Illegal Argument!")

    config_filename = "/tmp/io_manager_configuration.json"
    daemon = ""
    for opt, arg in opts:
        if opt in ("-h", "--help"):
            usage(argv[0], "Help")
        elif opt in ("-c", "--config"):
            config_filename = arg
        elif opt in ("-p", "--process"):
            daemon = "-p"

    msg("configuration file: %s" % config_filename)
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
                          daemon])

# ------------------
# Entry point
# -----------------
if __name__ == '__main__':
    import sys
    main(sys.argv)
