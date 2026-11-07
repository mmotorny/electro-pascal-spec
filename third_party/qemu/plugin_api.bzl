"""Finds the QEMU plugin header and the glib headers it needs, on the host.

Produces flags.txt with the -I flags for compiling a plugin. Homebrew
installs QEMU's header in its Cellar folder, and glib's under the prefix.
"""

def _qemu_plugin_api_impl(rctx):
    rctx.getenv("PATH")  # Look again whenever PATH changes.
    qemu = rctx.which("qemu-system-i386")
    if not qemu:
        fail("qemu-system-i386 not found on PATH. Install it as described in README.md.")
    cellar = rctx.path(str(qemu.realpath)).dirname.dirname
    prefix = qemu.dirname.dirname
    dirs = [str(cellar) + "/include", str(prefix) + "/include/glib-2.0", str(prefix) + "/lib/glib-2.0/include"]
    for d, f in zip(dirs, ["qemu-plugin.h", "glib.h", "glibconfig.h"]):
        if not rctx.path(d + "/" + f).exists:
            fail("%s not found in %s; is QEMU installed with Homebrew?" % (f, d))
    rctx.file("flags.txt", " ".join(["-I" + d for d in dirs]) + "\n")
    rctx.file("BUILD.bazel", 'exports_files(["flags.txt"], visibility = ["//visibility:public"])\n')

qemu_plugin_api = repository_rule(implementation = _qemu_plugin_api_impl)
