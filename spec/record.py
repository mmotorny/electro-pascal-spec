"""Runs spec cases through TPC and writes what it gives into the cases.

Usage: bazel run //spec:record [-- case or directory ...]
       bazel test //spec:tpc_test

With no case or directory, takes every case under spec/. Records each
case's tokens (captured from TPC's scanner by machine/tokens.py), compile
and output (from machine/probe.py), prints the cases that changed, and
writes spec/MACHINE.json: what the results ran on.

With --check (as //spec:tpc_test runs it), changes nothing: prints every case
whose tokens, compile or output differ from what TPC gives, and fails if any
do.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "machine"))

import cases  # noqa: E402
import probe  # noqa: E402
import tokens  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True)
    parser.add_argument("--check", action="store_true", help="compare instead of recording")
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()

    # Under bazel test there is no workspace: the cases are in the runfiles.
    spec = os.path.dirname(os.path.abspath(__file__))
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY", os.path.dirname(spec))
    if "BUILD_WORKSPACE_DIRECTORY" in os.environ:
        spec = os.path.join(workspace, "spec")
    base = os.environ.get("BUILD_WORKING_DIRECTORY", workspace)
    paths = [os.path.join(base, p) for p in args.paths] or [spec]
    selected = []
    for path in paths:
        selected += [cases.Case(path)] if path.endswith(cases.EXTENSION) else cases.find(path)

    tools = probe.Tools(os.path.abspath(args.qemu), os.path.abspath(args.mtools))
    sources = [c.source for c in selected]
    info, results = probe.run(tools, os.path.abspath(args.disk), sources)
    _, captured = tokens.run(tools, os.path.abspath(args.disk), sources)
    changed = 0
    for case, result, capture in zip(selected, results, captured):
        new = {"tokens": capture["tokens"], "compile": cases.verdict(result)}
        if "run_output" in result:
            new["output"] = result["run_output"]
        old = {k: case.data.get(k) for k in ("tokens", "compile", "output")}
        if old == {**new, "output": new.get("output")}:
            continue
        changed += 1
        name = os.path.relpath(case.path, workspace)
        if args.check:
            for problem in differences(old, new):
                print(f"{name}: {problem}")
            continue
        print(f"{name}: " + "; ".join(differences(old, new)))
        case.data.pop("output", None)
        case.data.update(new)
        case.save()
    machine_file = os.path.join(spec, "MACHINE.json")
    if args.check:
        with open(machine_file) as f:
            recorded = json.load(f)
        if recorded != info:
            print(f"note: the cases were recorded on {recorded}, this run is on {info}")
        print(f"{len(selected)} cases, {changed} differ from TPC")
        sys.exit(1 if changed else 0)
    with open(machine_file, "w") as f:
        f.write(json.dumps(info, indent=2) + "\n")
    print(f"{len(selected)} cases, {changed} changed")


def differences(old, new):
    """What differs between a case's recorded fields and what TPC gives."""
    out = []
    if old["tokens"] != new["tokens"]:
        a = [cases.token_text(*t) for t in cases.token_pairs(old["tokens"] or [])]
        b = [cases.token_text(*t) for t in cases.token_pairs(new["tokens"])]
        i = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
        out.append(f"tokens from {i + 1}: the case says {', '.join(a[i:i + 4]) or '(end)'}; "
                   f"TPC gives {', '.join(b[i:i + 4]) or '(end)'}")
    for key in ("compile", "output"):
        if old.get(key) != new.get(key):
            show = lambda v: "nothing" if v is None else cases.verdict_text(v) if key == "compile" else cases.scalar(v)
            out.append(f"{key}: the case says {show(old.get(key))}; TPC gives {show(new.get(key))}")
    return out


if __name__ == "__main__":
    main()
