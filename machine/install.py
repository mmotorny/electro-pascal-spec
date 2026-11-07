"""Builds the reference machine's hard disk image.

MS-DOS 6.22 and Borland Pascal 7.01 are installed by their own installers,
with default options, inside QEMU. This script plays the user: it reads the
screen, presses keys and swaps floppies.

The MS-DOS 6.22 Upgrade refuses to install on an empty disk, so the disk is
first partitioned and formatted with FDISK and FORMAT /S from Setup disk 1.
Setup then upgrades that system. /G skips making an uninstall floppy.
"""

import argparse
import glob
import os
import subprocess
import tempfile
import time

from qmp import Machine, log

DISK_SIZE = 64 * 1024 * 1024


def extract_disks(archive, dest):
    """Extracts the floppy images (Disk*.img) from an archive."""
    os.makedirs(dest)
    subprocess.run(["/usr/bin/tar", "-xf", archive, "-C", dest, "--include", "*/Disk*.img"],
                   check=True)
    disks = {}
    for path in glob.glob(os.path.join(dest, "*", "Disk*.img")):
        number = int(os.path.basename(path)[4:-4])
        disks[number] = path
    return disks


def leave_setup(m):
    """Quits MS-DOS Setup, which disk 1 starts on boot, for the A:\\> prompt."""
    m.wait(r"Welcome to Setup", timeout=60)
    m.key("f3")
    m.wait(r"F3")
    m.key("f3")
    m.wait_prompt("A:\\>")


def install_msdos(m, disks):
    log("MS-DOS: partitioning")
    leave_setup(m)
    m.type("FDISK\n")
    m.wait(r"Enter choice:")
    m.key("ret")  # 1. Create DOS partition or Logical DOS Drive
    m.wait(r"Create Primary DOS Partition")
    m.key("ret")  # 1. Create Primary DOS Partition
    m.wait(r"maximum available size")
    m.key("ret")  # Y: all of the disk, active
    m.wait(r"Press any key when ready", timeout=300)
    m.key("ret")  # Restarts from disk 1.

    log("MS-DOS: formatting")
    leave_setup(m)
    m.type("FORMAT C: /S\n")
    m.wait(r"Proceed with Format")
    m.type("Y\n")
    m.wait(r"Volume label", timeout=300)
    m.key("ret")  # No label.
    m.wait_prompt("A:\\>")

    log("MS-DOS: running Setup")
    m.type("SETUP /G\n")
    m.wait(r"Welcome to Setup", timeout=60)
    m.key("ret")
    m.wait(r"Setup will use the following system settings")
    m.key("ret")
    m.wait(r"The following programs can be installed")
    m.key("ret")
    m.wait(r"To install MS-DOS 6.22 files now, press Y")
    m.key("y")
    for n in (2, 3):
        m.wait(rf"Setup Disk #{n}", timeout=600)
        m.insert_floppy(disks[n])
        m.key("ret")
    m.wait(r"Remove disks from all floppy disk drives", timeout=600)
    m.eject_floppy()
    m.key("ret")
    m.wait(r"MS-DOS Setup Complete", timeout=120)
    m.key("ret")  # Restarts from the hard disk.
    m.wait_prompt("C:\\>", timeout=120)

    # Setup saved the "previous" DOS in C:\OLD_DOS.1. There was none, so
    # remove the folder with Setup's own tool, as a user would after upgrading.
    log("MS-DOS: removing OLD_DOS.1")
    m.type("C:\\DOS\\DELOLDOS\n")
    m.wait(r"To continue with DELOLDOS, press Y")
    m.key("y")
    m.wait(r"DELOLDOS has finished removing old DOS files")
    m.key("ret")
    m.wait_prompt("C:\\>")


def install_bp(m, disks):
    log("Borland Pascal: running INSTALL")
    m.insert_floppy(disks[1])
    m.type("A:\n")
    m.wait_prompt("A:\\>")
    m.type("INSTALL\n")
    m.wait(r"Press ENTER to continue", timeout=60)
    m.key("ret")
    m.wait(r"Enter the SOURCE drive")
    m.key("ret")  # A
    m.wait(r"Start Installation")
    while "Press ENTER to begin Installing" not in "\n".join(m.screen()):
        m.key("down")
    m.key("ret")

    # Answer prompts until done. Without Windows installed, INSTALL warns that
    # it can't create the Windows group or find the BWCC.DLL directory. Its
    # dialogs overlay the screen, so other text can sit between their lines.
    notices = r"unable to gain access to the Windows|unable to locate the directory you"
    wrong_disk = r"Wrong disk in drive A:"
    wrong_disk_count = 0
    while True:
        match = m.wait(rf"(?s)Please insert disk.*?Disk #(\d+)|{notices}|{wrong_disk}"
                       r"|installation is now complete", timeout=120)
        if match.group(1):
            n = int(match.group(1))
            log(f"Borland Pascal: disk {n}")
            m.insert_floppy(disks[n])
            # The drive doesn't report disk changes, so DOS assumes a disk
            # read in the last 2 seconds is still in the drive and serves its
            # cached directory. Wait that out before INSTALL reads the disk.
            time.sleep(3)
            m.key("spc")
            m.wait_gone(rf"Disk #{n}\b", timeout=30)
        elif match.group(0) == wrong_disk:
            wrong_disk_count += 1
            if wrong_disk_count > 5:
                raise RuntimeError("INSTALL keeps rejecting the disk")
            log("Borland Pascal: wrong disk reported, retrying")
            time.sleep(3)
            m.key("esc")
            m.wait_gone(wrong_disk, timeout=30)
        elif "complete" in match.group(0):
            break
        else:
            m.key("spc")
            m.wait_gone(match.group(0))
    m.key("spc")  # Opens the README viewer.
    m.wait_gone(r"installation is now complete")
    m.key("esc")
    m.wait_prompt("A:\\>", timeout=60)
    m.eject_floppy()
    m.type("C:\n")
    m.wait_prompt("C:\\>")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qemu", required=True)
    parser.add_argument("--msdos", required=True, help="MS-DOS 6.22 archive")
    parser.add_argument("--bp", required=True, help="Borland Pascal 7.01 archive")
    parser.add_argument("--out", required=True, help="hard disk image to write")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as work:
        msdos = extract_disks(args.msdos, os.path.join(work, "msdos"))
        bp = extract_disks(args.bp, os.path.join(work, "bp"))
        disk = os.path.join(work, "c.img")
        with open(disk, "wb") as f:
            f.truncate(DISK_SIZE)

        m = Machine(args.qemu, work, disk, floppy=msdos[1])
        try:
            install_msdos(m, msdos)
            install_bp(m, bp)
        finally:
            m.quit()
        os.replace(disk, args.out)
    log("done")


if __name__ == "__main__":
    main()
