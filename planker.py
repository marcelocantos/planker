#!/usr/bin/env python3
"""Planker CLI

Reads a JSON file with two arrays:
- `available`: list of available plank lengths (numbers)
- `desired`: list of desired plank lengths (numbers)

Allocates planks using a best-fit greedy cutter by default.
"""

import json
import sys
from typing import List, Dict, Any


def allocate_greedy(pieces: List[int], cuts: List[int]):
    kerf = 3

    allocated = [[] for _ in range(len(pieces))]
    unallocated = []

    leftover = [x + kerf for x in pieces]
    for want in cuts:
        want += kerf
        candidates = {(p, i) for i, p in enumerate(leftover) if p >= want}
        if candidates:
            _, best_i = min(candidates)
            allocated[best_i].append(want - kerf)
            leftover[best_i] -= want
        else:
            unallocated.append(want)

    return allocated, unallocated, leftover


def main():
    data = json.load(sys.stdin)

    available = sum(([x] * n for n, x in data["available"]), [])
    desired = sorted(sum(([x] * n for n, x in data["desired"]), []), reverse=True)

    # print(available)
    # print(desired)
    allocated, unallocated, leftover = allocate_greedy(available, desired)
    print("unallocated:", unallocated, file=sys.stderr)
    print("allocated\tleftover\tcuts")
    for i, alloc in enumerate(allocated):
        print("\t".join(map(str, [available[i], leftover[i]] + list(map(str, alloc)))))

if __name__ == "__main__":
    main()
