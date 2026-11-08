# electro-pascal-spec

A clean-room specification of the Pascal dialect of Borland Pascal 7.01 for
DOS and its units, including Turbo Vision. The spec is written by observing
how the original compiler and the programs it builds behave. The clean-room
implementation lives in a separate repo.

## Prerequisites

Developed on macOS (Apple Silicon) with [Homebrew](https://brew.sh).

| Tool | Version | Install | Used for |
| --- | --- | --- | --- |
| Bazelisk | latest | `brew install bazelisk` | Runs the latest Bazel |
| QEMU | latest | `brew install qemu` | Runs MS-DOS 6.22 and Borland Pascal 7.01 as the reference machine |
| Python 3 | latest | `xcode-select --install` | Drives the installers on the reference machine |
| mtools | latest | `brew install mtools` | Copies files to and from the reference machine's disk |
| PyYAML, jsonschema | latest | installed by Bazel with the system Python's `pip` | Reading the spec's cases and checking them against their schema |
| Codex CLI | latest | see github.com/openai/codex | `codex`, which runs the independent review of commits before they are pushed (see `AGENTS.md`) |

Tools aren't pinned: keep them up to date with `brew upgrade`.

## Proprietary inputs

Spec work runs against original software and manuals that are not freely
licensed, so this repo doesn't contain them or say where to get them. All of
them are required: bring your own copies, which you must be licensed to use.

| Target | What | Terms | Variable |
| --- | --- | --- | --- |
| `//third_party/bp701:archive` | Borland Pascal With Objects 7.01 (1993), English, 3.5" disk images in a 7z archive | Proprietary | `BP701_URL` |
| `//third_party/msdos622:archive` | MS-DOS 6.22 (Upgrade), 3.5" disk images in a 7z archive | Proprietary | `MSDOS622_URL` |
| `//third_party/tp55:archive` | Turbo Pascal 5.5 (1989), `tp55.zip` as later released free by Borland | Free for personal use only, no redistribution | `TP55_URL` |
| `//third_party/tp70:users_guide` | Turbo Pascal 7.0 User's Guide (1992), scanned PDF | Proprietary | `TP70_USERS_GUIDE_URL` |
| `//third_party/tp70:language_guide` | Turbo Pascal 7.0 Language Guide (1992), scanned PDF | Proprietary | `TP70_LANGUAGE_GUIDE_URL` |
| `//third_party/tp70:programmers_reference` | Turbo Pascal 7.0 Programmer's Reference (1992), scanned PDF | Proprietary | `TP70_PROGRAMMERS_REFERENCE_URL` |

Set each variable in a `user.bazelrc` file in the repo root. It's gitignored.
Use `file://` for a local copy:

```
common --repo_env=BP701_URL=file:///path/to/bp701.7z
```

## Building

```
bazel build //...
```

## Reference machine

`bazel build //machine:disk` builds the reference machine's hard disk,
`bazel-bin/machine/disk.img`: a 64 MB disk image for a 486 PC with 16 MB of
memory. A script installs MS-DOS 6.22 and then Borland Pascal 7.01 inside
QEMU by running their own installers with default options, reading the screen
and typing keys like a user would. It takes about a minute.

`bazel run //machine:run` boots that disk in a QEMU window. Changes to the
disk are thrown away when QEMU exits. Arguments after `--` go to QEMU.

`bazel run //machine:probe -- file.pas ...` compiles each file with `TPC.EXE`
on the reference machine and prints the results as JSON: whether it compiled,
or the error number, line, column and message, or that `TPC` was still
compiling it after 30 seconds (a hang), plus `TPC`'s full output. It
also records what the results ran on: the QEMU version and hashes of the key
BP files. Large sets are spread over one machine per CPU core. With
`--coverage`, each result also lists the code edges `TPC` executed while
compiling it, recorded by a QEMU plugin (`machine/coverage/`). The plugin
is compiled with the Xcode command-line tools against Homebrew QEMU's
plugin header.

## Spec

The spec lives in [`spec/`](spec). It starts with the lexer,
[`spec/lexer.md`](spec/lexer.md), backed by test cases in
`spec/lexer/cases/`. Each case is a YAML file holding a small program (and
any include files it reads), the tokens `TPC` reads in it, and what
compiling and running it with `TPC` gave, including any error message;
[`spec/case.schema.yaml`](spec/case.schema.yaml) defines the format.
`spec/` holds only what a clean-room implementation reads; the tools that
make and check the cases are in [`harness/`](harness).

- `bazel run //harness:record [-- case or directory ...]` runs cases through
  `TPC` on the reference machine and writes what it gives into them: the
  tokens it reads, whether the program compiles, and what it prints.
- `bazel test //harness:tpc_test` runs every case through `TPC` the same way
  and fails if any case's `tokens`, `compile` or `output` differ from what
  `TPC` gives. It changes nothing. Bazel reruns it only when a case, the
  reference machine or the tools change.
- `bazel test //harness:cases_test` checks, without running `TPC`, that every
  case is well formed and recorded, that every rule's links name existing
  cases and every case is linked from a rule, and that the rules the spec
  gives for real values give the recorded values.
- `bazel run //harness:clean_room -- prepare DIR` and
  `bazel run //harness:clean_room -- score FILE` set up and score a
  clean-room trial: an implementation built from `spec/` alone, with the
  cases' recorded results removed (see `AGENTS.md`).
- `bazel run //machine:tokens -- file ...` prints the tokens `TPC` reads
  in Pascal files or cases, `asm` blocks included. It watches `TPC` through
  QEMU's gdbstub, using a few facts about `TPC`'s internals gathered at the
  top of `machine/tokens.py`.

Where Borland's documents disagree with `TPC`, the spec follows `TPC` and
doesn't mention them. The disagreements are collected in
[`notes/discrepancies.md`](notes/discrepancies.md).

## IDE help as text

`bazel build //help:all` decodes the DOS IDE's online help into plain text:
`bazel-bin/help/turbo.txt` (language, compiler and run-time library) and
`bazel-bin/help/tvision.txt` (Turbo Vision). It's Borland's text, so it exists
only as build output.

## License

BSD 3-Clause, see `LICENSE`. This covers the spec and everything else in the
repo except the third-party files described above, which keep their own terms.

## Trademarks

Borland, Turbo Pascal and Turbo Vision are trademarks of their respective
owners, and MS-DOS is a trademark of Microsoft. They're used here only to
identify what this spec describes. This project is not affiliated with or
endorsed by any of them.
