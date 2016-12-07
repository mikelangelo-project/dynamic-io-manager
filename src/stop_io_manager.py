#!/usr/bin/python
import os
from utils.aux import msg, err, __live_execute

__author__ = 'yossiku'


def main(argv):
    euid = os.geteuid()
    if euid != 0:
        print("Script did not started as root, running sudo..")
        args = ['sudo', sys.executable] + argv + [os.environ]
        # the next row replaces the currently-running process with the sudo
        os.execlpe('sudo', *args)

        scripts_path = os.path.dirname(os.path.abspath(__file__))

        out = __live_execute([os.path.join(scripts_path, 'io_manager.py'),
                               "-k"])

# ------------------
# Entry point
# -----------------
if __name__ == '__main__':
    import sys
    main(sys.argv)
