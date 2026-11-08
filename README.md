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
| Antigravity CLI | latest | see antigravity.google | `agy`, which runs the independent review of commits before they are pushed (see `AGENTS.md`) |
| tmux | latest | `brew install tmux` | Runs `agy` interactively during the review |

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
or the error number, line, column and message, plus `TPC`'s full output. It
also records what the results ran on: the QEMU version and hashes of the key
BP files. Large sets are spread over one machine per CPU core. With
`--coverage`, each result also lists the code edges `TPC` executed while
compiling it, recorded by a QEMU plugin (`machine/coverage/`). The plugin
is compiled with the Xcode command-line tools against Homebrew QEMU's
plugin header.

## Spec

The spec lives in [`spec/`](spec). It starts with the lexer,
[`spec/lexer.md`](spec/lexer.md), backed by test cases in
`spec/lexer/cases/`. Each case is a small program with the tokens the spec
expects and `TPC`'s recorded verdict and program output.

- `bazel run //spec:record` runs every case through `TPC` on the reference
  machine and writes the verdicts and outputs into the cases.
- `bazel test //spec:cases_test` checks that every case is well formed and
  recorded, without running `TPC`.
- `python3 spec/compare.py CAPTURED.json` compares the cases' `tokens:`
  lines with a dump of the tokens `TPC` actually delivered, in the spec's
  notation. The dump comes from a capture tool that is not part of this
  repo.

## Fuzzing

`bazel run //fuzz -- --out DIR [--rounds N]` mutates the spec's cases and
keeps every mutant that makes `TPC` run code no earlier input reached,
shrinks each one, and writes them to `DIR` with their verdicts. These finds
are candidates for new cases. `--range-file` limits coverage to an address
range, to focus on one part of `TPC`.

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
