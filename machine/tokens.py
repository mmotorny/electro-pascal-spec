"""Captures the tokens TPC's scanner hands to its parser, for each source.

Usage: bazel run //machine:tokens -- file ... [--out x.json]

Each file is a Pascal source, or a spec case (*.yaml), whose source is used.

Runs TPC on the reference machine like probe.py (whose floppy layout, file
names and verdict parsing it shares), with QEMU's gdbstub and breakpoints
where the scanner hands over a token. Each token is reported in the form of
a spec case's tokens (see spec/case.schema.yaml): a kind, or a kind mapped
to its value. The compiled programs aren't run.

Prints one line per file, or with --out writes JSON: {"machine": ...,
"results": [{"source": path, "verdict": ..., "tokens": [...]}, ...]}.
"""

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import struct
import sys
import tempfile
import threading

import probe
import qmp
from gdbremote import GdbRemote

# --- What this tool knows about TPC.EXE --------------------------------------
#
# Facts about TPC's internals, needed to watch its scanner: where in its load
# image to stop, where in its data segment the token is, and how it numbers
# token kinds. They hold only for the TPC.EXE whose SHA-256 spec/MACHINE.json
# records, which run() checks first.

# Paragraph where TPC's load image starts when run from probe.py's batch file.
LOAD_SEG = 0x4B8
# Breakpoints, as offsets in the load image (TPC's code segment starts there).
ENTRY = 0x0000            # TPC starts.
SCAN_EXIT = 0x8301        # The scanner has a token; its kind is stored.
RESCAN_EXIT = 0x8524      # A caret token was scanned again as a character string.
# Variables in TPC's data segment.
DS_WINDOW = (0x2C60, 0x2FA0)  # Covers all of them; read in one go.
V_FILEREC = 0x2C78        # Pointer to the current file's record: +2 line number (word),
                          # +0x12 name length (byte), +0x13 name.
V_CONSTTYPE = 0x2CA4      # Type of a constant token: T_* below.
V_START = 0x2D4C          # Pointer to the token's first character in the line buffer.
V_KIND = 0x2D5C           # The token's kind (byte).
V_LINEBUF = 0x2E32        # The current line.
V_IDENT = 0x2F02          # An identifier: length byte, then its characters as written.
V_VALUE = 0x2F42          # A constant's value: a 32-bit integer, a character, or a
                          # pointer to a length-prefixed string.
T_INTEGER, T_REAL, T_STRING, T_CHAR = 0x152, 0xF2, 0xBA, 0x1CE
# Token kinds.
IDENT_KIND = 0x01
CONST_KIND = 0x02
SYMBOLS = {
    0x03: "PLUS", 0x04: "MINUS", 0x05: "STAR", 0x06: "SLASH", 0x07: "EQ",
    0x08: "NE", 0x09: "GT", 0x0A: "LT", 0x0B: "GE", 0x0C: "LE",
    0x0D: "LPAREN", 0x0E: "RPAREN", 0x0F: "LBRACKET", 0x10: "RBRACKET",
    0x11: "DOT", 0x12: "COMMA", 0x13: "COLON", 0x14: "SEMI", 0x15: "CARET",
    0x16: "ASSIGN", 0x17: "DOTDOT", 0x18: "AT",
    # Kinds the parser asks for in some contexts; each stands for one text.
    0x19: "SLASH",  # `/` inside an inline(...) list.
    0x1A: "EQ",     # `=` while the type of a typed constant is parsed.
}
# Reserved words have kinds of their own, which TPC keeps in a table in its
# load image: entries of a 2-byte link, the kind, the length and the word.
KEYWORD_TABLE = (0x8D74, 0x8F24)
# The built-in assembler, which reads asm blocks with a scanner of its own. Its
# code segment starts this many paragraphs into the load image.
ASM_SEG = 0x0C97
# Breakpoints, as offsets in that segment.
ASM_STATEMENT = 0x0006    # The assembler starts on a statement.
ASM_EXIT = 0x07F8         # Its scanner has a token; DH is the token's kind.
# The scanner's state, in the assembler's stack frame, as offsets from BP.
A_TEXT = -0x12            # Far pointer to the text being read.
A_START = -0x14           # Offset of the token's first character.
A_CLASS = -0x19           # What the raw token is: A_SYMBOL, A_WORD or A_STRING.
A_SYMBOL, A_WORD, A_STRING = 0, 1, 2
A_RAW = -0x6C             # A symbol: length byte, then its character.
A_UPPER = -0x8E           # A word in upper case: length byte, then the characters.
A_VALUE = -0x36           # A number's value: 32 bits.
A_CHARS = -0x10E          # A string's characters: length byte, then the characters.
A_FRAME = -0x110          # Covers all of them.
# Kinds the assembler's scanner gives tokens.
A_END = 0x3B              # The statement has ended.
A_INSTRUCTION = 0x41
A_NUMBER = 0x64           # Strings too, which are numbers outside db.
A_IDENT = 0x6B            # A Pascal identifier.
A_FIRST = 0x01            # The first word of a statement isn't an instruction.
A_RESERVED = set(range(0x43, 0x51)) | {0x65, 0x66}  # Registers, operators, sizes.
# Where probe.machine_info and spec/MACHINE.json keep TPC.EXE's hash.
TPC_EXE = "BP\\BIN\\TPC.EXE"

