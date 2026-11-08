# Lexer limits

Where `TPC` stops, with an error or a hang, a program that would otherwise
compile. No compiled program can depend on these. [`lexer.md`](lexer.md) links here
wherever one of them applies. Each is recorded with cases like the rest
of the spec, but whether an implementation matches it is for the
implementation to decide.

## Source text

- A line may hold at most 127 characters, not counting CRs. A tab counts as
  one character ([line-127](lexer/cases/11-program-lines/line-127.yaml), [line-127-crlf](lexer/cases/11-program-lines/line-127-crlf.yaml), [line-127-two-crs](lexer/cases/11-program-lines/line-127-two-crs.yaml), [line-127-with-cr-inside](lexer/cases/11-program-lines/line-127-with-cr-inside.yaml), [line-127-tab](lexer/cases/11-program-lines/line-127-tab.yaml)).
- A longer line is error 11 at column 128, and no token on that line is
  listed ([line-128](lexer/cases/11-program-lines/line-128.yaml), [line-128-tab](lexer/cases/11-program-lines/line-128-tab.yaml), [line-128-with-cr-inside](lexer/cases/11-program-lines/line-128-with-cr-inside.yaml)). This
  happens wherever the line is: inside a comment, an unterminated string or
  text skipped by `{$IFDEF}` too
  ([line-128-in-comment-before-end](lexer/cases/11-program-lines/line-128-in-comment-before-end.yaml), [line-128-in-string](lexer/cases/11-program-lines/line-128-in-string.yaml), [line-128-in-skipped-text](lexer/cases/11-program-lines/line-128-in-skipped-text.yaml)).

## Numbers

- The exponent's digits are read only while its value stays at most 9999,
  and the next digit starts a new token: `1e12345` is `REAL(1e1234)` then
  `INTEGER(5)`
  ([real-exponent-4-digits](lexer/cases/06-numbers/real-exponent-4-digits.yaml), [real-exponent-1000](lexer/cases/06-numbers/real-exponent-1000.yaml), [real-exponent-9999](lexer/cases/06-numbers/real-exponent-9999.yaml), [real-exponent-10000](lexer/cases/06-numbers/real-exponent-10000.yaml), [real-exponent-5-digits](lexer/cases/06-numbers/real-exponent-5-digits.yaml), [real-exponent-5-digits-small](lexer/cases/06-numbers/real-exponent-5-digits-small.yaml)).

## Conditional symbols

Counting each defined symbol, the predefined ones included, as its length
plus one, the total may be at most 1024. A `{$DEFINE}` that would go over
is error 127 at its name. Removing a symbol, even a predefined one, lowers
the total
([symbols-full](lexer/cases/10-compiler-directives/symbols-full.yaml), [symbols-over](lexer/cases/10-compiler-directives/symbols-over.yaml), [symbols-undef-frees](lexer/cases/10-compiler-directives/symbols-undef-frees.yaml), [symbols-undef-frees-over](lexer/cases/10-compiler-directives/symbols-undef-frees-over.yaml)).

## Include files

- Include files may nest as long as, counting 20 plus the length of its
  name for the program and for every include file being read at that
  point, the total is at most 6144. The names counted are the program's
  name as given to `TPC`, and each include file's name as read from its directive, with `.PAS` added when it has
  none. With the 12-character names that the cases' programs have, 218
  nested files with 8-character names are allowed (32 + 218 × 28 = 6136)
  and 219 aren't; 191 with 12-character names are (exactly 6144) and 192
  aren't; and 235 with 6-character names are and 236 aren't, whether or not
  their directives give the `.PAS`. The include file that goes over is
  error 18 just after its directive, in the file that includes it. A file
  that includes itself ends the same way
  ([depth-218-short-names](lexer/cases/14-include-files/depth-218-short-names.yaml), [depth-219-short-names](lexer/cases/14-include-files/depth-219-short-names.yaml), [depth-191-long-names](lexer/cases/14-include-files/depth-191-long-names.yaml), [depth-192-long-names](lexer/cases/14-include-files/depth-192-long-names.yaml), [depth-23?-*](lexer/cases/14-include-files/), [includes-itself](lexer/cases/14-include-files/includes-itself.yaml)).
- The program can't end in an include file: with the main `begin … end.`
  in one, it is error 10 at the `.` ([final-end-in-include](lexer/cases/14-include-files/final-end-in-include.yaml)). Nor can a statement part go on past
  the end of the include file it begins in: with `begin` in an include
  file and the rest in the program, it is error 10 at the line after the
  include file's last line ([statement-part-begins-in-include](lexer/cases/14-include-files/statement-part-begins-in-include.yaml)).

## `asm` blocks

- `end` followed directly by DEL (127) at the start of a statement makes
  `TPC` loop forever: it never finishes compiling the program
  ([end-then-del](lexer/cases/15-asm-blocks/end-then-del.yaml)).

## Not covered yet

- Whether the units a program uses affect the limit on nested include
  files.
