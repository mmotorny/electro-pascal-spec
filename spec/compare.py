"""Compares cases' token lines with tokens captured from TPC.

Usage: python3 spec/compare.py CAPTURED.json [--write]

CAPTURED.json maps case paths (relative to spec/lexer/cases/, or to the repo)
to token lines in the spec's notation, as produced by the dirty room's
capture tool. Prints every case whose `tokens:` line differs, showing where
the two first part. With --write, replaces the cases' token lines with the
captured ones (review the diff before committing).
"""

import argparse
import json
import os
import sys

import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("captured")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(args.captured) as f:
        captured = json.load(f)
    by_path = {}
    for key, line in captured.items():
        for candidate in (key, os.path.join("spec/lexer/cases", key)):
            path = os.path.join(root, candidate)
            if os.path.exists(path):
                by_path[os.path.realpath(path)] = line
                break
        else:
            print(f"no such case: {key}")

    differ = 0
    for case in cases.find(os.path.join(root, "spec")):
        line = by_path.get(os.path.realpath(case.path))
        if line is None:
            continue
        expected, actual = case.tokens(), cases.split_tokens(line)
        if expected == actual:
            continue
        differ += 1
        i = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
        print(f"{os.path.relpath(case.path, root)}: from token {i + 1}")
        print(f"    spec:     {' '.join(expected[i:i + 6]) or '(end)'}")
        print(f"    captured: {' '.join(actual[i:i + 6]) or '(end)'}")
        if args.write:
            case.fields["tokens"] = line
            case.save()
    print(f"{len(by_path)} captured cases, {differ} differ")
    sys.exit(1 if differ and not args.write else 0)


if __name__ == "__main__":
    main()
