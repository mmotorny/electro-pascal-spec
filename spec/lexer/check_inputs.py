"""Checks the reference lexer against TPC on arbitrary inputs.

Usage: python3 spec/lexer/check_inputs.py DIR CAPTURED.json SUMMARY.json

DIR holds the inputs (for example the fuzzer's finds), CAPTURED.json maps
each input's file name to the tokens TPC delivered in the spec's notation,
and SUMMARY.json is the fuzzer's summary, giving TPC's verdict for each file.
Prints every input on which the reference lexer, and so the spec, disagrees
with TPC: these are gaps to turn into cases.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cases  # noqa: E402
import reference  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dir")
    parser.add_argument("captured")
    parser.add_argument("summary")
    args = parser.parse_args()
    with open(args.captured) as f:
        captured = {os.path.basename(k): v for k, v in json.load(f).items()}
    with open(args.summary) as f:
        verdicts = {x["file"]: x["verdict"] for x in json.load(f)}
    gaps = 0
    for name in sorted(verdicts):
        if name not in captured:
            continue
        with open(os.path.join(args.dir, name), "rb") as f:
            source = f.read()
        tokens, error = reference.lex(source)
        problem = reference.check(tokens, error, cases.split_tokens(captured[name]), verdicts[name])
        if problem:
            gaps += 1
            print(f"{name}: {problem}\n    {source!r}")
    print(f"{len(verdicts)} inputs, {gaps} where the spec disagrees with TPC")


if __name__ == "__main__":
    main()
