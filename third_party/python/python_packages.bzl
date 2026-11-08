"""Python packages for the tools, installed with the system Python's pip.

Installs the latest release of each package (and what it needs) into a
folder that python_tool puts on PYTHONPATH. Fetched again when Bazel
refetches repositories, so the packages track their latest releases.
"""

def _python_packages_impl(rctx):
    result = rctx.execute(
        ["/usr/bin/python3", "-m", "pip", "install", "--quiet", "--disable-pip-version-check",
         "--no-input", "--target", "site"] + rctx.attr.packages,
        timeout = 600,
    )
    if result.return_code:
        fail("pip install %s failed:\n%s%s" % (" ".join(rctx.attr.packages), result.stdout, result.stderr))
    rctx.file("BUILD.bazel", """filegroup(
    name = "site",
    srcs = glob(["site/**"], exclude = ["site/**/__pycache__/**"]),
    visibility = ["//visibility:public"],
)
""")

python_packages = repository_rule(
    implementation = _python_packages_impl,
    attrs = {
        "packages": attr.string_list(mandatory = True, doc = "Package names for pip, unversioned."),
    },
)
