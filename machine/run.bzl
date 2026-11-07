"""A `bazel run` target that boots a disk image on the reference machine."""

def _machine_run_impl(ctx):
    script = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.write(script, is_executable = True, content = """#!/bin/sh
exec /usr/bin/python3 -B -s {run} --qemu {qemu} --disk {disk} "$@"
""".format(
        run = ctx.file._run.short_path,
        qemu = ctx.executable._qemu.short_path,
        disk = ctx.file.disk.short_path,
    ))
    files = [ctx.file.disk, ctx.file._run, ctx.executable._qemu] + ctx.files._lib
    return DefaultInfo(executable = script, runfiles = ctx.runfiles(files = files))

machine_run = rule(
    implementation = _machine_run_impl,
    executable = True,
    attrs = {
        "disk": attr.label(allow_single_file = True, mandatory = True),
        "_run": attr.label(default = "run.py", allow_single_file = True),
        "_lib": attr.label_list(default = ["qmp.py"], allow_files = True),
        "_qemu": attr.label(
            default = "//third_party/qemu:qemu-system-i386",
            executable = True,
            cfg = "exec",
            allow_single_file = True,
        ),
    },
)
