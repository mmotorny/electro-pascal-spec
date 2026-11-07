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

With a coverage plugin (//machine/coverage), each result also gets
"coverage": the sorted edge indices TPC executed while compiling the probe.
Only code inside TPC's own load image counts, so that BIOS, DOS and timer
interrupts don't make coverage differ between runs. Where TPC loads is found
by running a tiny program from the same batch file that prints its PSP
segment; DOS gives TPC the same place.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import tempfile

from qmp import Machine, log

PARTITION_OFFSET = 63 * 512  # Of C: on the reference disk; see defs.bzl.
BATCH_SIZE = 200  # Fits on one floppy with room to spare.
TPC = "C:\\BP\\BIN\\TPC.EXE"
# A .COM program that executes the coverage plugin's marker, XCHG BX,BX, and
# exits: MOV AX,4C00h; INT 21h.
MARKER_COM = bytes([0x87, 0xDB, 0xB8, 0x00, 0x4C, 0xCD, 0x21])
# A .COM program that prints its PSP segment as 4 hex digits:
#   MOV AH,62h; INT 21h; MOV CX,4
#   L: ROL BX,4; MOV DL,BL; AND DL,0Fh; ADD DL,'0'; CMP DL,'9'; JBE P
#      ADD DL,7
#   P: MOV AH,2; INT 21h; LOOP L
#   MOV AX,4C00h; INT 21h
PSP_COM = bytes.fromhex("b462cd21b90400c1c30488da80e20f80c23080fa39760380c207b402cd21e2e7b8004ccd21")
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
    # Compiles that take 0.1 s or more also report ", X.X seconds".
    if any(re.search(r"\d+ lines, (?:[\d.]+ seconds, )?\d+ bytes code", l) for l in lines):
        return {"verdict": "ok"}
    return {"verdict": "unknown"}


def run_batch(tools, disk, sources, workdir, first=0, coverage=None):
    """Compiles up to BATCH_SIZE sources on one machine.

    Probes are numbered from `first`, so that TPC's output, which names the
    file, doesn't depend on how a run was split into batches.
    """
    floppy = os.path.join(workdir, "probes.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    tools.mtool("mmd", "-i", floppy, "::/P")
    script = ["@ECHO OFF", "A:", "CD \\P"]
    if coverage:
        script.append("A:\\PSP > A:\\PSP.TXT")
    for n, source in enumerate(sources):
        name = f"P{first + n:07}"
        path = os.path.join(workdir, name + ".PAS")
        with open(path, "wb") as f:
            f.write(source)
        if coverage:
            script.append("A:\\MARK")
        script += [f"{TPC} {name}.PAS > {name}.OUT"]
        if coverage:
            script.append("A:\\MARK")
        script += [
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
    extra = []
    if coverage:
        for name, code in (("MARK.COM", MARKER_COM), ("PSP.COM", PSP_COM)):
            with open(os.path.join(workdir, name), "wb") as f:
                f.write(code)
            tools.mtool("mcopy", "-i", floppy, os.path.join(workdir, name), "::/")
        edges_file = os.path.join(workdir, "edges.txt")
        lo, hi = coverage["range"]
        extra = ["-plugin", f"{coverage['plugin']},out={edges_file},lo={lo},hi={hi}"]
    tools.mtool("mcopy", "-i", floppy,
                *[os.path.join(workdir, f"P{first + n:07}.PAS") for n in range(len(sources))], "::/P/")

    m = Machine(tools.qemu, workdir, disk, floppy=floppy, snapshot=True, floppy_writable=True,
                boot="c", extra_args=extra)
    try:
        m.wait_prompt("C:\\>", timeout=60)
        m.type("A:\\RUN\n")
        m.wait(r"PROBES DONE", timeout=60 + 5 * len(sources))
    finally:
        m.quit()

    out_dir = os.path.join(workdir, "out")
    os.makedirs(out_dir)
    tools.mtool("mcopy", "-n", "-i", floppy, "::/P/*.OUT", "::/P/*.ERL", "::/P/*.RUN", out_dir + "/")
    edges = []
    if coverage:
        with open(edges_file) as f:
            lines = f.read().split("\n")
        # Lines alternate: before a probe's first marker, then between its
        # two markers, which is TPC compiling it.
        edges = [sorted(int(x, 16) for x in lines[2 * n + 1].split()) for n in range(len(sources))]
    results = []
    for n in range(len(sources)):
        name = f"P{first + n:07}"
        with open(os.path.join(out_dir, name + ".ERL"), "rb") as f:
            failed = bool(f.read().strip())
        with open(os.path.join(out_dir, name + ".OUT"), "rb") as f:
            output = f.read().decode("cp437")
        result = parse_output(output)
        result["exit_code"] = 1 if failed else 0
        if coverage:
            result["coverage"] = edges[n]
        if result["verdict"] == "ok":
            with open(os.path.join(out_dir, name + ".RUN"), "rb") as f:
                result["run_output"] = f.read().decode("latin-1")
        result["output"] = output
        results.append(result)
    return results


def tpc_range(tools, disk, workdir):
    """The linear addresses of TPC's load image on the reference machine."""
    d = os.path.join(workdir, "calibrate")
    os.makedirs(d)
    floppy = os.path.join(d, "fd.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    for name, code in (("PSP.COM", PSP_COM),):
        with open(os.path.join(d, name), "wb") as f:
            f.write(code)
        tools.mtool("mcopy", "-i", floppy, os.path.join(d, name), "::/")
    with open(os.path.join(d, "RUN.BAT"), "wb") as f:
        f.write(b"@ECHO OFF\r\nA:\r\nCD \\P\r\nA:\\PSP > A:\\PSP.TXT\r\nCD \\\r\nECHO PROBES DONE\r\n")
    tools.mtool("mcopy", "-i", floppy, os.path.join(d, "RUN.BAT"), "::/")
    tools.mtool("mmd", "-i", floppy, "::/P")
    m = Machine(tools.qemu, d, disk, floppy=floppy, snapshot=True, floppy_writable=True, boot="c")
    try:
        m.wait_prompt("C:\\>", timeout=60)
        m.type("A:\\RUN\n")
        m.wait(r"PROBES DONE", timeout=60)
    finally:
        m.quit()
    psp = int(tools.mtool("mtype", "-i", floppy, "::/PSP.TXT", capture=True).decode().strip(), 16)
    exe = os.path.join(d, "TPC.EXE")
    tools.mtool("mcopy", "-n", "-i", f"{disk}@@{PARTITION_OFFSET}", "::/BP/BIN/TPC.EXE", exe)
    with open(exe, "rb") as f:
        header = f.read(32)
    last_page, pages, _, header_paragraphs = struct.unpack_from("<HHHH", header, 2)
    image = pages * 512 - (512 - last_page if last_page else 0) - header_paragraphs * 16
    start = (psp + 0x10) * 16
    return start, start + image


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


def run(tools, disk, sources, jobs=None, coverage=None, coverage_range=None):
    """Compiles each source (bytes) and returns (machine info, results).

    coverage: path to the coverage plugin, to record coverage.
    coverage_range: (lo, hi) linear addresses to count coverage in; default:
        all of TPC's load image.
    """
    jobs = jobs or os.cpu_count() or 1
    size = max(1, min(BATCH_SIZE, -(-len(sources) // jobs)))  # Spread over all machines.
    batches = [sources[i:i + size] for i in range(0, len(sources), size)]
    with tempfile.TemporaryDirectory() as work:
        info = machine_info(tools, disk, work)
        if coverage:
            coverage = {"plugin": coverage, "range": coverage_range or tpc_range(tools, disk, work)}

        def one(i):
            d = os.path.join(work, f"batch{i}")
            os.makedirs(d)
            log(f"batch {i + 1}/{len(batches)}: {len(batches[i])} probes")
            return run_batch(tools, disk, batches[i], d, first=i * size, coverage=coverage)

        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            results = [r for batch in pool.map(one, range(len(batches))) for r in batch]
    return info, results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True, help="the reference disk")
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--coverage-plugin", help="the coverage plugin, //machine/coverage")
    parser.add_argument("--coverage", action="store_true", help="record each probe's coverage")
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
    plugin = os.path.abspath(args.coverage_plugin) if args.coverage else None
    info, results = run(tools, os.path.abspath(args.disk), sources, args.jobs, coverage=plugin)
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