# -----------------------------------------------------------------------------


def reserved_words(tools, disk, workdir):
    """{kind: WORD}, read from the reference disk's TPC.EXE."""
    path = os.path.join(workdir, "TPC.EXE")
    tools.mtool("mcopy", "-n", "-i", f"{disk}@@{probe.PARTITION_OFFSET}", "::/BP/BIN/TPC.EXE", path)
    with open(path, "rb") as f:
        data = f.read()
    image = data[int.from_bytes(data[8:10], "little") * 16:]
    words, i = {}, KEYWORD_TABLE[0]
    while i < KEYWORD_TABLE[1]:
        kind, n = image[i + 2], image[i + 3]
        name = image[i + 4:i + 4 + n].decode("ascii")
        if not (name.isalpha() and name.isupper()):
            raise RuntimeError(f"unexpected reserved word table entry {name!r}")
        words[kind] = name
        i += 4 + n
    return words


class Capture:
    """Handles the gdbstub of one machine; collects raw tokens per TPC run."""

    def __init__(self, sock_path):
        self.runs = []
        self.error = None
        self._gdb = GdbRemote(sock_path)
        base = LOAD_SEG * 16
        self._entry, self._scan, self._rescan = base + ENTRY, base + SCAN_EXIT, base + RESCAN_EXIT
        asm = base + ASM_SEG * 16
        self._ds = None
        self._statement = []  # The current asm statement's tokens.
        for a in (self._entry, self._scan, self._rescan, asm + ASM_STATEMENT, asm + ASM_EXIT):
            self._gdb.set_breakpoint(a)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._gdb.cont()
        self._thread.start()

    def close(self):
        self._gdb.close()

    def _loop(self):
        try:
            while True:
                self._gdb.wait_stop()
                regs = self._gdb.registers()
                try:
                    self._handle(regs)
                except (EOFError, OSError):
                    raise  # The machine has gone, as after a hang: the capture just ends.
                except Exception as e:  # Keep the machine going; reported by the caller.
                    if self.error is None:
                        self.error = e
                self._gdb.cont(regs["cs"] * 16 + (regs["eip"] & 0xFFFF))
        except (EOFError, OSError):
            pass
        except Exception as e:
            self.error = e
            self._gdb.close()

    def _handle(self, regs):
        cs, ip = regs["cs"], regs["eip"] & 0xFFFF
        if cs == LOAD_SEG + ASM_SEG and self.runs:
            self._handle_asm(regs, ip)
            return
        if cs != LOAD_SEG:
            return  # Only TPC runs at this place: the batch runs nothing else.
        if ip == ENTRY:
            self.runs.append([])
            return
        if not self.runs:
            return
        self._ds = regs["ds"]
        ds = regs["ds"] * 16
        lo, hi = DS_WINDOW
        w = self._gdb.read_memory(ds + lo, hi - lo)
        word = lambda off: struct.unpack_from("<H", w, off - lo)[0]
        kind = w[V_KIND - lo] if ip == SCAN_EXIT else regs["eax"] & 0xFF
        record = self._gdb.read_memory(ds + word(V_FILEREC), 0x13 + 80)
        start, end = word(V_START), regs["esi"] & 0xFFFF
        text = w[start - lo:end - lo].decode("latin-1") if V_LINEBUF <= start <= end <= V_LINEBUF + 0x80 else None
        token = {"kind": kind, "text": text, "line": struct.unpack_from("<H", record, 2)[0],
                 "column": start - V_LINEBUF + 1, "file": record[0x13:0x13 + record[0x12]].decode("latin-1")}
        if kind == CONST_KIND:
            t, value = word(V_CONSTTYPE), w[V_VALUE - lo:V_VALUE - lo + 10]
            if t == T_INTEGER:
                token["integer"] = struct.unpack_from("<i", value)[0]
            elif t == T_CHAR:
                token["string"] = chr(value[0])
            elif t == T_STRING:
                s = self._gdb.read_memory(ds + struct.unpack_from("<H", value)[0], 256)
                token["string"] = s[1:1 + s[0]].decode("latin-1")
            elif t != T_REAL:
                raise RuntimeError(f"constant of unknown type {t:#x}")
        elif kind == IDENT_KIND:
            n = w[V_IDENT - lo]
            token["ident"] = w[V_IDENT + 1 - lo:V_IDENT + 1 - lo + n].decode("latin-1")
        if ip == RESCAN_EXIT:
            self.runs[-1][-1] = token  # Replaces the caret token the parser just got.
        else:
            self.runs[-1].append(token)

    def _handle_asm(self, regs, ip):
        """A token of an asm block. The assembler asks for the end of a
        statement again after it has had it: only the first counts, and a
        statement with no other token gives none."""
        if ip == ASM_STATEMENT:
            self._statement = []
            return
        if ip != ASM_EXIT or self._ds is None:
            return
        frame = (regs["ss"] * 16 + (regs["ebp"] & 0xFFFF) + A_FRAME) & 0xFFFFF
        f = self._gdb.read_memory(frame, -A_FRAME)
        at = lambda off: off - A_FRAME
        word = lambda off: struct.unpack_from("<H", f, at(off))[0]
        counted = lambda off: f[at(off) + 1:at(off) + 1 + f[at(off)]].decode("latin-1")
        kind, cls = (regs["edx"] >> 8) & 0xFF, f[at(A_CLASS)]
        if kind == A_END:  # Whatever the class: it can be the last token's.
            if not self._statement or self._statement[-1]["asm"] == "ASM_END":
                return
            token = {"asm": "ASM_END"}
        elif cls == A_STRING and kind == A_NUMBER:
            token = {"asm": "ASM_STRING", "string": counted(A_CHARS)}
        elif cls == A_SYMBOL and kind == f[at(A_RAW) + 1]:
            token = {"asm": "ASM_SYMBOL", "string": chr(kind)}
        elif cls == A_WORD and kind == A_NUMBER:
            token = {"asm": "ASM_NUMBER", "integer": struct.unpack_from("<I", f, at(A_VALUE))[0]}
        elif cls == A_WORD and kind == A_IDENT:
            name = counted(A_UPPER)  # A_RAW loses its & in a way that garbles it.
            token = {"asm": "ASM_IDENT", "ident": name[1:] if name.startswith("&") else name}
        elif cls == A_WORD and kind in {A_INSTRUCTION, A_FIRST} | A_RESERVED:
            name = {A_INSTRUCTION: "ASM_INSTRUCTION", A_FIRST: "ASM_WORD"}.get(kind, "ASM_RESERVED")
            token = {"asm": name, "ident": counted(A_UPPER)}
        else:
            raise RuntimeError(f"asm token of kind {kind:#x}, class {cls} this tool doesn't know")
        record = self._gdb.read_memory(self._ds * 16 + DS_WINDOW[0], DS_WINDOW[1] - DS_WINDOW[0])
        rec = self._gdb.read_memory(self._ds * 16 + struct.unpack_from("<H", record, V_FILEREC - DS_WINDOW[0])[0], 0x13 + 80)
        text_seg = word(A_TEXT + 2)
        token.update(line=struct.unpack_from("<H", rec, 2)[0], file=rec[0x13:0x13 + rec[0x12]].decode("latin-1"),
                     column=word(A_START) - V_LINEBUF + 1 if text_seg == self._ds else None, text=None)
        if token["asm"] == "ASM_END":
            token["column"] = None  # Often still the position of the token before.
        self._statement.append(token)
        self.runs[-1].append(token)


