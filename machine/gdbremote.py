"""A minimal GDB remote serial protocol client for QEMU's gdbstub (i386)."""

import socket
import struct


class GdbRemote:
    def __init__(self, path, timeout=None):
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.settimeout(timeout)
        self._sock.connect(path)
        self._buf = b""
        # Disable acks to halve the round trips.
        reply = self.request("QStartNoAckMode")
        self._noack = reply == "OK"

    def close(self):
        try:
            self._sock.close()
        except OSError:
            pass

    def _recv(self):
        data = self._sock.recv(65536)
        if not data:
            raise EOFError("gdbstub closed")
        self._buf += data

    def _send(self, payload):
        csum = sum(payload.encode("latin-1")) & 0xFF
        self._sock.sendall(b"$" + payload.encode("latin-1") + b"#%02x" % csum)

    def _packet(self):
        while True:
            # Skip acks and stray bytes.
            while self._buf and self._buf[:1] != b"$":
                self._buf = self._buf[1:]
            i = self._buf.find(b"#")
            if i >= 0 and len(self._buf) >= i + 3:
                payload = self._buf[1:i]
                self._buf = self._buf[i + 3:]
                if not getattr(self, "_noack", False):
                    self._sock.sendall(b"+")
                return payload.decode("latin-1")
            self._recv()

    def request(self, payload):
        self._send(payload)
        return self._packet()

    def send_only(self, payload):
        self._send(payload)

    def wait_stop(self):
        """Waits for a stop reply after 'c'."""
        while True:
            p = self._packet()
            if p and p[0] in "TS":
                return p
            if p and p[0] in "WX":
                raise EOFError("target exited: " + p)

    # Commands.

    def set_breakpoint(self, addr):
        r = self.request(f"Z0,{addr:x},1")
        if r != "OK":
            raise RuntimeError(f"breakpoint at {addr:#x}: {r!r}")

    def clear_breakpoint(self, addr):
        self.request(f"z0,{addr:x},1")

    def cont(self, at=None):
        """Continues; `at` is a breakpoint address the target is stopped on."""
        if at is not None:
            # Step off the breakpoint. A step can end without executing the
            # instruction (QEMU may exit the CPU loop early, more likely under
            # load), which would make the breakpoint hit twice: step until the
            # program counter moves.
            self.clear_breakpoint(at)
            for _ in range(1000):
                self.send_only("s")
                self.wait_stop()
                regs = self.registers()
                if regs["cs"] * 16 + (regs["eip"] & 0xFFFF) != at:
                    break
            else:
                raise RuntimeError(f"can't step off {at:#x}")
            self.set_breakpoint(at)
        self.send_only("c")

    def read_memory(self, addr, size):
        out = b""
        while size > 0:
            n = min(size, 2048)
            r = self.request(f"m{addr:x},{n:x}")
            if r.startswith("E"):
                raise RuntimeError(f"read {addr:#x}: {r}")
            out += bytes.fromhex(r)
            addr += n
            size -= n
        return out

    def write_memory(self, addr, data):
        r = self.request(f"M{addr:x},{len(data):x}:{data.hex()}")
        if r != "OK":
            raise RuntimeError(f"write {addr:#x}: {r}")

    def registers(self):
        """i386 registers: eax ecx edx ebx esp ebp esi edi eip eflags cs ss ds es fs gs."""
        r = bytes.fromhex(self.request("g")[:16 * 8])
        names = ["eax", "ecx", "edx", "ebx", "esp", "ebp", "esi", "edi",
                 "eip", "eflags", "cs", "ss", "ds", "es", "fs", "gs"]
        return dict(zip(names, struct.unpack("<16I", r)))

    def interrupt(self):
        self._sock.sendall(b"\x03")
