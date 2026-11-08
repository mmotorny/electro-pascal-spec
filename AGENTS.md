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
  The exception is a tool that relies on `TPC`'s internals: it must check
  that `TPC.EXE` is the exact file its facts were taken from and refuse to
  run otherwise. `machine/tokens.py` checks against the hash in
  `spec/MACHINE.json`, which `record` rewrites only after that check has
  passed.
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

- Keep `spec/` to what a clean-room implementer reads or runs: the spec's
  text, its cases, the case schema and `MACHINE.json`. Tools that make or
  check the cases go in `harness/`, and tools that drive the reference
  machine in `machine/`.

- A case's `tokens`, `compile` and `output` are written only by
  `bazel run //harness:record`, never by hand: write the `description` and
  the `source`, then record. Keep
  `bazel test //harness:cases_test //harness:tpc_test` passing.
- When a recorded result disagrees with the spec's text, the recorded
  result is right: fix the text, or record the behaviour as a quirk.
- When `TPC` never finishes compiling a case, `record` writes
  `compile: hang` (a compile still running after 30 seconds). Before
  committing such a case, confirm in the dirty room, from `TPC`'s code and
  by comparing its state between passes, that it loops forever rather than
  running slowly. The part's limits file then says that `TPC` never
  finishes on that input, and nothing more: not why, and not what an
  implementation should do instead, which is for the implementation repo
  to decide.
- Keep `TPC`'s capacity limits and its failures apart from the behaviour
  an implementation must match. A part's main file (such as
  `spec/lexer.md`) holds the behaviour; its limits file (such as
  `spec/lexer-limits.md`) holds the capacity limits, where `TPC` just
  gives up (how many files may be open, how long a line may be), and its
  bugs, such as hangs. Record them with cases all the same, and say only
  what `TPC` does, never why: an explanation of a limit or a bug brings
  `TPC`'s workings into what a clean-room implementer reads. Leave it to
  the implementation repo to decide whether to match them. To tell them
  apart:
  - It is a limit if `TPC` stops, with an error or a hang, a program
    that would otherwise compile: no compiled program can depend on it.
    The longest line and the number of files that may be open are
    limits.
  - Everything else is behaviour, for the main file: anything a compiled
    program can depend on, even by mistake, such as where a long
    identifier is cut, or a typo that `TPC` let through. Which of two
    errors an invalid program gets is behaviour too.

  Where the main file meets a limit, it says so in a line and links to
  the limits file. Bring borderline calls to the user rather than
  deciding them.
- Describe in a case's `description` what its input is and what it shows,
  never why `TPC` behaves that way inside.
- Write cases as small, complete programs of our own, laid out over lines
  the usual way: a line per declaration and statement, statements
  indented. Keep a program on fewer lines only where its layout is what
  the case shows (line lengths, line ends, positions on a line). When a
  case shows a value, make the program print it so `output` records it.
- Track every open question and gap as a GitHub issue, never in the
  documentation alone: where a document mentions one (such as under "Not
  covered yet"), it links to the issue. Issues are public, so they keep
  to the facts boundary like everything else.
- Every rule in the spec ends with links to the cases that show it, and
  every case is linked from some rule; a link to a folder, with a pattern
  such as `reserved-*` as its text, cites the cases matching it.
  `cases_test` checks both. A claim no case can show belongs in a GitHub
  issue, not in the rules.
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
  spec's token names), descriptions in our own words of what `TPC` does
  observably, including exactly what it computes (such as the arithmetic
  that gives a real literal's bits), and the facts about `TPC`'s internals
  that the harness needs to observe it (see Tools).
- **Never Borland's expression**: no code, disassembly listings, text from
  the manuals or the IDE help, and nothing copied or paraphrased from the
  runtime library source on the BP disks. Exact identifiers, declarations
  and error message strings are fine, since compatibility needs them.
- **Never raw results of reverse engineering**: no listings, traces,
  coverage data or notes about how `TPC`'s code works. Work with them only
  in the gitignored `dirty/` folder or in Bazel outputs, delete them when
  the work is done, and make nothing committed depend on them.
- **Tools**: generic tools (debugger clients, trace recorders, the coverage
  plugin) may be committed. A tool that observes `TPC` may carry the facts
  about its internals it needs for that, such as where to stop, where in
  memory to read and how `TPC` numbers its token kinds, gathered in one
  marked place (see `machine/tokens.py`). Never its code: no machine code,
  byte patterns or disassembly; compare against a hash where a tool must
  recognise `TPC`'s code.
- **Nothing explains how `TPC` works inside**, outside the one marked place
  in a tool: not the spec, the cases, notes, docs or comments. No
  mechanisms, components (a "scanner", "the assembler") handing work to
  each other, data structures, buffers, the order of internal steps, or
  why `TPC` does what it does. Say what an input gives, not how `TPC` gets
  there. The clean-room implementation reads the spec and must not learn
  `TPC`'s design from it.
- **No implementation code in the spec**: the spec is prose and cases. Code
  in this repo is harness tooling only: building the machine, running,
  recording and comparing.
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
  lexical structure, its token stream and the values a compiler computes
  are methods of operation and functionality, not expression. Don't hold
  back facts out of excess caution.
- **Explanations stay out to keep the clean room clean**, not because they
  are protected: an implementer who learns `TPC`'s design copies it.
- **What stays out does so for concrete reasons**: Borland's expression is
  protected, and passing on information obtained by decompiling is limited
  to what interoperability needs. Checking a compatible compiler's spec
  against `TPC` is interoperability work, and the few internals the harness
  needs to do it are facts, like the memory layouts that books on DOS
  internals have long published. Listings, traces and notes about the code
  aren't needed for it.

## Method

- **Cases are the oracle.** Spend effort on cases (inputs plus results
  recorded from `TPC`), not on models of `TPC`.
- **Find gaps from the code's branches.** In the dirty room, trace the cases
  through `TPC`'s code and list every conditional branch that no case takes,
  or that no case skips. Each one is a behaviour the spec hasn't covered:
  write a case for it.
- **Test limits on both sides.** Where `TPC` compares against a constant (a
  length, a maximum value), add cases just below, at and just above it.
- **Let the recorded result decide.** When a case disagrees with the spec's
  text, the case is right.

## Clean-room trial

A part of the spec is done only when an implementer can build from it
alone. Check that with a trial before calling a part done, and again after
large changes:

1. `bazel run //harness:clean_room -- prepare DIR` copies `spec/` into
   `DIR/spec`, with every case's recorded `tokens`, `compile` and `output`
   removed. Use a scratch folder outside the repo.
2. Give a fresh agent, with none of this work in its context, only that
   folder. Tell it to:
   - read nothing outside `DIR`: not this repo, `dirty/`, Bazel outputs,
     Borland's files, or the web on how Turbo Pascal behaves;
   - write `scan(source, files, options, precompile, fpu)` in `DIR` (the
     interface is in `harness/clean_room.py`);
   - report every place the text is missing, ambiguous or contradicts
     itself, with the reading it chose, and anything it relied on that the
     spec doesn't state.
3. `bazel run //harness:clean_room -- score DIR/FILE -v` scores its code
   against the full cases.
4. Work through the report and every case that isn't exact. Where the text
   is missing or wrong, fix it, and record new cases where none shows the
   fact. Where a case's description contradicts its results, fix the
   description. Errors that only a later part of the spec (such as the
   parser) can explain are expected.

A looser trial, with the results left in, finds gaps faster. In that case,
tell the agent to list every rule it inferred from the results, because
each one is a gap in the text.

Nothing from a trial is committed: the spec holds no implementation code.

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