def spec_token(token, words):
    """A raw token in the form of a case's tokens."""
    if "asm" in token:
        value = next((token[k] for k in ("ident", "integer", "string") if k in token), None)
        return token["asm"] if value is None else {token["asm"]: value}
    kind = token["kind"]
    if kind == IDENT_KIND:
        return {"IDENT": token["ident"].upper()[:63]}
    if kind == CONST_KIND:
        if "integer" in token:
            return {"INTEGER": token["integer"]}
        if "string" in token:
            return {"STRING": token["string"]}
        return {"REAL": token["text"]}
    if kind in SYMBOLS:
        return SYMBOLS[kind]
    if kind in words:
        return words[kind]
    raise RuntimeError(f"token {token['text']!r} at {token['line']}:{token['column']} "
                       f"has a kind ({kind:#x}) this tool doesn't know")


def run_batch(tools, disk, sources, workdir, first=0):
    """Compiles up to probe.BATCH_SIZE sources on one machine, capturing raw tokens."""
    os.makedirs(workdir, exist_ok=True)
    floppy = os.path.join(workdir, "probes.img")
    tools.mtool("mformat", "-C", "-f", "1440", "-i", floppy, "::")
    names = [probe.probe_name(first + n) for n in range(len(sources))]
    probe.lay_out(tools, floppy, workdir, names, sources)
    script = ["@ECHO OFF", "A:"]
    for name, source in zip(names, sources):
        script += [
            f"CD \\P\\{name}",
            *probe.precompile(source),
            f"ECHO COMPILING {name}",
            probe.command(name, source),
            f"IF ERRORLEVEL 1 ECHO 1> {name}.ERL",
            f"IF EXIST {name}.EXE DEL {name}.EXE",
        ]
    script += ["CD \\", "ECHO PROBES DONE"]
    with open(os.path.join(workdir, "RUN.BAT"), "wb") as f:
        f.write(("\r\n".join(script) + "\r\n").encode("ascii"))
    tools.mtool("mcopy", "-i", floppy, os.path.join(workdir, "RUN.BAT"), "::/")

    # A short socket path: Unix socket paths are limited to about 100 bytes.
    sockdir = tempfile.mkdtemp(prefix="cap", dir="/tmp")
    sock = os.path.join(sockdir, "gdb")
    m = qmp.Machine(tools.qemu, workdir, disk, floppy=floppy, snapshot=True, floppy_writable=True,
                    boot="c", extra_args=["-chardev", f"socket,id=gdb0,path={sock},server=on,wait=off",
                                          "-gdb", "chardev:gdb0", "-S"])
    cap = None
    try:
        cap = Capture(sock)
        m.wait_prompt("C:\\>", timeout=60)
        m.type("A:\\RUN\n")
        hung = probe.wait_batch(m, names)
    finally:
        m.quit()
        if cap:
            cap.close()
        shutil.rmtree(sockdir, ignore_errors=True)
    if cap.error:
        raise cap.error
    done = names.index(hung) if hung else len(names)
    # Each probe's files to compile first make TPC runs of their own, before
    # the probe's: keep only the probe's.
    runs, at = [], 0
    for source in sources[:done + bool(hung)]:
        at += len(probe.unpack(source)[3])
        runs.append(cap.runs[at] if at < len(cap.runs) else None)
        at += 1
    if at != len(cap.runs) or None in runs:
        raise RuntimeError(f"saw {len(cap.runs)} TPC runs where {at} were due; has TPC's load "
                           "address changed?")
    # Every token takes up source text, so two in a row at the same place mean
    # that a breakpoint hit was seen twice.
    for n, tokens in enumerate(cap.runs):
        for a, b in zip(tokens, tokens[1:]):
            if (a["line"], a["column"], a["file"]) == (b["line"], b["column"], b["file"]):
                raise RuntimeError(f"file {first + n}: token at {a['line']}:{a['column']} seen twice")

    out = os.path.join(workdir, "out")
    os.makedirs(out)
    tools.mtool("mcopy", "-s", "-n", "-i", floppy, "::/P", out + "/")
    results = []
    for name, tokens in zip(names[:done], runs):
        with open(os.path.join(out, "P", name, name + ".OUT"), "rb") as f:
            output = f.read().decode("cp437")
        # TPC adds the compile time when it's 0.1 s or more, which breakpoints
        # make likely. Drop it: it isn't deterministic.
        output = re.sub(r"(\d+ lines), \d+\.\d+ seconds,", r"\1,", output)
        result = probe.parse_output(output, name + ".PAS")
        result["raw_tokens"] = tokens
        results.append(result)
    if hung:
        # The tokens TPC's scanner delivered before it stopped making progress.
        qmp.log(f"{hung}: TPC hasn't finished after {probe.HANG_SECONDS} s; reporting a hang")
        results.append({"verdict": "hang", "raw_tokens": runs[done]})
        rest = sources[done + 1:]
        if rest:
            results += run_batch(tools, disk, rest, os.path.join(workdir, "rest"), first + done + 1)
    return results


