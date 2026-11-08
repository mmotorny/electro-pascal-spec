"""Sets up and scores a clean-room trial: an implementation built from spec/ alone.

Usage: bazel run //harness:clean_room -- prepare DIR
       bazel run //harness:clean_room -- score FILE [-v]

prepare copies spec/ to DIR/spec with every case's recorded results
(tokens, compile, output) removed, so that whoever implements from it can
read the rules and the cases' sources but not what TPC gave.

score imports FILE, which must define

    scan(source, files, options, precompile) -> {"tokens": [...], "compile": ...}

taking a case's program as bytes, its other files as {DOS name: bytes}, its
TPC options and the files it compiles first, and giving the token list and
compile outcome in the cases' notation (see spec/case.schema.yaml). It runs
every case and prints, per folder, how many give:

  exact        the case's tokens and compile outcome;
  tokens only  its tokens, but another outcome;
  prefix       a token list that starts with the case's, where TPC stopped
               at an error the implementation doesn't report;
  mismatch     anything else;
  crash        an exception.

With -v it also lists every case that isn't exact.
"""

import argparse
import collections
import importlib.util
import os
import shutil
import sys
import traceback

import cases

RESULTS = ("tokens", "compile", "output")
KINDS = ("exact", "tokens only", "prefix", "mismatch", "crash")


def prepare(spec, out):
    target = os.path.join(out, "spec")
    if os.path.exists(target):
        sys.exit(f"{target} already exists")
    shutil.copytree(spec, target, ignore=shutil.ignore_patterns("BUILD.bazel"))
    stripped = cases.find(target)
    for case in stripped:
        for key in RESULTS:
            case.data.pop(key, None)
        case.save()
    print(f"{target}: {len(stripped)} cases, recorded results removed")


def classify(case, out):
    """(kind, detail) for one case's output from scan."""
    got, got_compile = out["tokens"], out["compile"]
    if isinstance(got_compile, dict):
        got_compile = {k: v for k, v in got_compile.items() if v is not None}
    want, want_compile = case.data["tokens"], case.data["compile"]
    if got == want:
        if got_compile == want_compile:
            return "exact", ""
        return "tokens only", f"TPC gives {want_compile}; scan gives {got_compile}"
    if got[:len(want)] == want and want_compile not in ("ok", "hang"):
        return "prefix", f"TPC stops with {cases.verdict_text(want_compile)}"
    i = next((i for i, (a, b) in enumerate(zip(got, want)) if a != b), min(len(got), len(want)))
    return "mismatch", f"token {i + 1}: TPC gives {want[i:i + 3]}; scan gives {got[i:i + 3]}"


def score(spec, path, verbose):
    sys.path.insert(0, os.path.dirname(os.path.abspath(path)))
    loader = importlib.util.spec_from_file_location("implementation", path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    tally = collections.defaultdict(collections.Counter)
    details = []
    for case in cases.find(spec):
        folder = os.path.basename(os.path.dirname(case.path))
        try:
            kind, detail = classify(case, module.scan(case.source, case.files, case.options, case.precompile))
        except Exception:
            kind, detail = "crash", traceback.format_exc().strip().splitlines()[-1]
        tally[folder][kind] += 1
        if kind != "exact":
            details.append(f"{folder}/{case.name}: {kind}: {detail}")
    total = collections.Counter()
    print("| folder | " + " | ".join(KINDS) + " |")
    print("|---" * (len(KINDS) + 1) + "|")
    for folder in sorted(tally):
        total.update(tally[folder])
        print(f"| {folder} | " + " | ".join(str(tally[folder][k]) for k in KINDS) + " |")
    print("| total | " + " | ".join(str(total[k]) for k in KINDS) + " |")
    if verbose:
        print("\n".join(details))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare").add_argument("dir")
    p = sub.add_parser("score")
    p.add_argument("file")
    p.add_argument("-v", action="store_true")
    args = parser.parse_args()
    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY",
                               os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    base = os.environ.get("BUILD_WORKING_DIRECTORY", workspace)
    spec = os.path.join(workspace, "spec")
    if args.command == "prepare":
        prepare(spec, os.path.join(base, args.dir))
    else:
        score(spec, os.path.join(base, args.file), args.v)


if __name__ == "__main__":
    main()
