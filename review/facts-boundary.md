You are reviewing a pull request to a public repository that specifies the
Pascal dialect of Borland Pascal 7.01 by observing its compiler, `TPC.EXE`.
Its contributors also reverse-engineer `TPC.EXE` privately. Your job is to
check that this pull request publishes only facts, not Borland's expression
and not raw reverse-engineering results. Read AGENTS.md ("Facts boundary")
for the rules.

The changes are in the file `REVIEW.diff` in the current folder (the diff
from `main` to this pull request's branch). Read it, and read the changed
files in full where needed. You don't need to run any commands. Check each
change against these questions:

1. Does it contain Borland's expression: code (Pascal, assembly or machine
   code from `TPC.EXE` or Borland's libraries), disassembly, or text copied or
   closely paraphrased from Borland's manuals or online help?
2. Does it contain raw reverse-engineering results: memory addresses or
   offsets inside `TPC.EXE`, byte patterns or signatures of its code, internal
   token codes or numbering, names of internal routines, traces, coverage
   data, or notes describing `TPC`'s code rather than its behaviour?
3. Is any committed tool specific to `TPC.EXE`'s code (it embeds addresses,
   byte patterns or internal codes), rather than generic?
4. Does it add implementation code to the spec (for example a lexer or parser
   written to behave like `TPC`), rather than harness tooling for building,
   running, recording, comparing or fuzzing?
5. Do test case descriptions (the `#` lines in `*.case` files) say why `TPC`
   behaves as it does in terms of its code, rather than what the input is and
   what it shows?
6. Does it name or hint at where to download Borland's or Microsoft's
   proprietary files?

Descriptions of behaviour in the authors' own words are fine, including how
`TPC`'s parts interact, as are programs the authors wrote, results recorded
from running `TPC`, and generic tools.

Answer with "VERDICT: PASS" or "VERDICT: FAIL" on the first line, then, for a
FAIL, list each problem with the file, the line and why. Be concrete and
brief. Don't change any files.
