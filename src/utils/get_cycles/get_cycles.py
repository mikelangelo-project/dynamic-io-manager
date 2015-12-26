import ctypes
import os
import subprocess
import time
import logging


def usage(program_name, error):
    print("%s [<count>]" % (program_name, ))
    print(error)


class Cycles:
    _LIBRARY_PATH = 'librdtsc.so'
    _RDTSCLIB = None

    cycles_per_second = None
    resolution = None

    @staticmethod
    def initialize():
        """
        initialize the get cycles class if one is not running yet.

        :return True if the class was initialized successfully,
        False otherwise
        Note; returns false if the class is already initialized)
        """
        if Cycles._RDTSCLIB is not None:
            return False

        lib_path = Cycles._LIBRARY_PATH

        # Compile the library
        subprocess.call(['make', '-C', lib_path])

        # Load the library
        if not os.path.exists(lib_path):
            lib_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                    lib_path)

        if not os.path.exists(lib_path):
            logging.error("Error: couldn't locate %s, searched locations: %s" %
                          (Cycles._LIBRARY_PATH, lib_path))
            raise IOError

        print("found library at " + lib_path)
        Cycles._RDTSCLIB = ctypes.CDLL(lib_path)
        Cycles._RDTSCLIB.get_cycles.argtypes = []
        Cycles._RDTSCLIB.get_cycles.restype = ctypes.c_ulonglong

        avg, min, max = Cycles.get_resolution()
        logging.info("Resolution: Average: %lu, Min: %lu, Max: %lu" %
                     (avg, min, max))
        Cycles.resolution = avg

        avg, min, max = Cycles.get_cycles_per_second()
        logging.info("Cycles/Sec: Average: %lu, Min: %lu, Max: %lu" %
                     (avg, min, max))
        Cycles.cycles_per_second = avg
        return True

    def __init__(self):
        self.cycles_per_second = self.get_cycles_per_second()
        self.resolution, _, _ = self.get_resolution()

    @staticmethod
    def get_cycles():
        return Cycles._RDTSCLIB.get_cycles()

    @staticmethod
    def delay(cycles):
        start = Cycles.get_cycles()
        while Cycles.get_cycles() - start < cycles:
            continue
        return

    @staticmethod
    def get_resolution(count=1000):
        # TODO: add confidence interval
        diffs = [0 - Cycles.get_cycles() + Cycles.get_cycles()
                 for _ in xrange(count)]

        # avg, min, max
        return sum(diffs, 0) / len(diffs), min(diffs), max(diffs)

    @staticmethod
    def get_cycles_per_second(interval=0.01, count=100):
        diffs = []
        for _ in xrange(count):
            start = Cycles.get_cycles()
            time.sleep(interval)
            end = Cycles.get_cycles()
            diffs.append(end - start)
        # avg, min, max
        return sum(diffs, 0) / (len(diffs) * interval), \
            min(diffs) * interval, max(diffs) * interval


def main(argv):
    count = 1000
    if len(argv) > 1:
        count = int(argv[1])

    Cycles.initialize()

    avg, min, max = \
        Cycles.get_resolution(count)
    print("Resolution: Average: %lu, Min: %lu, Max: %lu" % (avg, min, max))

    avg, min, max = \
        Cycles.get_cycles_per_second(count)
    print("Cycles/Sec: Average: %lu, Min: %lu, Max: %lu" % (avg, min, max))

if __name__ == '__main__':
    import sys
    main(sys.argv)
