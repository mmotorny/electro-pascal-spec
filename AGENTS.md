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

- A case's `compile` and `output` are written only by
  `bazel run //spec:record`, never by hand. Run it after adding or changing
  cases, and keep `bazel test //spec:cases_test` passing.
- When a recorded result disagrees with the spec's text or a case's
  `tokens`, the recorded result is right: fix the text or the tokens,
  or record the behaviour as a quirk.
- A case's `tokens` must match the token stream captured from `TPC`, in
  the spec's token names. `bazel run //spec:compare` checks the cases
  against such a capture.
- Describe in a case's `description` what its input is and what it shows, never why `TPC` behaves
  that way inside.
- Write cases as small, complete programs of our own, laid out over lines
  the usual way: a line per declaration and statement, statements
  indented. Keep a program on fewer lines only where its layout is what
  the case shows (line lengths, line ends, positions on a line). When a
  case shows a value, make the program print it so `output` records it.
- Every rule in the spec ends with links to the cases that show it, and
  every case is linked from some rule; a link to a folder, with a pattern
  such as `reserved-*` as its text, cites the cases matching it.
  `cases_test` checks both. A claim no case can show belongs under "Not
  covered yet", not in the rules.
- Say exactly what `TPC` does: no "about", "often" or "as far as the cases
  go". Where a rule summarises the cases (such as the rounding of real
  values), make `cases_test` check it against them.
- The spec describes only `TPC`. Where Borland's documents say something
  else, don't mention them in the spec; add an entry to
  [`notes/discrepancies.md`](notes/discrepancies.md), in our own words.

## Facts boundary

Facts may enter this repo; Borland's expression and raw reverse-engineering
results may not.

- **Facts are welcome**, whatever they were learned from: programs we wrote,
  results recorded from `TPC` (verdicts, program output, token streams in the
  spec's token names), and descriptions in our own words of how `TPC`
  behaves, including how its parts interact (for example where the parser
  makes the lexer read `^` as a character).
- **Never Borland's expression**: no code, disassembly listings, text from
  the manuals or the IDE help, and nothing copied or paraphrased from the
  runtime library source on the BP disks. Exact identifiers, declarations
  and error message strings are fine, since compatibility needs them.
- **Never raw results of reverse engineering**: no listings, addresses,
  traces, coverage data, internal token codes or notes about `TPC`'s code.
  Work with them only in the gitignored `dirty/` folder or in Bazel outputs,
  delete them when the work is done, and make nothing committed depend on
  them.
- **Tools**: generic tools (debugger clients, trace recorders, the coverage
  plugin) may be committed. Tools that carry knowledge of `TPC`'s code, such
  as its addresses, byte patterns or internal codes, may not.
- **No implementation code in the spec**: the spec is prose and cases. Code
  in this repo is harness tooling only: building the machine, running,
  recording, comparing and fuzzing.
- Write the spec in your own words. Never copy prose, examples, syntax
  diagrams or the organisation of the manuals.
- Don't use Borland, Turbo Pascal, Turbo Vision or MS-DOS in project names or
  branding, only to say what the spec describes.
- Put only Borland's own files from the BP disks into the reference install.
  Leave out anything else a copy may contain, such as third-party tools or
  replacement libraries.

Why the boundary is drawn here:

- **What is checked is what gets published, not who wrote it.** Someone who
  has seen `TPC`'s code will always end up writing facts, and adding more
  agents doesn't make anyone clean. A review of everything that crosses the
  boundary does.
- **Behaviour is not protected, however it was learned.** A language's
  lexical structure, its token stream and how a compiler's parts hand work
  to each other are methods of operation and functionality, not expression.
  Don't hold back facts out of excess caution.
- **What stays out does so for concrete reasons**: Borland's expression is
  protected, and passing on information obtained by decompiling is limited
  to what interoperability needs.
  Addresses, internal codes and listings aren't needed to describe the
  language.

## Method

- **Cases are the oracle.** Spend effort on cases (inputs plus results
  recorded from `TPC`), not on models of `TPC`.
- **Find gaps from the code's branches.** In the dirty room, trace the cases
  through `TPC`'s code and list every conditional branch that no case takes,
  or that no case skips. Each one is a behaviour the spec hasn't covered:
  write a case for it.
- **Test limits on both sides.** Where `TPC` compares against a constant (a
  length, a maximum value), add cases just below, at and just above it.
- **Coverage-guided fuzzing** (`bazel run //fuzz`) finds what nobody thought
  to ask. Turn each interesting find into a small case.
- **Let the recorded result decide.** When a case disagrees with the spec's
  text, the case is right.

## Review

Nothing is pushed to `main` until it has passed review against the facts
boundary. The reviewer is independent of the author: GPT-6.1 Sol at medium
reasoning effort, run through the Codex CLI in a separate worktree of the
commits to push, so it sees only what they would publish (no `dirty/`, no
build outputs). It may read the whole repo and search the web. Its
checklist is [`review/facts-boundary.md`](review/facts-boundary.md). Push
only on PASS; on FAIL, fix the problems and review again.

Commit locally, then review the commits not yet on `origin/main` (replace
DIR with a scratch folder):

```
git fetch --quiet origin && git worktree add --quiet --detach DIR HEAD
cd DIR && git diff origin/main...HEAD > REVIEW.diff
codex exec -m gpt-6.1-sol -c model_reasoning_effort='"medium"' \
  -c web_search='"live"' -s read-only --ephemeral \
  "$(cat review/facts-boundary.md)" < /dev/null
cd - && git worktree remove --force DIR
```

The read-only sandbox lets the reviewer run commands without asking, so
this runs unattended. `< /dev/null` matters: without a terminal on stdin,
Codex waits to read more of the prompt from it. The verdict is the last
thing it prints.
