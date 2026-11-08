"""Compiles probe programs with TPC on the reference machine.

Each batch of probes goes onto a floppy image as A:\\P\\Pnnnnnnn.PAS, together
with a batch file that compiles each one with C:\\BP\\BIN\\TPC.EXE and saves
its output. The reference disk boots without being changed. Batches run on
several machines in parallel.

Each result is either {"verdict": "ok"}, {"verdict": "error", "code": N,
"line": L, "column": C, "message": "..."} or {"verdict": "hang"}, plus TPC's
full output and its exit code (for a hang, only the verdict). Line and column are 1-based; the column is where TPC puts its
caret. When a probe compiles, the program is also run, and "run_output"
holds what it wrote to standard output (as a latin-1 string, one character
per byte).

With a coverage plugin (//machine/coverage), each result also gets
"coverage": the sorted edge indices TPC executed while compiling the probe.
Only code inside TPC's own load image counts, so that BIOS, DOS and timer
interrupts don't make coverage differ between runs. Where TPC loads is found
by running a tiny program that prints its PSP segment. DOS gives TPC the
same place, provided the program's full path is as long as TPC's, because
DOS stores the path in the environment block allocated just below it.
"""

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time

from qmp import Machine, log

PARTITION_OFFSET = 63 * 512  # Of C: on the reference disk; see defs.bzl.
BATCH_SIZE = 200  # Fits on one floppy with room to spare.
# A compile still running after this many seconds is reported as a hang.
HANG_SECONDS = 30
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


def parse_output(text, main_file=None):
    """Turns TPC's output into a verdict. An error in a file other than
    main_file also gets "file": that file's name."""
    lines = text.replace("\r\n", "\n").split("\n")
    for i, line in enumerate(lines):
        # Progress lines like "P0001.PAS(1)" are overwritten with \r.
        line = line.rsplit("\r", 1)[-1]
        match = re.match(r"^(\S+)\((\d+)\): Error (\d+): (.*)$", line)
        if match:
            column = None
            if i + 2 < len(lines) and "^" in lines[i + 2]:
                column = lines[i + 2].index("^") + 1
            result = {"verdict": "error", "code": int(match.group(3)),
                      "line": int(match.group(2)), "column": column,
                      "message": match.group(4)}
            if main_file and match.group(1).upper() != main_file.upper():
                result["file"] = match.group(1).upper()
            return result
        match = re.match(r"^(?:\S+: )?Error (\d+): (.*)$", line)
        if match:
            return {"verdict": "error", "code": int(match.group(1)), "line": None,
                    "column": None, "message": match.group(2)}
    # Compiles that take 0.1 s or more also report ", X.X seconds".
    if any(re.search(r"\d+ lines, (?:[\d.]+ seconds, )?\d+ bytes code", l) for l in lines):
        return {"verdict": "ok"}
    return {"verdict": "unknown"}


# Extra files a probe may bring along: DOS 8.3 names, in upper case.
FILE_NAME = re.compile(r"[A-Z0-9_]{1,8}(\.[A-Z0-9_]{1,3})?")


def probe_name(n):
    """The name of probe number n: its folder on the floppy and its main file."""
    return f"P{n:07}"


# Options a probe may give TPC: no blanks or characters COMMAND.COM treats
# specially.
OPTION = re.compile(r"[/-][A-Za-z0-9$_.:;=+,\\-]*")


def unpack(source):
    """A probe's (program, extra files, TPC options, files to compile first,
    fpu). A source is the program as bytes, or (bytes, {file name: bytes}), or
    that plus [option, ...], or that plus [file name, ...]: extra files that
    TPC compiles, in that order and with no options, before the program; or
    that plus False, for TPC to compile as on a machine without a
    floating-point unit."""
    if not isinstance(source, tuple):
        return source, {}, [], [], True
    main, extra, options, first, fpu = (source + ([], [], True))[:5]
    for option in options:
        if not OPTION.fullmatch(option):
            raise ValueError(f"bad TPC option {option!r}")
    for file_name in first:
        if file_name not in extra:
            raise ValueError(f"file to compile first {file_name!r} isn't among the extra files")
    return main, extra, options, first, fpu


def has_fpu(source):
    return unpack(source)[4]


def precompile(source):
    """The lines that compile a probe's files to compile first (see unpack)."""
    return [f"{TPC} {file_name} > NUL" for file_name in unpack(source)[3]]


def command(name, source):
    """The line that compiles probe `name` with TPC."""
    return " ".join([TPC] + unpack(source)[2] + [f"{name}.PAS > {name}.OUT"])


