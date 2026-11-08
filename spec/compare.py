"""Compares cases' token lists with tokens captured from TPC.

Usage: bazel run //spec:compare -- CAPTURED.json [--write]

CAPTURED.json maps case paths (relative to spec/lexer/cases/, or to the repo)
to token lists in the form of a case's `tokens` (a kind, or a mapping from a
kind to its value), as produced by the dirty room's capture tool. Prints
every case whose tokens differ, showing where the two first part. With
--write, replaces the cases' tokens with the captured ones (review the diff
before committing).
"""

import argparse
import json
import os
import sys

import cases


def pairs(tokens):
    return [next(iter(t.items())) if isinstance(t, dict) else (t, None) for t in tokens]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("captured")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = os.environ.get("BUILD_WORKSPACE_DIRECTORY") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    base = os.environ.get("BUILD_WORKING_DIRECTORY", root)
    with open(os.path.join(base, args.captured)) as f:
        captured = json.load(f)
    by_path = {}
    for key, tokens in captured.items():
        for candidate in (key, os.path.join("spec/lexer/cases", key)):
            path = os.path.join(root, candidate)
            if os.path.exists(path):
                by_path[os.path.realpath(path)] = pairs(tokens)
                break
        else:
            print(f"no such case: {key}")

    differ = 0
    for case in cases.find(os.path.join(root, "spec")):
        actual = by_path.get(os.path.realpath(case.path))
        if actual is None:
            continue
        expected = case.tokens
        if expected == actual:
            continue
        differ += 1
        i = next((i for i, (a, b) in enumerate(zip(expected, actual)) if a != b), min(len(expected), len(actual)))
        show = lambda ts: ", ".join(cases.token_text(*t) for t in ts[i:i + 6]) or "(end)"
        print(f"{os.path.relpath(case.path, root)}: from token {i + 1}")
        print(f"    spec:     {show(expected)}")
        print(f"    captured: {show(actual)}")
        if args.write:
            case.tokens = actual
            case.save()
    print(f"{len(by_path)} captured cases, {differ} differ")
    sys.exit(1 if differ and not args.write else 0)


if __name__ == "__main__":
    main()
