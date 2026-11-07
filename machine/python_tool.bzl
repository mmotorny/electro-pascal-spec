"""`bazel run` targets for Python scripts that run with the system Python."""

def _python_tool_impl(ctx):
    targets = ctx.attr.data + ctx.attr.srcs
    args = [ctx.expand_location(a, targets) for a in ctx.attr.fixed_args]
    script = ctx.actions.declare_file(ctx.label.name + ".sh")
    ctx.actions.write(script, is_executable = True, content = "#!/bin/sh\nexec /usr/bin/python3 -B -s %s %s \"$@\"\n" % (
        ctx.file.main.short_path,
        " ".join(["'%s'" % a for a in args]),
    ))
    files = [ctx.file.main] + ctx.files.srcs + ctx.files.data
    runfiles = ctx.runfiles(files = files)
    for t in ctx.attr.data:
        runfiles = runfiles.merge(t[DefaultInfo].default_runfiles)
    return DefaultInfo(executable = script, runfiles = runfiles)

python_tool = rule(
    implementation = _python_tool_impl,
    executable = True,
    doc = "Runs `main` with `fixed_args` (which may use $(rootpath ...)) and then the command line.",
    attrs = {
        "main": attr.label(allow_single_file = [".py"], mandatory = True),
        "srcs": attr.label_list(allow_files = [".py"]),
        "data": attr.label_list(allow_files = True),
        "fixed_args": attr.string_list(),
    },
)

python_test = rule(
    implementation = _python_tool_impl,
    test = True,
    doc = "A test that runs `main` with `fixed_args`; it passes if `main` exits with 0.",
    attrs = {
        "main": attr.label(allow_single_file = [".py"], mandatory = True),
        "srcs": attr.label_list(allow_files = [".py"]),
        "data": attr.label_list(allow_files = True),
        "fixed_args": attr.string_list(),
    },
)
