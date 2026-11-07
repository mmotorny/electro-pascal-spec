"""Drives a QEMU PC through QMP: keys, floppy swaps and the text screen."""

import json
import os
import re
import subprocess
import sys
import time

# Characters that need more than their own lowercase key.
_KEYS = {
    " ": ("spc",), "\n": ("ret",), "\\": ("backslash",), "/": ("slash",),
    ".": ("dot",), ",": ("comma",), ";": ("semicolon",), "'": ("apostrophe",),
    "-": ("minus",), "=": ("equal",), ":": ("shift", "semicolon"),
    "*": ("shift", "8"), "(": ("shift", "9"), ")": ("shift", "0"),
    "+": ("shift", "equal"), "$": ("shift", "4"), ">": ("shift", "dot"),
    "<": ("shift", "comma"), "_": ("shift", "minus"), "|": ("shift", "backslash"),
}


# The reference machine: a 486 PC with 16 MB of memory, its clock starting at
# a fixed date, and no network.
MACHINE_ARGS = [
    "-machine", "pc", "-cpu", "486", "-m", "16",
    "-rtc", "base=1994-06-01T12:00:00", "-nic", "none", "-boot", "order=ac",
]


class Machine:
    """A 486 PC with a floppy drive and one IDE hard disk, without a display."""

    def __init__(self, qemu, workdir, hard_disk, floppy=None):
        self._screen_file = os.path.join(workdir, "screen.bin")
        drives = ["-drive", f"if=ide,index=0,format=raw,file={hard_disk}"]
        if floppy:
            drives += ["-drive", f"if=floppy,index=0,format=raw,readonly=on,file={floppy}"]
        else:
            drives += ["-drive", "if=floppy,index=0"]
        self._proc = subprocess.Popen(
            [qemu] + MACHINE_ARGS + [
                "-display", "none", "-monitor", "none", "-serial", "none",
                "-parallel", "none", "-qmp", "stdio"] + drives,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        self._read()
        self.cmd("qmp_capabilities")

    def _read(self):
        while True:
            line = self._proc.stdout.readline()
            if not line:
                raise RuntimeError("QEMU exited")
            msg = json.loads(line)
            if "event" not in msg:
                return msg

    def cmd(self, name, **args):
        self._proc.stdin.write(json.dumps({"execute": name, "arguments": args}).encode() + b"\n")
        self._proc.stdin.flush()
        reply = self._read()
        if "error" in reply:
            raise RuntimeError(f"{name}: {reply['error']['desc']}")
        return reply["return"]

    def quit(self):
        self.cmd("quit")
        self._proc.wait(timeout=30)

    # Input.

    def key(self, *names):
        self.cmd("send-key", keys=[{"type": "qcode", "data": n} for n in names])
        time.sleep(0.05)

    def type(self, text):
        for ch in text:
            keys = _KEYS.get(ch) or (("shift", ch.lower()) if ch.isupper() else (ch,))
            self.key(*keys)

    def insert_floppy(self, image):
        self.cmd("blockdev-change-medium", device="floppy0", filename=image,
                 format="raw", **{"read-only-mode": "read-only"})

    def eject_floppy(self):
        self.cmd("eject", device="floppy0")

    # Output.

    def screen(self):
        """The 80x25 text screen as a list of rows."""
        self.cmd("pmemsave", val=0xB8000, size=80 * 25 * 2, filename=self._screen_file)
        with open(self._screen_file, "rb") as f:
            cells = f.read()[::2]
        text = "".join(chr(c) if 32 <= c < 127 else " " for c in cells)
        return [text[i:i + 80].rstrip() for i in range(0, len(text), 80)]

    def wait(self, pattern, timeout=120):
        """Waits until the screen matches a regular expression."""
        deadline = time.time() + timeout
        while True:
            rows = self.screen()
            match = re.search(pattern, "\n".join(rows))
            if match:
                return match
            if time.time() > deadline:
                raise TimeoutError(f"waiting for {pattern!r}; screen:\n" + "\n".join(rows))
            time.sleep(0.2)

    def wait_gone(self, pattern, timeout=120):
        """Waits until the screen no longer matches a regular expression."""
        deadline = time.time() + timeout
        while re.search(pattern, "\n".join(self.screen())):
            if time.time() > deadline:
                raise TimeoutError(f"waiting for {pattern!r} to go away")
            time.sleep(0.2)

    def wait_prompt(self, prompt, timeout=120):
        """Waits until the last non-blank row is exactly a DOS prompt such as C:\\>."""
        deadline = time.time() + timeout
        while True:
            rows = [r for r in self.screen() if r]
            if rows and rows[-1] == prompt:
                return
            if time.time() > deadline:
                raise TimeoutError(f"waiting for prompt {prompt}; screen:\n" + "\n".join(rows))
            time.sleep(0.2)


def log(msg):
    print(f"[machine] {msg}", file=sys.stderr, flush=True)
