"""Tools installed on the host (see README.md), found on PATH.

Bazel actions run with a minimal PATH, so this rule looks the tool up on the
user's PATH and exposes a wrapper that calls it by absolute path.
"""

def _host_tool_impl(rctx):
    rctx.getenv("PATH")  # Look the tool up again whenever PATH changes.
    path = rctx.which(rctx.attr.program)
    if not path:
        fail("%s not found on PATH. Install it as described in README.md." % rctx.attr.program)
    rctx.file("tool", "#!/bin/sh\nexec '%s' \"$@\"\n" % path, executable = True)
    rctx.file("BUILD.bazel", 'exports_files(["tool"], visibility = ["//visibility:public"])\n')

host_tool = repository_rule(
    implementation = _host_tool_impl,
    attrs = {
        "program": attr.string(mandatory = True, doc = "Name of the program on PATH."),
    },
)
