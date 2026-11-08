You are reviewing changes to a public repository that specifies the
Pascal dialect of Borland Pascal 7.01 by observing its compiler, `TPC.EXE`.
Its contributors also reverse-engineer `TPC.EXE` privately. Your job is to
check that these changes publish only facts, not Borland's expression
and not raw reverse-engineering results. Read AGENTS.md ("Facts boundary")
for the rules.

The changes are in the file `REVIEW.diff` in the current folder: the diff
between the published `main` and the commits about to be pushed. Read it.
You may read any file in this repository, for example to see a changed file
in full, and search the web, for example to check whether a piece of text
comes from Borland's manuals. Check each change against these questions:

1. Does it contain Borland's expression: code (Pascal, assembly or machine
   code from `TPC.EXE` or Borland's libraries), disassembly, or text copied or
   closely paraphrased from Borland's manuals or online help?
2. Does it contain raw reverse-engineering results: listings, traces,
   coverage data, or notes describing how `TPC`'s code works rather than its
   behaviour?
3. Does a tool carry more of `TPC.EXE` than the facts it needs to observe
   `TPC`? Addresses to stop at, memory offsets to read and internal codes
   are allowed in a harness tool that uses them, gathered in one marked
   place. Machine code, byte patterns or signatures of `TPC`'s code are not
   (a hash is fine), nor are internals the tool doesn't use.
3a. Do internals of `TPC` (addresses, offsets, internal codes) appear in the
   spec's text or cases, which must describe behaviour only?
4. Does it add implementation code to the spec (for example a lexer or parser
   written to behave like `TPC`), rather than harness tooling for building,
   running, recording or comparing?
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
