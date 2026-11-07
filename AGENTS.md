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

## Spec cases

- A case's `tpc:` and `output:` lines are written only by
  `bazel run //spec:record`, never by hand. Run it after adding or changing
  cases, and keep `bazel test //spec:cases_test` passing.
- When a recorded result disagrees with the spec's text or a case's
  `tokens:` line, the recorded result is right: fix the text or the tokens,
  or record the behaviour as a quirk.
- A case's `tokens:` line must match the token stream captured from `TPC`.
  The capture tool lives in the dirty room (`dirty/`, local only); its
  spec-notation dump is the one thing the clean room may use from it, and
  `spec/compare.py` checks the cases against it.
- Write cases as small, complete programs of our own. When a case shows a
  value, make the program print it so `output:` records it.

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
- Never commit Borland's text, such as the decoded IDE help. It exists only as
  Bazel outputs.
- Nothing dirty is ever committed. Dirty means derived from `TPC`'s internals:
  disassembly, token dumps with internal codes, coverage data, and tools
  written with that knowledge. It lives only in the gitignored `dirty/` folder
  and in Bazel outputs, and nothing committed depends on it.
- Dirty-room work (disassembly, the token capture tool) is done by a separate
  agent. Clean-room work (`spec/`) never reads `dirty/` or disassembly output.
  Only token dumps that use the spec's token names, and `TPC` verdicts, cross
  over.
- Reading the manuals and the IDE help is allowed in the clean room, as long
  as the spec is written in our own words (see above).
- Put only Borland's own files from the BP disks into the reference install.
  Leave out anything else a copy may contain, such as third-party tools or
  replacement libraries.
