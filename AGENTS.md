# Agent instructions

Read `README.md` first for what this project is, its prerequisites and how to
build it.

## Ground rules

- Keep agent instructions and project knowledge in this file or elsewhere in
  the repo. Don't use agent memory features: they don't carry over between
  machines.
- Keep `README.md` up to date. Whenever a prerequisite (a tool, its version
  or how to install it) or a proprietary input is added, removed or changed,
  update the README in the same change.
- Don't pin tool versions or input hashes. Track the latest releases, and
  record what a result came from alongside the result instead: tool versions
  (such as QEMU) and hashes of the key proprietary files (such as `BPC.EXE`
  and `TURBO.TPL`).
- Don't wrap `bazel run` or `bazel build` commands in shell scripts, aliases
  or make targets. Document the Bazel command itself, in `README.md` for
  people or here for agents.

## Proprietary materials

- Never commit proprietary files: Borland Pascal 7.01, MS-DOS 6.22, Turbo
  Pascal 5.5 and the Turbo Pascal 7.0 manuals.
- Never publish where to get them: no URLs, site names or hints in files,
  comments, error messages, commit messages, issues or PRs.
- Their URLs belong only in the gitignored `user.bazelrc`. After any Bazel
  change, check that `MODULE.bazel.lock` contains none of them.

## Clean room

- The BP 7.01 archive includes Borland's runtime library source. The spec
  describes observable behaviour only. Never copy or paraphrase that source
  into the spec.
- Write the spec in your own words. Never copy prose, examples, syntax
  diagrams or the organisation of the manuals. Exact identifiers,
  declarations and error message strings are fine, since compatibility
  needs them.
- Don't use Borland, Turbo Pascal, Turbo Vision or MS-DOS in project names or
  branding, only to say what the spec describes.
- Put only Borland's own files from the BP disks into the reference install.
  Leave out anything else a copy may contain, such as third-party tools or
  replacement libraries.