def lay_out(tools, floppy, workdir, names, sources):
    """Puts each probe in its own folder, A:\\P\\<name>\\, as <name>.PAS plus
    the extra files it brings (see unpack)."""
    tree = os.path.join(workdir, "P")
    for name, source in zip(names, sources):
        main, extra = unpack(source)[:2]
        folder = os.path.join(tree, name)
        os.makedirs(folder)
        with open(os.path.join(folder, name + ".PAS"), "wb") as f:
            f.write(main)
        for file_name, data in extra.items():
            if not FILE_NAME.fullmatch(file_name) or file_name.startswith("P0"):
                raise ValueError(f"bad extra file name {file_name!r}")
            with open(os.path.join(folder, file_name), "wb") as f:
                f.write(data)
    tools.mtool("mcopy", "-s", "-i", floppy, tree, "::/")


def run_batch(tools, disk, sources, workdir, first=0, coverage=None):
    """Compiles up to BATCH_SIZE sources on one machine. The sources all have
    an FPU, or all don't (see unpack).

    Probes are numbered from `first`, so that TPC's output, which names the
    file, doesn't depend on how a run was split into batches.
    """
    fpu = {has_fpu(s) for s in sources}
    if len(fpu) != 1:
        raise ValueError("a batch's sources must all have an FPU or all not")
    return _run_batch(tools, disk, sources, workdir, first, coverage, fpu.pop())


