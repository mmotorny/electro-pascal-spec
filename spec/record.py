"""Runs every spec case through TPC and writes its verdict and output into the case.

Usage: bazel run //spec:record [-- case or directory ...]

With no arguments, records every case under spec/. Prints the cases whose
verdict changed. Also writes spec/MACHINE.json: what the verdicts ran on.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "machine"))

import cases  # noqa: E402
import probe  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True)
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args()

    workspace = os.environ["BUILD_WORKSPACE_DIRECTORY"]
    base = os.environ.get("BUILD_WORKING_DIRECTORY", workspace)
    paths = [os.path.join(base, p) for p in args.paths] or [os.path.join(workspace, "spec")]
    selected = []
    for path in paths:
        selected += [cases.Case(path)] if path.endswith(cases.EXTENSION) else cases.find(path)

    tools = probe.Tools(os.path.abspath(args.qemu), os.path.abspath(args.mtools))
    info, results = probe.run(tools, os.path.abspath(args.disk), [c.source for c in selected])
    changed = 0
    for case, result in zip(selected, results):
        new = {"compile": cases.verdict(result)}
        if "run_output" in result:
            new["output"] = result["run_output"]
        old = {k: case.data.get(k) for k in ("compile", "output")}
        if old != {"compile": new["compile"], "output": new.get("output")}:
            print(f"{os.path.relpath(case.path, workspace)}: {old} -> {new}")
            case.data.pop("output", None)
            case.data.update(new)
            case.save()
            changed += 1
    with open(os.path.join(workspace, "spec", "MACHINE.json"), "w") as f:
        f.write(json.dumps(info, indent=2) + "\n")
    print(f"{len(selected)} cases, {changed} changed")


if __name__ == "__main__":
    main()
