#!/usr/bin/python

import re


class CPU:
    processorPattern = re.compile('\s*processor\s*:\s*(\d+)\s*')
    socketPattern = re.compile('\s*physical\s+id\s*:\s*(\d+)\s*')

    def __init__(self, cpu_id, socket):
        self.id = cpu_id
        self.socket = socket

    @staticmethod
    def parse_cpus():
        ids = []
        sockets = []
        with open("/proc/cpuinfo") as f:
            for line in f:
                match = CPU.processorPattern.match(line)
                if match:
                    value = match.group(1)
                    ids.append(int(value))
                    continue
                match = CPU.socketPattern.match(line)
                if match:
                    value = match.group(1)
                    sockets.append(int(value))
                    continue

        cpus = {}
        for i, cpu_id in enumerate(ids):
            cpus[cpu_id] = CPU(cpu_id, sockets[i])
        return cpus
    
    def __str__(self):
        return "id: %d, socket: %d" % (self.id, self.socket)

    def __repr__(self):
        return "%s(%s)" % (self.__class__, self.__str__())