import ctypes
import os
import subprocess
import time


class Cycles:
    LIBRARY_PATH = 'librdtsc.so'
    INSTANCE = None

    @staticmethod
    def initialize():
        """
        initialize the get cycles object if one is not running yet.

        :return True if the object was initialized successfully,
        False otherwise
        Note; returns false if the object is already initialized)
        """
        if Cycles.INSTANCE is not None:
            return False
        Cycles.INSTANCE = Cycles()
        return True

    def __init__(self):
        lib_path = Cycles.LIBRARY_PATH

        # Compile the library
        subprocess.call(['make', '-C', lib_path])

        # Load the library
        if not os.path.exists(lib_path):
            lib_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                    lib_path)

        if not os.path.exists(lib_path):
            print("Error: couldn't locate %s, searched locations: %s" %
                  (Cycles.LIBRARY_PATH, lib_path))
            sys.exit(1)

        print("found library at " + lib_path)
        self.rdtsclib = ctypes.CDLL(lib_path)
        self.rdtsclib.get_cycles.argtypes = []
        self.rdtsclib.get_cycles.restype = ctypes.c_ulonglong

        self.cycles_per_second = self.get_cycles_per_second()
        self.resolution, _, _ = self.get_resolution()

    def get_cycles(self):
        return self.rdtsclib.get_cycles()

    def delay(self, cycles):
        start = self.get_cycles()
        while self.get_cycles() - start < cycles:
            continue
        return

    def get_resolution(self, count=1000):
        # TODO: add confidence interval
        diffs = [0 - self.get_cycles() + self.get_cycles()
                 for _ in xrange(count)]

        # avg, min, max
        return sum(diffs, 0) / len(diffs), min(diffs), max(diffs)

    def get_cycles_per_second(self, count=100):
        diffs = []
        for _ in xrange(count):
            start = self.get_cycles()
            time.sleep(0.01)
            end = self.get_cycles()
            diffs.append(end - start)
        # avg, min, max
        return sum(diffs, 0) / (len(diffs) / 100.0), \
            min(diffs) / 100, max(diffs) / 100


def main(argv):
    count = 1000
    if len(argv) > 1:
        count = int(argv[1])

    cycles = Cycles()

    avg, min, max = \
        cycles.get_resolution(count)
    print("Resolution: Average: %lu, Min: %lu, Max: %lu" % (avg, min, max))

    avg, min, max = \
        cycles.get_cycles_per_second(count)
    print("Cycles/Sec: Average: %lu, Min: %lu, Max: %lu" % (avg, min, max))

if __name__ == '__main__':
    import sys
    main(sys.argv)