def _run_batch(tools, disk, sources, workdir, first, coverage, fpu):
    floppy = os.path.join(workdir, "probes.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    names = [probe_name(first + n) for n in range(len(sources))]
    lay_out(tools, floppy, workdir, names, sources)
    script = ["@ECHO OFF", "A:"]
    for name, source in zip(names, sources):
        script += [f"CD \\P\\{name}"] + precompile(source) + [f"ECHO COMPILING {name}"]
        if coverage:
            script.append("A:\\MARK")
        script += [command(name, source)]
        if coverage:
            script.append("A:\\MARK")
        script += [
            # COMMAND.COM creates the file even when the condition is false,
            # so a non-zero exit code is a non-empty file.
            f"IF ERRORLEVEL 1 ECHO 1> {name}.ERL",
            f"IF EXIST {name}.EXE ECHO RUNNING {name}",
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
        with open(os.path.join(workdir, "MARK.COM"), "wb") as f:
            f.write(MARKER_COM)
        tools.mtool("mcopy", "-i", floppy, os.path.join(workdir, "MARK.COM"), "::/")
        edges_file = os.path.join(workdir, "edges.txt")
        lo, hi = coverage["range"]
        extra = ["-plugin", f"{coverage['plugin']},out={edges_file},lo={lo},hi={hi}"]

    sockdir = no_fpu = None
    if not fpu:
        import tokens  # Knows where TPC tests for an FPU; it imports this module.
        # A short socket path: Unix socket paths are limited to about 100 bytes.
        sockdir = tempfile.mkdtemp(prefix="fpu", dir="/tmp")
        sock = os.path.join(sockdir, "gdb")
        extra += ["-chardev", f"socket,id=gdb0,path={sock},server=on,wait=off",
                  "-gdb", "chardev:gdb0", "-S"]
    m = Machine(tools.qemu, workdir, disk, floppy=floppy, snapshot=True, floppy_writable=True,
                boot="c", extra_args=extra)
    try:
        if not fpu:
            no_fpu = tokens.NoFpu(sock)
        m.wait_prompt("C:\\>", timeout=60)
        m.type("A:\\RUN\n")
        hung = wait_batch(m, names)
    finally:
        m.quit()
        if no_fpu:
            no_fpu.close()
        if sockdir:
            shutil.rmtree(sockdir, ignore_errors=True)
    done = names.index(hung) if hung else len(names)
    if no_fpu:
        if no_fpu.error:
            raise no_fpu.error
        due = sum(len(unpack(s)[3]) + 1 for s in sources[:done])
        if no_fpu.hits < due:
            raise RuntimeError(f"TPC tested for an FPU {no_fpu.hits} times where {due} compiles ran; "
                               "has TPC's load address changed?")

    out = os.path.join(workdir, "out")
    os.makedirs(out)
    tools.mtool("mcopy", "-s", "-n", "-i", floppy, "::/P", out + "/")
    edges = []
    if coverage:
        with open(edges_file) as f:
            lines = f.read().split("\n")
        # Lines alternate: before a probe's first marker, then between its
        # two markers, which is TPC compiling it.
        edges = [sorted(int(x, 16) for x in lines[2 * n + 1].split()) for n in range(done)]
    results = []
    for n, name in enumerate(names[:done]):
        out_dir = os.path.join(out, "P", name)
        with open(os.path.join(out_dir, name + ".ERL"), "rb") as f:
            failed = bool(f.read().strip())
        with open(os.path.join(out_dir, name + ".OUT"), "rb") as f:
            output = f.read().decode("cp437")
        result = parse_output(output, name + ".PAS")
        result["exit_code"] = 1 if failed else 0
        if coverage:
            result["coverage"] = edges[n]
        if result["verdict"] == "ok":
            with open(os.path.join(out_dir, name + ".RUN"), "rb") as f:
                result["run_output"] = f.read().decode("latin-1")
        result["output"] = output
        results.append(result)
    if hung:
        log(f"{hung}: TPC hasn't finished after {HANG_SECONDS} s; reporting a hang")
        results.append({"verdict": "hang"})
        rest = sources[done + 1:]
        if rest:
            more = os.path.join(workdir, "rest")
            os.makedirs(more)
            results += run_batch(tools, disk, rest, more, first + done + 1, coverage)
    return results


def wait_batch(m, names, timeout=60):
    """Waits for a batch file that prints COMPILING <name> before each probe
    to print PROBES DONE. Returns None, or the name of the probe whose compile
    hasn't finished HANG_SECONDS after it started. Raises if nothing moves on
    for `timeout` seconds otherwise, or a compiled program never finishes."""
    last, since = None, time.time()
    while True:
        rows = m.screen()
        text = "\n".join(rows)
        if "PROBES DONE" in text:
            return None
        marks = re.findall(r"^(COMPILING|RUNNING) (P\d{7})$", text, re.M)
        mark = marks[-1] if marks else None
        if mark != last:
            last, since = mark, time.time()
        elif mark and mark[0] == "COMPILING" and mark[1] in names and time.time() - since > HANG_SECONDS:
            return mark[1]
        elif time.time() - since > timeout:
            raise TimeoutError(f"waiting for PROBES DONE; screen:\n" + text)
        time.sleep(0.2)


def tpc_range(tools, disk, workdir):
    """The linear addresses of TPC's load image on the reference machine."""
    d = os.path.join(workdir, "calibrate")
    os.makedirs(d)
    floppy = os.path.join(d, "fd.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    # A:\P\PSP00000.COM is as long as C:\BP\BIN\TPC.EXE.
    assert len("A:\\P\\PSP00000.COM") == len(TPC)
    tools.mtool("mmd", "-i", floppy, "::/P")
    with open(os.path.join(d, "PSP00000.COM"), "wb") as f:
        f.write(PSP_COM)
    tools.mtool("mcopy", "-i", floppy, os.path.join(d, "PSP00000.COM"), "::/P/")
    with open(os.path.join(d, "RUN.BAT"), "wb") as f:
        f.write(b"@ECHO OFF\r\nA:\r\nCD \\P\r\nA:\\P\\PSP00000 > A:\\PSP.TXT\r\nCD \\\r\nECHO PROBES DONE\r\n")
    tools.mtool("mcopy", "-i", floppy, os.path.join(d, "RUN.BAT"), "::/")
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
    """Compiles each source and returns (machine info, results). A source is
    the program as bytes, or a tuple that adds extra files beside it (such
    as include files) and options for TPC's command line; see unpack.

    coverage: path to the coverage plugin, to record coverage.
    coverage_range: (lo, hi) linear addresses to count coverage in; default:
        all of TPC's load image.
    """
    jobs = jobs or os.cpu_count() or 1
    size = max(1, min(BATCH_SIZE, -(-len(sources) // jobs)))  # Spread over all machines.
    batches = batches_of(sources, size)
    with tempfile.TemporaryDirectory() as work:
        info = machine_info(tools, disk, work)
        if coverage:
            coverage = {"plugin": coverage, "range": coverage_range or tpc_range(tools, disk, work)}

        def one(i):
            d = os.path.join(work, f"batch{i}")
            os.makedirs(d)
            first, batch = batches[i]
            log(f"batch {i + 1}/{len(batches)}: {len(batch)} probes")
            return run_batch(tools, disk, [sources[n] for n in batch], d, first=first, coverage=coverage)

        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            results = in_order(len(sources), batches, pool.map(one, range(len(batches))))
    return info, results


def batches_of(sources, size):
    """[(first, [index, ...]), ...]: batches of at most `size` sources, those
    with an FPU apart from those without. `first` numbers the batch's probes,
    which stay in the sources' order."""
    out = []
    for fpu in (True, False):
        chosen = [n for n, s in enumerate(sources) if has_fpu(s) == fpu]
        out += [(chosen[i], chosen[i:i + size]) for i in range(0, len(chosen), size)]
    return out


def in_order(count, batches, batch_results):
    """The results of batches_of's batches, in the sources' order."""
    results = [None] * count
    for (_, batch), got in zip(batches, batch_results):
        for n, result in zip(batch, got):
            results[n] = result
    return results


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
