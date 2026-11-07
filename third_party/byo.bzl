"""Bring-your-own files: proprietary inputs that this repo cannot distribute.

The repo records only what each file is. Where to get it is up to each user,
who sets an environment variable to a URL (file:// works for local copies),
usually in user.bazelrc:

    common --repo_env=BP701_URL=file:///path/to/your/copy.7z
"""

def _byo_file_impl(rctx):
    name = getattr(rctx, "original_name", rctx.name)
    url = rctx.getenv(rctx.attr.url_env)
    if not url:
        fail("Missing %s: %s.\nSet %s to its URL (file:// for a local copy), " %
             (name, rctx.attr.description, rctx.attr.url_env) +
             "e.g. in user.bazelrc:\n    common --repo_env=%s=..." % rctx.attr.url_env)
    rctx.download(
        url = url,
        output = rctx.attr.file_name,
    )
    rctx.file("BUILD.bazel", """\
exports_files(["{name}"], visibility = ["//visibility:public"])

filegroup(
    name = "file",
    srcs = ["{name}"],
    visibility = ["//visibility:public"],
)
""".format(name = rctx.attr.file_name))

byo_file = repository_rule(
    implementation = _byo_file_impl,
    attrs = {
        "description": attr.string(mandatory = True, doc = "What the file is, for error messages."),
        "file_name": attr.string(mandatory = True, doc = "Name to save the file under."),
        "url_env": attr.string(mandatory = True, doc = "Environment variable holding the URL."),
    },
)
