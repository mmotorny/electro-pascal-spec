"""Boots the reference machine in a QEMU window.

Changes to the disk are thrown away when QEMU exits. Extra arguments are
passed on to QEMU.
"""

import argparse
import os

from qmp import MACHINE_ARGS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--disk", required=True)
    args, extra = parser.parse_known_args()
    qemu = os.path.abspath(args.qemu)
    os.execv(qemu, [qemu] + MACHINE_ARGS + ["-boot", "order=c",
        "-drive", f"if=ide,index=0,format=raw,snapshot=on,file={os.path.abspath(args.disk)}",
        "-drive", "if=floppy,index=0",
    ] + extra)


if __name__ == "__main__":
    main()
