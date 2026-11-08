# Curiosities

Odd things `TPC` does that are worth telling, for whoever writes up the
story of this project. Each entry says what happens and why, in our own
words and in terms of how `TPC`'s parts behave and hand work to each other,
with the cases that show it. Like [`discrepancies.md`](discrepancies.md),
this is not part of the spec.

## Lexer

- **`end` followed by DEL hangs `TPC`.** In an `asm` block, `end` followed
  directly by DEL (127) at the start of a statement makes `TPC` loop
  forever ([end-then-del](../spec/lexer/cases/15-asm-blocks/end-then-del.yaml)).
  Two parts of `TPC` disagree about DEL. Before each statement, `TPC` looks
  for `end`, which closes the block, and doesn't take it as the end when
  the next character could continue a word, as in `end1` or `end_`
  ([end-then-digit](../spec/lexer/cases/15-asm-blocks/end-then-digit.yaml),
  [end-then-underscore](../spec/lexer/cases/15-asm-blocks/end-then-underscore.yaml)).
  That check counts DEL among those characters, so it hands the text to
  the assembler as a statement. The assembler, though, treats DEL as a
  blank ([del-is-blank](../spec/lexer/cases/15-asm-blocks/del-is-blank.yaml)),
  so it reads the word `end`, which inside a statement ends the statement
  just before it
  ([end-after-statement](../spec/lexer/cases/15-asm-blocks/end-after-statement.yaml)).
  The statement is empty, and the next one starts where it did, at the
  same `end`. Nothing has moved, so the same thing happens again, forever:
  on every pass, all of `TPC`'s state comes back exactly as it was. Any
  other character after `end` that can't continue a word ends the block,
  character 233 for one
  ([end-then-high-character](../spec/lexer/cases/15-asm-blocks/end-then-high-character.yaml)).
