"""Compiles probe programs with TPC on the reference machine.

Each batch of probes goes onto a floppy image as A:\\P\\Pnnnnnnn.PAS, together
with a batch file that compiles each one with C:\\BP\\BIN\\TPC.EXE and saves
its output. The reference disk boots without being changed. Batches run on
several machines in parallel.

Each result is either {"verdict": "ok"} or {"verdict": "error", "code": N,
"line": L, "column": C, "message": "..."}, plus TPC's full output and its
exit code. Line and column are 1-based; the column is where TPC puts its
caret. When a probe compiles, the program is also run, and "run_output"
holds what it wrote to standard output (as a latin-1 string, one character
per byte).
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile

from qmp import Machine, log

PARTITION_OFFSET = 63 * 512  # Of C: on the reference disk; see defs.bzl.
BATCH_SIZE = 200  # Fits on one floppy with room to spare.
TPC = "C:\\BP\\BIN\\TPC.EXE"
# Files whose hashes are recorded with every result.
RECORDED_FILES = ["BP/BIN/TPC.EXE", "BP/BIN/TURBO.TPL", "BP/BIN/TPC.CFG"]


class Tools:
    def __init__(self, qemu, mtools):
        self.qemu = qemu
        self.mtools = mtools

    def mtool(self, command, *args, capture=False):
        env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
        result = subprocess.run([self.mtools, "-c", command, *args], env=env, check=True,
                                stdout=subprocess.PIPE if capture else subprocess.DEVNULL)
        return result.stdout


def parse_output(text):
    """Turns TPC's output into a verdict."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        # Progress lines like "P0001.PAS(1)" are overwritten with \r.
        line = line.rsplit("\r", 1)[-1]
        match = re.match(r"^\S+\((\d+)\): Error (\d+): (.*)$", line)
        if match:
            column = None
            if i + 2 < len(lines) and "^" in lines[i + 2]:
                column = lines[i + 2].index("^") + 1
            return {"verdict": "error", "code": int(match.group(2)),
                    "line": int(match.group(1)), "column": column,
                    "message": match.group(3)}
        match = re.match(r"^(?:\S+: )?Error (\d+): (.*)$", line)
        if match:
            return {"verdict": "error", "code": int(match.group(1)), "line": None,
                    "column": None, "message": match.group(2)}
    if any(re.search(r"\d+ lines, \d+ bytes code", l) for l in lines):
        return {"verdict": "ok"}
    return {"verdict": "unknown"}


def run_batch(tools, disk, sources, workdir, first=0):
    """Compiles up to BATCH_SIZE sources on one machine.

    Probes are numbered from `first`, so that TPC's output, which names the
    file, doesn't depend on how a run was split into batches.
    """
    floppy = os.path.join(workdir, "probes.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    tools.mtool("mmd", "-i", floppy, "::/P")
    script = ["@ECHO OFF", "A:", "CD \\P"]
    for n, source in enumerate(sources):
        name = f"P{first + n:07}"
        path = os.path.join(workdir, name + ".PAS")
        with open(path, "wb") as f:
            f.write(source)
        script += [
            f"{TPC} {name}.PAS > {name}.OUT",
            # COMMAND.COM creates the file even when the condition is false,
            # so a non-zero exit code is a non-empty file.
            f"IF ERRORLEVEL 1 ECHO 1> {name}.ERL",
            # As with ERL, the redirection creates RUN even if nothing runs.
            f"IF EXIST {name}.EXE {name} > {name}.RUN",
            f"IF EXIST {name}.EXE DEL {name}.EXE",
        ]
    script += ["CD \\", "ECHO PROBES DONE"]
    with open(os.path.join(workdir, "RUN.BAT"), "wb") as f:
        f.write(("\r\n".join(script) + "\r\n").encode("ascii"))
    tools.mtool("mcopy", "-i", floppy, os.path.join(workdir, "RUN.BAT"), "::/")
    tools.mtool("mcopy", "-i", floppy,
                *[os.path.join(workdir, f"P{first + n:07}.PAS") for n in range(len(sources))], "::/P/")

    m = Machine(tools.qemu, workdir, disk, floppy=floppy, snapshot=True, floppy_writable=True,
                boot="c")
    try:
        m.wait_prompt("C:\\>", timeout=60)
        m.type("A:\\RUN\n")
        m.wait(r"PROBES DONE", timeout=60 + 5 * len(sources))
    finally:
        m.quit()

    out_dir = os.path.join(workdir, "out")
    os.makedirs(out_dir)
    tools.mtool("mcopy", "-n", "-i", floppy, "::/P/*.OUT", "::/P/*.ERL", "::/P/*.RUN", out_dir + "/")
    results = []
    for n in range(len(sources)):
        name = f"P{first + n:07}"
        with open(os.path.join(out_dir, name + ".ERL"), "rb") as f:
            failed = bool(f.read().strip())
        with open(os.path.join(out_dir, name + ".OUT"), "rb") as f:
            output = f.read().decode("cp437")
        result = parse_output(output)
        result["exit_code"] = 1 if failed else 0
        if result["verdict"] == "ok":
            with open(os.path.join(out_dir, name + ".RUN"), "rb") as f:
                result["run_output"] = f.read().decode("latin-1")
        result["output"] = output
        results.append(result)
    return results


def machine_info(tools, disk, workdir):
    """What the results ran on, recorded alongside them."""
    version = subprocess.run([tools.qemu, "--version"], capture_output=True, text=True,
                             check=True).stdout.splitlines()[0]
    hashes = {}
    for path in RECORDED_FILES:
        local = os.path.join(workdir, os.path.basename(path))
        tools.mtool("mcopy", "-n", "-i", f"{disk}@@{PARTITION_OFFSET}", "::/" + path, local)
        with open(local, "rb") as f:
            hashes[path.replace("/", "\\")] = hashlib.sha256(f.read()).hexdigest()
    return {"qemu": version, "sha256": hashes}


def run(tools, disk, sources, jobs=None):
    """Compiles each source (bytes) and returns (machine info, results)."""
    jobs = jobs or os.cpu_count() or 1
    size = max(1, min(BATCH_SIZE, -(-len(sources) // jobs)))  # Spread over all machines.
    batches = [sources[i:i + size] for i in range(0, len(sources), size)]
    with tempfile.TemporaryDirectory() as work:
        info = machine_info(tools, disk, work)

        def one(i):
            d = os.path.join(work, f"batch{i}")
            os.makedirs(d)
            log(f"batch {i + 1}/{len(batches)}: {len(batches[i])} probes")
            return run_batch(tools, disk, batches[i], d, first=i * size)

        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            results = [r for batch in pool.map(one, range(len(batches))) for r in batch]
    return info, results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True, help="the reference disk")
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--out", help="JSON file to write; default: stdout")
    parser.add_argument("sources", nargs="+", help="Pascal source files")
    args = parser.parse_args()

    # Under `bazel run`, paths on the command line are relative to where it ran.
    base = os.environ.get("BUILD_WORKING_DIRECTORY", "")
    sources = []
    for path in args.sources:
        with open(os.path.join(base, path), "rb") as f:
            sources.append(f.read())
    tools = Tools(os.path.abspath(args.qemu), os.path.abspath(args.mtools))
    info, results = run(tools, os.path.abspath(args.disk), sources, args.jobs)
    report = {"machine": info,
              "results": [dict(source=path, **r) for path, r in zip(args.sources, results)]}
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        with open(os.path.join(base, args.out), "w") as f:
            f.write(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
