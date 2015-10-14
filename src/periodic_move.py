#!/usr/bin/python
import sys
import time

from utils.vhost import Vhost, vhost_write

__author__ = 'eyalmo'


def usage(program_name, error):
    print('Error: %s' % (str(error), ))
    print('USAGE: %s <dev id> <worker 1> <worker 2> <move interval>' %
          (program_name, ))
    print('Moves device between two workers every interval')
    sys.exit()


if __name__ == '__main__':
    if len(sys.argv) != 5:
        usage(sys.argv[0], "Wrong number of arguments, expected 4 got %d" %
              (len(sys.argv) - 1,))

    # initialize vhost
    Vhost.initialize()
    Vhost.INSTANCE.update(False)

    workers = Vhost.INSTANCE.workers
    devices = Vhost.INSTANCE.devices

    if sys.argv[1] not in devices:
        usage(sys.argv[0], "device %s not found!" % (sys.argv[1],))
    dev = devices[sys.argv[1]]

    if sys.argv[2] not in workers:
        usage(sys.argv[0], "worker %s not found!" % (sys.argv[2],))
    worker_1 = workers[sys.argv[2]]

    if sys.argv[3] not in workers:
        usage(sys.argv[0], "worker %s not found!" % (sys.argv[3],))
    worker_2 = workers[sys.argv[3]]

    try:
        interval = float(sys.argv[4])
    except IOError:
        usage(sys.argv[0], "%s is not a number!" % (sys.argv[4],))

    while True:
        vhost_write(dev, "worker", worker_1["id"])
        time.sleep(interval)
        vhost_write(dev, "worker", worker_2["id"])
        time.sleep(interval)