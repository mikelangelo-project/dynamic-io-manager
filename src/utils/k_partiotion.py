__author__ = 'eyalmo'


class Permutation:
    # TODO: add dummy load with 0 that cannot be removed or added
    def __init__(self, loads):
        self.loads = loads
        self.sum = sum((load for _, load in loads), start=0)

    def min(self):
        l1_id, load1 = self.loads[-1]
        return l1_id, load1, self.sum - load1

    def max(self):
        l1_id, load1 = self.loads[0]
        return l1_id, load1, self.sum - load1

    @staticmethod
    def get_best_swap(perm1, perm2, average):
        def swap_value(load1, load2):
            return abs(perm1.sum - load1 + load2 - average) + \
                abs(perm2.sum - load2 + load1 - average) - \
                abs(perm1.sum - average) - \
                abs(perm2.sum - average)
        best_id1, best_id2, best_value = perm1[0][0], perm2[-1][0], \
            swap_value(perm1[1][1], perm2[1][1])
        for l1_id, l1 in perm1.items():
            for l2_id, l2 in perm2.items():
                sv = swap_value(l1, l2)
                if best_value < sv:
                    best_id1, best_id2, best_value = l1_id, l2_id, sv
        return best_id1, best_id2, best_value

    def add(self, l_id, load):
        self.loads[l_id] = load
        self.sum += load

    def remove(self, l_id):
        self.sum -= self.loads[l_id]
        del self.loads[l_id]

    def get_load(self, l_id):
        return self.loads[l_id]


def distribute_equally(permutations, average=None):
    if not average:
        average = sum(p.sum for p in permutations) / len(permutations)

    permutations = sorted(permutations, key=lambda x: x.sum)
    high = permutations[0].sum
    low = permutations[-1].sum

    best_value = 1
    while best_value > 0:
        best_p1, best_id1, best_p2, best_id2 = None, None, None, None
        best_value = 0

        for high_p in permutations:
            if high_p.sum != high:
                break
            for low_p in reversed(permutations):
                if low_p.sum != low:
                    break

                id1, id2, value = Permutation.get_best_swap(high_p, low_p,
                                                            average)
                if value > best_value:
                    best_p1, best_id1, best_p2,  = high_p, id1, low_p
                    best_id2, best_value = id2, value
        best_p1.add(id2, best_p2.get_load(best_id2))
        best_p2.add(id1, best_p1.get_load(best_id1))

        best_p1.remove(id1)
        best_p2.remove(id2)