def run(tools, disk, sources, tpc_sha256, jobs=None):
    """Compiles each source (bytes, or (bytes, {file name: bytes}) as for
    probe.run) and returns (machine info, results). Each result is probe.py's
    verdict plus "tokens", in the form of a case's, from every file read.

    tpc_sha256: the SHA-256 of the TPC.EXE this tool's facts hold for, as
    spec/MACHINE.json records it. Raises if the reference disk's differs."""
    jobs = jobs or os.cpu_count() or 1
    size = max(1, min(probe.BATCH_SIZE, -(-len(sources) // jobs)))
    batches = [sources[i:i + size] for i in range(0, len(sources), size)]
    with tempfile.TemporaryDirectory(prefix="cap") as work:
        info = probe.machine_info(tools, disk, work)
        found = info["sha256"][TPC_EXE]
        if found != tpc_sha256:
            raise RuntimeError(f"the reference disk's TPC.EXE has SHA-256 {found}, but what this tool "
                               f"knows about TPC's internals holds only for {tpc_sha256}")
        words = reserved_words(tools, disk, work)

        def one(i):
            d = os.path.join(work, f"b{i}")
            os.makedirs(d)
            qmp.log(f"batch {i + 1}/{len(batches)}: {len(batches[i])} files")
            for attempt in range(3):
                try:
                    return run_batch(tools, disk, batches[i], os.path.join(d, str(attempt)), first=i * size)
                except (RuntimeError, TimeoutError) as e:
                    if attempt == 2:
                        raise
                    qmp.log(f"batch {i + 1}: {e}; retrying")

        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            results = [r for batch in pool.map(one, range(len(batches))) for r in batch]
    for result in results:
        result["tokens"] = [spec_token(t, words) for t in result.pop("raw_tokens")]
    return info, results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--mtools", required=True)
    parser.add_argument("--disk", required=True)
    parser.add_argument("--machine", required=True, help="spec/MACHINE.json, which names the TPC.EXE")
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--out", help="JSON file to write; default: one line per file on stdout")
    parser.add_argument("sources", nargs="+", help="Pascal sources or spec cases")
    args = parser.parse_args()
    base = os.environ.get("BUILD_WORKING_DIRECTORY", "")
    sources = []
    for path in args.sources:
        with open(os.path.join(base, path), "rb") as f:
            data = f.read()
        if path.endswith(".yaml"):
            import yaml
            case = yaml.safe_load(data)
            data = case["source"].encode("latin-1")
            if case.get("files") or case.get("options"):
                files = {k: v.encode("latin-1") for k, v in (case.get("files") or {}).items()}
                data = (data, files, case.get("options") or [], case.get("precompile") or [])
        sources.append(data)
    with open(args.machine) as f:
        tpc_sha256 = json.load(f)["sha256"][TPC_EXE]
    tools = probe.Tools(os.path.abspath(args.qemu), os.path.abspath(args.mtools))
    info, results = run(tools, os.path.abspath(args.disk), sources, tpc_sha256, args.jobs)
    if args.out:
        with open(os.path.join(base, args.out), "w") as f:
            json.dump({"machine": info, "results": [dict(source=p, **r) for p, r in zip(args.sources, results)]},
                      f, indent=1)
            f.write("\n")
        return
    for path, result in zip(args.sources, results):
        tokens = ", ".join(t if isinstance(t, str) else "%s: %r" % next(iter(t.items())) for t in result["tokens"])
        print(f"{path}: {tokens}")


if __name__ == "__main__":
    main()
