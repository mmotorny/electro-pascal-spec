"""Helpers for files on the reference disk."""

# Byte offset of the C: partition on //machine:disk. FDISK puts it at
# sector 63, after the first track.
PARTITION_OFFSET = 63 * 512

def disk_file(name, path, out):
    """Copies a file off the reference disk, e.g. path = "BP/BIN/TPC.EXE"."""
    native.genrule(
        name = name,
        srcs = ["//machine:disk"],
        outs = [out],
        cmd = "MTOOLS_SKIP_CHECK=1 $(location //third_party/mtools:mtools) -c mcopy -n -i $(location //machine:disk)@@%d ::/%s $@" % (PARTITION_OFFSET, path),
        tools = ["//third_party/mtools:mtools"],
    )
