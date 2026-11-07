"""Coverage-guided fuzzing of TPC, starting from the spec's cases.

Usage: bazel run //fuzz -- --out DIR [--rounds N] [cases dir ...]

Each round mutates inputs from the pool, compiles the mutants with TPC on the
reference machine with coverage on, and keeps every mutant that reaches code
no earlier input reached. At the end, each kept input ("find") is shrunk to
the smallest version that still reaches its new code, and written to DIR as
find-NNNN.pas, with summary.json listing each find's verdict.

Finds are inputs worth a closer look, not bugs: turn the interesting ones
into spec cases. Coverage data stays in DIR's summary only as counts.
"""

import argparse
import json
import os
import random
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "machine"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spec"))

import cases  # noqa: E402
import probe  # noqa: E402

MAX_SIZE = 400

# Pieces that matter to the lexer, used for insertions and replacements.
DICTIONARY = [
    b"$", b"#", b"^", b"'", b"''", b"{", b"}", b"(*", b"*)", b"(.", b".)", b"..", b".", b":=",
    b"<>", b"<=", b">=", b"@", b"e", b"E", b"e+", b"e-", b"0", b"9", b"$F", b"#13", b"^M",
    b"\x1a", b"\r", b"\n", b"\t", b"\x00", b"\x80", b"\xff", b"_", b"{$", b"(*$", b"{$IFDEF X}",
    b"{$ENDIF}", b"{$ELSE}", b"{$DEFINE X}", b"{$I+}", b"{$R-}", b"asm", b"end", b"begin",
    b"2147483647", b"2147483648", b"4294967295", b"$FFFFFFFF", b"$100000000", b"1e4932",
    b"1.5", b"1.", b"9999", b"10000", b"#255", b"#256", b"#$FF", b"^@", b"^[", b"string",
    b"inline", b"(", b")", b"[", b"]", b";", b",", b"=", b"+", b"-", b"*", b"/",
]
TOKEN = re.compile(rb"[A-Za-z_][A-Za-z0-9_]*|\$[0-9A-Fa-f]*|[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]*)?"
                   rb"|'(?:[^'\n]|'')*'?|#\$?[0-9A-Fa-f]*|\^.|\{[^}]*\}?|\(\*.*?\*\)|[ \t\r\n]+|.", re.S)


def tokens(source):
    return TOKEN.findall(source)


def mutate(source, pool, rng):
    """One to four random edits of a source."""
    for _ in range(rng.choice((1, 1, 2, 3, 4))):
        toks = tokens(source) or [b""]
        i = rng.randrange(len(toks))
        op = rng.randrange(10)
        if op == 0:
            del toks[i]
        elif op == 1:
            toks.insert(i, toks[i])
        elif op == 2 and i + 1 < len(toks):
            toks[i], toks[i + 1] = toks[i + 1], toks[i]
        elif op == 3:
            toks[i] = rng.choice(DICTIONARY)
        elif op == 4:
            toks.insert(i, rng.choice(DICTIONARY))
        elif op == 5:
            toks.insert(i, bytes([rng.randrange(256)]))
        elif op == 6 and toks[i]:
            b = bytearray(toks[i])
            j = rng.randrange(len(b))
            b[j] = rng.randrange(256)
            toks[i] = bytes(b)
        elif op == 7:
            other = tokens(rng.choice(pool))
            if other:
                j = rng.randrange(len(other))
                toks[i:i] = other[j:j + rng.randint(1, 6)]
        elif op == 8 and toks[i][:1].isalpha():
            toks[i] = toks[i][:1] * rng.choice((62, 63, 64, 100, 120))
        elif op == 9 and toks[i][:1].isdigit():
            toks[i] = rng.choice((b"9", b"1", b"0")) * rng.choice((10, 11, 20, 40, 100))
        source = b"".join(toks)
    return source[:MAX_SIZE]


def shrink(run, finds, rounds=6):
    """Deletes chunks from each find while it still reaches its new edges."""
    for _ in range(rounds):
        candidates, owners = [], []
        for n, f in enumerate(finds):
            toks = tokens(f["source"])
            for size in (8, 3, 1):
                for i in range(0, len(toks), size):
                    smaller = b"".join(toks[:i] + toks[i + size:])
                    if smaller != f["source"]:
                        candidates.append(smaller)
                        owners.append(n)
        if not candidates:
            return
        results = run(candidates)
        best = {}
        for src, n, r in zip(candidates, owners, results):
            if finds[n]["new"] <= set(r["coverage"]) and r["verdict"] == finds[n]["result"]["verdict"]:
                if n not in best or len(src) < len(best[n][0]):
                    best[n] = (src, r)
        if not best:
            return
        for n, (src, r) in best.items():
            finds[n]["source"], finds[n]["result"] = src, r


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True)
    parser.add_argument("--coverage-plugin", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--per-round", type=int, default=3200)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("seeds", nargs="*", help="case directories to start from")
    args = parser.parse_args()

    workspace = os.environ.get("BUILD_WORKSPACE_DIRECTORY", os.getcwd())
    base = os.environ.get("BUILD_WORKING_DIRECTORY", workspace)
    out = os.path.join(base, args.out)
    os.makedirs(out, exist_ok=True)
    seed_dirs = [os.path.join(base, d) for d in args.seeds] or [os.path.join(workspace, "spec", "lexer", "cases")]
    pool = [c.source for d in seed_dirs for c in cases.find(d)]

    tools = probe.Tools(os.path.abspath(args.qemu), os.path.abspath(args.mtools))
    disk, plugin = os.path.abspath(args.disk), os.path.abspath(args.coverage_plugin)

    def run(sources):
        return probe.run(tools, disk, sources, coverage=plugin)[1]

    rng = random.Random(args.seed)
    seen = set()
    for r in run(pool):
        seen |= set(r["coverage"])
    print(f"{len(pool)} seeds reach {len(seen)} edges", flush=True)

    finds = []
    for round_number in range(args.rounds):
        start = time.time()
        mutants = list({mutate(rng.choice(pool), pool, rng) for _ in range(args.per_round)})
        found = 0
        for src, r in zip(mutants, run(mutants)):
            new = set(r["coverage"]) - seen
            if new:
                seen |= new
                pool.append(src)
                finds.append({"source": src, "new": new, "result": r})
                found += 1
        print(f"round {round_number + 1}: {len(mutants)} mutants, {found} finds, {len(seen)} edges, "
              f"{time.time() - start:.0f}s", flush=True)

    print(f"shrinking {len(finds)} finds", flush=True)
    shrink(run, finds)
    summary = []
    for n, f in enumerate(finds):
        name = f"find-{n:04}.pas"
        with open(os.path.join(out, name), "wb") as fh:
            fh.write(f["source"])
        summary.append({"file": name, "new_edges": len(f["new"]), "verdict": cases.verdict_text(f["result"]),
                        "message": f["result"].get("message"), "output": f["result"].get("run_output")})
    with open(os.path.join(out, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"wrote {len(finds)} finds to {out}")


if __name__ == "__main__":
    main()
