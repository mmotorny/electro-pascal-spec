# Lexer

How `TPC.EXE` (Borland Pascal 7.01, real-mode command-line compiler) splits a
source file into tokens. Every rule ends with links to the cases in
[`lexer/cases/`](lexer/cases) that show it, and every case is linked from
some rule; `bazel test //harness:cases_test` checks both. A link whose text
holds a `*` or `?` stands for all the cases in its folder that match it. A
case's `tokens`, `compile` and `output` are recorded from the real compiler
and are the final word; where this text and a case disagree, the case is
right and this text needs fixing. `bazel test //harness:tpc_test` checks that
every case still matches what `TPC` gives.

Between them, the cases take both sides of every branch in `TPC`'s scanner,
and in the scanner of its built-in assembler, that a single source file can
reach, except as noted under
[not covered yet](#not-covered-yet). A case's token list ends where `TPC`
stops asking for tokens: at the end of the program, or at the token where
it reports an error. When the error is in the lexer itself, the bad token
is not delivered.

## Cases

Each case is a YAML file; [`case.schema.yaml`](case.schema.yaml) defines
its fields exactly. For example:

```yaml
description: Thirty leading zeros don't overflow.
source: |
  program P;
  const C = 0000000000000000000000000000007;
  begin
    Write(C)
  end.
tokens:
  - PROGRAM
  - IDENT: P
  - SEMI
  - CONST
  - IDENT: C
  - EQ
  - INTEGER: 7
  - SEMI
  - BEGIN
  - IDENT: WRITE
  - LPAREN
  - IDENT: C
  - RPAREN
  - END
  - DOT
compile: ok
output: "7"
```

- `source` is the program. Its text is the file's bytes, one character per
  byte, so a source holding control characters or bytes above 127 is
  written as a double-quoted string with escapes, such as `"pro\0gram"` or
  `"M\xe9"`.
- `tokens` lists the tokens in order. A token is its kind, alone or mapped
  to its value:

  | Kind | Token | Value |
  | --- | --- | --- |
  | `AND`, `ARRAY`, … `XOR` | a [reserved word](#reserved-words), named by the word in upper case | none |
  | `IDENT` | an [identifier](#identifiers) | its first 63 characters, in upper case |
  | `INTEGER` | an [integer number](#numbers) | its value as a signed 32-bit integer |
  | `REAL` | a [real number](#numbers) | its text, as written |
  | `STRING` | a [character string](#character-strings) | its characters, one per byte |
  | `PLUS` `MINUS` `STAR` `SLASH` | `+` `-` `*` `/` | none |
  | `EQ` `NE` `LT` `LE` `GT` `GE` | `=` `<>` `<` `<=` `>` `>=` | none |
  | `LPAREN` `RPAREN` | `(` `)` | none |
  | `LBRACKET` `RBRACKET` | `[` or `(.`, and `]` or `.)` | none |
  | `DOT` `DOTDOT` `COMMA` `COLON` `SEMI` | `.` `..` `,` `:` `;` | none |
  | `ASSIGN` | `:=` | none |
  | `CARET` `AT` | `^` `@` | none |

- `options`, when present, lists options for `TPC`'s command line, such as
  `/M` (build the units the program uses from their sources) or `/DNAME`.
- `files`, when present, holds more files beside the program, such as
  include files: DOS file names in upper case, each mapped to its
  contents, written like `source`.
- `compile` is what compiling the source with `TPC` gives: `ok`; `hang`
  when `TPC` never finishes compiling it; or the error number with the line and column `TPC` reports it at, the file it
  is in when that isn't the program, and `TPC`'s message:

  ```yaml
  compile:
    error: 5
    line: 1
    column: 16
    message: Syntax error.
  ```

- `output` is what the compiled program writes, one character per byte;
  it is there only when the program compiles.

## Source text

- A file is a sequence of bytes. Line feed (10) ends a line, alone or after
  a carriage return. Carriage return (13) does not: a file with CR alone is
  one long line ([lf-ends-a-line](lexer/cases/01-separators/lf-ends-a-line.yaml), [crlf-ends-a-line](lexer/cases/01-separators/crlf-ends-a-line.yaml), [cr-does-not-end-a-line](lexer/cases/01-separators/cr-does-not-end-a-line.yaml)).
- A line may hold at most 127 characters, not counting CRs. A tab counts as
  one character ([line-127](lexer/cases/11-program-lines/line-127.yaml), [line-127-crlf](lexer/cases/11-program-lines/line-127-crlf.yaml), [line-127-two-crs](lexer/cases/11-program-lines/line-127-two-crs.yaml), [line-127-with-cr-inside](lexer/cases/11-program-lines/line-127-with-cr-inside.yaml), [line-127-tab](lexer/cases/11-program-lines/line-127-tab.yaml)).
- A longer line is error 11 at column 128, before any token on that line is
  delivered ([line-128](lexer/cases/11-program-lines/line-128.yaml), [line-128-tab](lexer/cases/11-program-lines/line-128-tab.yaml), [line-128-with-cr-inside](lexer/cases/11-program-lines/line-128-with-cr-inside.yaml)). This
  happens wherever the line is: inside a comment, an unterminated string or
  text skipped by `{$IFDEF}` too
  ([line-128-in-comment-before-end](lexer/cases/11-program-lines/line-128-in-comment-before-end.yaml), [line-128-in-string](lexer/cases/11-program-lines/line-128-in-string.yaml), [line-128-in-skipped-text](lexer/cases/11-program-lines/line-128-in-skipped-text.yaml)).
- NUL (0) bytes are dropped as a line is read, as if they weren't in the
  file: `pro`, NUL, `gram` is `program`, a NUL between two digits or inside
  a quoted string disappears, and NULs don't count toward the line length
  ([nul-in-word](lexer/cases/02-character-set/nul-in-word.yaml), [nul-in-number](lexer/cases/02-character-set/nul-in-number.yaml), [nul-in-string](lexer/cases/02-character-set/nul-in-string.yaml), [nul-not-counted](lexer/cases/02-character-set/nul-not-counted.yaml), [nul-after-semicolon](lexer/cases/02-character-set/nul-after-semicolon.yaml)).
- Nothing changes where a token crosses a 4096-byte boundary of the file
  ([string-across-4096](lexer/cases/11-program-lines/string-across-4096.yaml)).
- ^Z (26) ends the file; nothing after it is read
  ([ctrl-z-ends-file](lexer/cases/12-end-of-file/ctrl-z-ends-file.yaml)). When the file ends too early, the error is
  reported at column 1 of the line after the last line read, and a line
  that ^Z cuts short still counts as read
  ([ctrl-z-early](lexer/cases/12-end-of-file/ctrl-z-early.yaml), [ctrl-z-early-more-lines](lexer/cases/12-end-of-file/ctrl-z-early-more-lines.yaml), [ctrl-z-line-3](lexer/cases/12-end-of-file/ctrl-z-line-3.yaml), [missing-final-dot](lexer/cases/12-end-of-file/missing-final-dot.yaml)).
  The last line needs no line end ([no-final-newline](lexer/cases/12-end-of-file/no-final-newline.yaml)).
- Scanning stops after the program's final `end.`. Anything after it is
  never read ([after-final-end](lexer/cases/12-end-of-file/after-final-end.yaml)).

## Separators

- Characters 1 to 32 are blanks (0 never gets this far, see
  [source text](#source-text)). Blanks and comments separate tokens and are
  otherwise ignored ([control-characters-are-blanks](lexer/cases/01-separators/control-characters-are-blanks.yaml), [comment-is-a-separator](lexer/cases/01-separators/comment-is-a-separator.yaml)).
- A separator is needed only between two tokens that would otherwise run
  together: two words (reserved words or identifiers) or a word and a
  number. `programP` is a single identifier
  ([words-joined](lexer/cases/01-separators/words-joined.yaml), [no-separator-next-to-symbols](lexer/cases/01-separators/no-separator-next-to-symbols.yaml)).
- A blank inside a two-character symbol splits it: `: =` is `:` then `=`
  ([assign-split](lexer/cases/03-special-symbols/assign-split.yaml), [dotdot-split](lexer/cases/03-special-symbols/dotdot-split.yaml), [le-split](lexer/cases/03-special-symbols/le-split.yaml), [ne-split](lexer/cases/03-special-symbols/ne-split.yaml), [ge-split](lexer/cases/03-special-symbols/ge-split.yaml), [lbracket-digraph-split](lexer/cases/03-special-symbols/lbracket-digraph-split.yaml), [rbracket-digraph-split](lexer/cases/03-special-symbols/rbracket-digraph-split.yaml)).

## Character set

- Reserved words and identifiers are made of the letters A–Z and a–z, the
  digits 0–9 and the underscore. Case doesn't matter
  ([upper-case-words](lexer/cases/02-character-set/upper-case-words.yaml), [mixed-case-words](lexer/cases/02-character-set/mixed-case-words.yaml)).
- The printable characters ``! " % & ? \ ` | ~``, DEL (127) and the
  characters 128 to 255 are allowed only inside strings and comments
  ([high-characters-in-string](lexer/cases/02-character-set/high-characters-in-string.yaml), [del-in-string](lexer/cases/02-character-set/del-in-string.yaml), [not-a-symbol-in-comment](lexer/cases/02-character-set/not-a-symbol-in-comment.yaml)).
  Elsewhere each is error 5, and no token is delivered for it
  ([not-a-symbol-exclamation](lexer/cases/02-character-set/not-a-symbol-exclamation.yaml), [not-a-symbol-double-quote](lexer/cases/02-character-set/not-a-symbol-double-quote.yaml), [not-a-symbol-percent](lexer/cases/02-character-set/not-a-symbol-percent.yaml), [not-a-symbol-ampersand](lexer/cases/02-character-set/not-a-symbol-ampersand.yaml), [not-a-symbol-question-mark](lexer/cases/02-character-set/not-a-symbol-question-mark.yaml), [not-a-symbol-backslash](lexer/cases/02-character-set/not-a-symbol-backslash.yaml), [not-a-symbol-backquote](lexer/cases/02-character-set/not-a-symbol-backquote.yaml), [not-a-symbol-vertical-bar](lexer/cases/02-character-set/not-a-symbol-vertical-bar.yaml), [not-a-symbol-tilde](lexer/cases/02-character-set/not-a-symbol-tilde.yaml), [not-a-symbol-del](lexer/cases/02-character-set/not-a-symbol-del.yaml), [high-character-outside-string](lexer/cases/02-character-set/high-character-outside-string.yaml)).

## Special symbols

Single characters `+ - * / = < > [ ] . , ( ) : ; ^ @` and pairs
`<= >= <> := .. (. .)`
([arithmetic](lexer/cases/03-special-symbols/arithmetic.yaml), [relational](lexer/cases/03-special-symbols/relational.yaml), [brackets](lexer/cases/03-special-symbols/brackets.yaml), [caret-and-at](lexer/cases/03-special-symbols/caret-and-at.yaml)). `(.` and `.)` mean
the same as `[` and `]` ([bracket-digraphs](lexer/cases/03-special-symbols/bracket-digraphs.yaml)). `/` is `SLASH` everywhere, the byte lists of
`inline(...)` included ([inline-slash](lexer/cases/03-special-symbols/inline-slash.yaml)). `{ } (* *)` delimit
[comments](#comments). `$` and `#` start [hex numbers](#numbers) and
[control characters](#character-strings).

## Reserved words

These 49 words are reserved and can't be used as identifiers ([reserved-*](lexer/cases/04-reserved-words/)):

`and array asm begin case const constructor destructor div do downto else
end file for function goto if implementation in inherited inline interface
label mod nil not object of or packed procedure program record repeat set
shl shr string then to type unit until uses var while with xor`

`exports`, `library` and the standard directives `absolute assembler export
external far forward index interrupt near private public resident virtual`
are ordinary identifiers to the lexer ([not-reserved-*](lexer/cases/04-reserved-words/)).

## Identifiers

- A letter or underscore, then any number of letters, digits and
  underscores. `_` alone is an identifier. A digit can't come first: `1A` is
  a number and an identifier
  ([digits-after-first](lexer/cases/05-identifiers/digits-after-first.yaml), [underscore-first](lexer/cases/05-identifiers/underscore-first.yaml), [underscore-only](lexer/cases/05-identifiers/underscore-only.yaml), [digit-first](lexer/cases/05-identifiers/digit-first.yaml)).
- Case doesn't matter, and only the first 63 characters are significant:
  identifiers that agree in their first 63 characters are the same
  identifier ([case-insensitive](lexer/cases/05-identifiers/case-insensitive.yaml), [63-significant-same](lexer/cases/05-identifiers/63-significant-same.yaml), [63-significant-differ](lexer/cases/05-identifiers/63-significant-differ.yaml)).
- A qualified identifier such as `System.WriteLn` is three tokens
  ([qualified](lexer/cases/05-identifiers/qualified.yaml)).

## Numbers

- **Decimal integers** are digit sequences with values from 0 to
  2147483647 ([decimal](lexer/cases/06-numbers/decimal.yaml), [decimal-max](lexer/cases/06-numbers/decimal-max.yaml)). Leading zeros don't matter
  ([leading-zeros](lexer/cases/06-numbers/leading-zeros.yaml), [decimal-many-leading-zeros](lexer/cases/06-numbers/decimal-many-leading-zeros.yaml)). A larger value is
  error 7, at the digit where the value first goes over: in a run of twenty
  `1`s, that's the 11th ([decimal-over](lexer/cases/06-numbers/decimal-over.yaml), [decimal-overflow-position](lexer/cases/06-numbers/decimal-overflow-position.yaml)). A
  minus sign is a separate token, so `-2147483648` is an error
  ([decimal-min](lexer/cases/06-numbers/decimal-min.yaml)).
- **Hex integers** are `$` and one or more hex digits, either case, with a
  value up to `$FFFFFFFF`, and error 7 likewise at the digit that goes over
  ([hex](lexer/cases/06-numbers/hex.yaml), [hex-lower](lexer/cases/06-numbers/hex-lower.yaml), [hex-over](lexer/cases/06-numbers/hex-over.yaml), [hex-overflow-position](lexer/cases/06-numbers/hex-overflow-position.yaml)). Leading zeros
  don't count ([hex-leading-zeros](lexer/cases/06-numbers/hex-leading-zeros.yaml)). The value is a 32-bit pattern read
  as signed: `$FFFFFFFF` is -1 and `$80000000` is -2147483648
  ([hex-max](lexer/cases/06-numbers/hex-max.yaml), [hex-sign-bit](lexer/cases/06-numbers/hex-sign-bit.yaml)). `$` without a hex digit right after it is
  error 7 ([dollar-alone](lexer/cases/06-numbers/dollar-alone.yaml), [dollar-space](lexer/cases/06-numbers/dollar-space.yaml)).
- **Reals** are digits, then a fraction (`.` and digits), an exponent
  (`E` or `e`, an optional sign and digits), or both
  ([real-fraction](lexer/cases/06-numbers/real-fraction.yaml), [real-exponent](lexer/cases/06-numbers/real-exponent.yaml), [real-exponent-negative](lexer/cases/06-numbers/real-exponent-negative.yaml), [real-exponent-upper-signed](lexer/cases/06-numbers/real-exponent-upper-signed.yaml), [real-many-fraction-digits](lexer/cases/06-numbers/real-many-fraction-digits.yaml), [real-many-integer-digits](lexer/cases/06-numbers/real-many-integer-digits.yaml)).
  The digits after `.` and after `E` may be missing: `1.`, `1.e5`, `1e`,
  `1e+` and `1e-` are all accepted, and a missing exponent counts as 0
  ([real-no-fraction-digits](lexer/cases/06-numbers/real-no-fraction-digits.yaml), [real-dot-exponent](lexer/cases/06-numbers/real-dot-exponent.yaml), [real-exponent-no-digits](lexer/cases/06-numbers/real-exponent-no-digits.yaml), [real-exponent-plus-no-digits](lexer/cases/06-numbers/real-exponent-plus-no-digits.yaml), [real-exponent-minus-no-digits](lexer/cases/06-numbers/real-exponent-minus-no-digits.yaml)).
  The exponent's digits are read only while its value stays at most 9999,
  and the next digit starts a new token: `1e12345` is `REAL(1e1234)` then
  `INTEGER(5)`
  ([real-exponent-4-digits](lexer/cases/06-numbers/real-exponent-4-digits.yaml), [real-exponent-1000](lexer/cases/06-numbers/real-exponent-1000.yaml), [real-exponent-9999](lexer/cases/06-numbers/real-exponent-9999.yaml), [real-exponent-10000](lexer/cases/06-numbers/real-exponent-10000.yaml), [real-exponent-5-digits](lexer/cases/06-numbers/real-exponent-5-digits.yaml), [real-exponent-5-digits-small](lexer/cases/06-numbers/real-exponent-5-digits-small.yaml)).
  Leading zeros in the exponent don't count
  ([real-exponent-leading-zeros-9999](lexer/cases/06-numbers/real-exponent-leading-zeros-9999.yaml)). A number can't start with `.`
  ([real-no-integer-digits](lexer/cases/06-numbers/real-no-integer-digits.yaml)). A value beyond the Extended range is
  error 6, just after the number ([real-overflow](lexer/cases/06-numbers/real-overflow.yaml)); a value that fits
  Extended is a valid token even where it doesn't fit the type it is used
  as ([real-huge](lexer/cases/06-numbers/real-huge.yaml)).
- `1..2` is `1`, `..`, `2`, and `1.)` is `1`, `.)`: a `.` directly
  followed by another `.` or by `)` doesn't make a real
  ([integer-then-dotdot](lexer/cases/06-numbers/integer-then-dotdot.yaml)) ([bracket-digraphs](lexer/cases/03-special-symbols/bracket-digraphs.yaml)). `1. )` is
  `REAL(1.)` and `)` ([real-dot-then-blank-paren](lexer/cases/06-numbers/real-dot-then-blank-paren.yaml)).

## Labels

A label is an identifier or a number from 0 to 9999; leading zeros don't
matter, so `01` and `1` are the same label
([label-identifier](lexer/cases/07-labels/label-identifier.yaml), [label-max](lexer/cases/07-labels/label-max.yaml), [label-leading-zeros](lexer/cases/07-labels/label-leading-zeros.yaml)). To the lexer a
numeric label is an ordinary `INTEGER`: `10000` is delivered as a number and
then rejected where a label is expected ([label-over](lexer/cases/07-labels/label-over.yaml)).

## Character strings

A string is a run of parts with no separators between them
([mixed](lexer/cases/08-strings/mixed.yaml), [mixed-around](lexer/cases/08-strings/mixed-around.yaml), [caret-mixed](lexer/cases/08-strings/caret-mixed.yaml), [caret-pair-in-write](lexer/cases/08-strings/caret-pair-in-write.yaml)). A blank
between parts ends the string, and the next part starts a new one
([separator-between-parts](lexer/cases/08-strings/separator-between-parts.yaml)). The parts are:

- **Quoted strings**: characters between apostrophes on one line, with two
  apostrophes standing for one
  ([quoted](lexer/cases/08-strings/quoted.yaml), [empty](lexer/cases/08-strings/empty.yaml), [blank](lexer/cases/08-strings/blank.yaml), [doubled-apostrophe](lexer/cases/08-strings/doubled-apostrophe.yaml), [long-string](lexer/cases/08-strings/long-string.yaml)) ([brace-in-string](lexer/cases/09-comments/brace-in-string.yaml)).
  A line end before the closing apostrophe is error 8 ([unterminated](lexer/cases/08-strings/unterminated.yaml)).
- **`#` and a number**, decimal or hex, with no blank after `#`
  ([control-characters](lexer/cases/08-strings/control-characters.yaml), [hash-hex](lexer/cases/08-strings/hash-hex.yaml), [hash-space](lexer/cases/08-strings/hash-space.yaml)). The number is read like
  any integer, with the same limits and error 7 when it overflows
  ([hash-overflow](lexer/cases/08-strings/hash-overflow.yaml)). Then only its low 8 bits are used: `#256` is `#0`,
  `#65601` is `'A'` and `#2147483647` is `#255`
  ([hash-255](lexer/cases/08-strings/hash-255.yaml), [hash-256](lexer/cases/08-strings/hash-256.yaml), [hash-large](lexer/cases/08-strings/hash-large.yaml), [hash-max-integer](lexer/cases/08-strings/hash-max-integer.yaml)).
- **`^` and the very next character**, whatever it is, a blank included:
  the character with bit 64 flipped, after changing `a` to `z` to upper
  case. `^M` and `^m` are `#13`, `^@` is `#0`, `^[` is `#27`, `^1` is
  `'q'`, `^'` is `'g'`, and `^` then a space is `` ` `` (96)
  ([caret-letter](lexer/cases/08-strings/caret-letter.yaml), [caret-lower](lexer/cases/08-strings/caret-lower.yaml), [caret-at](lexer/cases/08-strings/caret-at.yaml), [caret-bracket](lexer/cases/08-strings/caret-bracket.yaml), [caret-digit](lexer/cases/08-strings/caret-digit.yaml), [caret-quote](lexer/cases/08-strings/caret-quote.yaml), [caret-space](lexer/cases/08-strings/caret-space.yaml)).
  Only `a` to `z` change case: `` ^` `` is `' '`, `^z` is `#26`, `^{` is
  `';'`, `^~` is `'>'`, `^` then DEL (127) is `'?'` and `^` then character
  233 is `#169`
  ([caret-backquote](lexer/cases/08-strings/caret-backquote.yaml), [caret-z](lexer/cases/08-strings/caret-z.yaml), [caret-brace](lexer/cases/08-strings/caret-brace.yaml), [caret-tilde](lexer/cases/08-strings/caret-tilde.yaml), [caret-del](lexer/cases/08-strings/caret-del.yaml), [caret-high](lexer/cases/08-strings/caret-high.yaml)).
  Only one character is taken: `^Integer` is `^I` followed by the
  identifier `nteger` ([caret-word](lexer/cases/08-strings/caret-word.yaml)). Where an operand is expected but
  `^` is the last character on its line, `TPC` delivers `CARET` and then
  reports error 8 just after it, as for an unterminated string
  ([caret-end-of-line](lexer/cases/08-strings/caret-end-of-line.yaml)).

Any number of strings, however long, may appear in one statement
([many-long-strings](lexer/cases/08-strings/many-long-strings.yaml)).

Whether `^` starts a string depends on where it appears. Where an operand
of an expression is expected, `^` and the next character are a character
string as above, and join with neighbouring parts: in constant expressions,
statements, set constructors and `case` labels
([caret-in-const-expression](lexer/cases/08-strings/caret-in-const-expression.yaml), [caret-in-expression](lexer/cases/08-strings/caret-in-expression.yaml), [caret-in-comparison](lexer/cases/08-strings/caret-in-comparison.yaml), [caret-in-write](lexer/cases/08-strings/caret-in-write.yaml), [caret-in-set](lexer/cases/08-strings/caret-in-set.yaml), [caret-case-label](lexer/cases/08-strings/caret-case-label.yaml)).
Everywhere else `^` is `CARET`:

- wherever a type is expected: after `=` in a type declaration, after `:`
  in a variable, record field or typed constant declaration, and after `of`
  in an array type
  ([caret-type-pointer](lexer/cases/08-strings/caret-type-pointer.yaml), [caret-var-pointer](lexer/cases/08-strings/caret-var-pointer.yaml), [caret-record-field](lexer/cases/08-strings/caret-record-field.yaml), [caret-typed-constant](lexer/cases/08-strings/caret-typed-constant.yaml), [caret-array-of](lexer/cases/08-strings/caret-array-of.yaml)).
  There `^M` is always a pointer to type `M`, so a subrange of characters
  can't be written with `^`: `type T = ^A..^Z` is an error
  ([caret-char-subrange](lexer/cases/08-strings/caret-char-subrange.yaml), [caret-var-subrange](lexer/cases/08-strings/caret-var-subrange.yaml)). `^1` there is
  `CARET INTEGER(1)` ([caret-type-digit](lexer/cases/08-strings/caret-type-digit.yaml)).
- after an operand, where it dereferences a pointer: `Q^.F`, `(Q)^`
  ([caret-after-identifier](lexer/cases/08-strings/caret-after-identifier.yaml), [caret-after-paren](lexer/cases/08-strings/caret-after-paren.yaml)).

## Comments

- `{` to the next `}`, or `(*` to the next `*)` ([braces](lexer/cases/09-comments/braces.yaml), [paren-star](lexer/cases/09-comments/paren-star.yaml)).
  Comments of both kinds may span lines
  ([multi-line](lexer/cases/09-comments/multi-line.yaml), [paren-star-multi-line](lexer/cases/09-comments/paren-star-multi-line.yaml)). A `*` at the end of one line
  and a `)` at the start of the next don't end a `(*` comment
  ([paren-star-split-close](lexer/cases/09-comments/paren-star-split-close.yaml)).
- They don't nest, and the other kind of delimiter has no effect inside
  one: `{ (* }` is a complete comment
  ([braces-dont-nest](lexer/cases/09-comments/braces-dont-nest.yaml), [paren-star-dont-nest](lexer/cases/09-comments/paren-star-dont-nest.yaml), [paren-star-inside-braces](lexer/cases/09-comments/paren-star-inside-braces.yaml), [brace-inside-paren-star](lexer/cases/09-comments/brace-inside-paren-star.yaml)).
- `(*)` opens a comment; the `)` is part of it
  ([paren-star-close-paren](lexer/cases/09-comments/paren-star-close-paren.yaml)).
- A `}` outside a comment is a syntax error ([stray-close-brace](lexer/cases/09-comments/stray-close-brace.yaml)). A
  `*)` outside a comment is simply `*` followed by `)`
  ([paren-star-dont-nest](lexer/cases/09-comments/paren-star-dont-nest.yaml)). A comment still open at the end of the file
  is error 10 ([unterminated-brace](lexer/cases/09-comments/unterminated-brace.yaml), [unterminated-paren-star](lexer/cases/09-comments/unterminated-paren-star.yaml)).

## Compiler directives

A comment whose first character is `$` is a compiler directive
([brace-directive](lexer/cases/10-compiler-directives/brace-directive.yaml), [paren-star-directive](lexer/cases/10-compiler-directives/paren-star-directive.yaml)). Directives are not tokens.
Their names aren't case sensitive ([lower-case-directive](lexer/cases/10-compiler-directives/lower-case-directive.yaml), [switch-lower-sign](lexer/cases/10-compiler-directives/switch-lower-sign.yaml)).
`{ $R+}` is an ordinary comment ([blank-before-dollar](lexer/cases/10-compiler-directives/blank-before-dollar.yaml)).

A directive is checked as soon as `{$` or `(*$` is read, before the end of
the comment is looked for, so a bad directive is error 17 even in a comment
that never ends
([invalid-directive-unterminated](lexer/cases/10-compiler-directives/invalid-directive-unterminated.yaml), [unterminated-directive](lexer/cases/10-compiler-directives/unterminated-directive.yaml)). Its name is
the run of letters and digits after the `$`, so `{$M16384}` has the unknown
name `M16384` ([m-no-blank-number](lexer/cases/10-compiler-directives/m-no-blank-number.yaml), [long-unknown-name](lexer/cases/10-compiler-directives/long-unknown-name.yaml)). The name is one
of:

- a conditional directive name (`DEFINE`, `UNDEF`, `IFDEF`, `IFNDEF`,
  `IFOPT`, `ELSE`, `ENDIF`), see below;
- a list of switches, each a switch letter and `+` or `-`, separated by
  commas with no blanks: `{$R+,X-}` ([switch-list](lexer/cases/10-compiler-directives/switch-list.yaml)). A blank after a
  comma is error 17 ([switch-list-blank-after-comma](lexer/cases/10-compiler-directives/switch-list-blank-after-comma.yaml)). Anything after
  the last sign that isn't a comma is ignored, a blank or not: `{$R+ text}`
  is accepted, and `{$R-B+}` turns R off and leaves B alone
  ([switch-trailing-text](lexer/cases/10-compiler-directives/switch-trailing-text.yaml), [switch-text-after-sign](lexer/cases/10-compiler-directives/switch-text-after-sign.yaml));
- a parameter directive letter (`C D G I L M O R S`) and its parameter.
  For `C`, `D`, `G`, `R` and `S`, everything after the letter up to the
  end of the comment is ignored, whatever it is and nothing at all
  included: `{$R}`, `{$R }` and `{$R=X}` are accepted
  ([parameter-c-text](lexer/cases/10-compiler-directives/parameter-c-text.yaml), [parameter-c-empty](lexer/cases/10-compiler-directives/parameter-c-empty.yaml), [parameter-d-text](lexer/cases/10-compiler-directives/parameter-d-text.yaml), [parameter-d-empty](lexer/cases/10-compiler-directives/parameter-d-empty.yaml), [parameter-g-text](lexer/cases/10-compiler-directives/parameter-g-text.yaml), [parameter-g-empty](lexer/cases/10-compiler-directives/parameter-g-empty.yaml), [parameter-s-text](lexer/cases/10-compiler-directives/parameter-s-text.yaml), [parameter-s-empty](lexer/cases/10-compiler-directives/parameter-s-empty.yaml), [switch-without-sign](lexer/cases/10-compiler-directives/switch-without-sign.yaml), [switch-r-blank](lexer/cases/10-compiler-directives/switch-r-blank.yaml), [r-equals](lexer/cases/10-compiler-directives/r-equals.yaml)).
  `I` and `L` take a file name, read as described under
  [include files](#include-files); a colon right after the letter is part
  of it ([l-colon](lexer/cases/10-compiler-directives/l-colon.yaml)). `O` takes a unit name, see [overlays](#overlays).
  `M` takes numbers, see [memory sizes](#memory-sizes)
  ([parameter-with-blank](lexer/cases/10-compiler-directives/parameter-with-blank.yaml)).

Anything else is error 17, at the column of the offending item: a blank
right after `$` ([dollar-blank](lexer/cases/10-compiler-directives/dollar-blank.yaml)), an unknown name such as `{$FOO}` or
`{$Z+}` ([unknown-directive](lexer/cases/10-compiler-directives/unknown-directive.yaml)), a switch list with a bad item
([switch-list-bad-second](lexer/cases/10-compiler-directives/switch-list-bad-second.yaml)), a switch letter that isn't also a parameter
directive written without its sign (`{$T}`, `{$T }`)
([switch-t-no-sign](lexer/cases/10-compiler-directives/switch-t-no-sign.yaml), [switch-b-no-sign](lexer/cases/10-compiler-directives/switch-b-no-sign.yaml), [switch-t-blank](lexer/cases/10-compiler-directives/switch-t-blank.yaml)), or a missing item
after a comma (`{$R+,}`) ([switch-trailing-comma](lexer/cases/10-compiler-directives/switch-trailing-comma.yaml)).

### Switches that must come first

The switches `A D E G K L N O T X Y` may appear only before the program
heading or right after it ([switch-n-before-header](lexer/cases/10-compiler-directives/switch-n-before-header.yaml), [switch-n-after-header](lexer/cases/10-compiler-directives/switch-n-after-header.yaml)).
After a `uses` clause or a declaration, or inside a statement part, any of
them is error 17 at the switch letter
([switch-*-after-declaration](lexer/cases/10-compiler-directives/), [switch-n-after-uses](lexer/cases/10-compiler-directives/switch-n-after-uses.yaml), [switch-n-in-statement](lexer/cases/10-compiler-directives/switch-n-in-statement.yaml)).
The other switches (`B F I P Q R S V W`) and `{$M}` may appear anywhere
([switches-local-after-declaration](lexer/cases/10-compiler-directives/switches-local-after-declaration.yaml), [m-after-declaration](lexer/cases/10-compiler-directives/m-after-declaration.yaml), [m-in-statement](lexer/cases/10-compiler-directives/m-in-statement.yaml)).

### Memory sizes

`{$M stack,heapmin,heapmax}` takes three numbers, decimal or hex
([m-hex](lexer/cases/10-compiler-directives/m-hex.yaml)). Before each number, any run of blanks, commas and semicolons
is skipped, so `{$M 16384 0 655360}`, `{$M 16384;0;655360}` and
`{$M ,16384,,0, ,655360}` are all accepted
([m-blanks](lexer/cases/10-compiler-directives/m-blanks.yaml), [m-semicolons](lexer/cases/10-compiler-directives/m-semicolons.yaml), [m-extra-commas](lexer/cases/10-compiler-directives/m-extra-commas.yaml)). Anything after the third
number is ignored ([m-trailing-text](lexer/cases/10-compiler-directives/m-trailing-text.yaml)). A number that is missing or out
of range is error 17 at the place where it starts or should start, so
`{$M}`, `{$M ABC}`, `{$M=16384}`, `{$M 16384}` and `{$M 16384,0}` are all
errors
([m-empty](lexer/cases/10-compiler-directives/m-empty.yaml), [m-letters](lexer/cases/10-compiler-directives/m-letters.yaml), [parameter-without-blank](lexer/cases/10-compiler-directives/parameter-without-blank.yaml), [m-one-number](lexer/cases/10-compiler-directives/m-one-number.yaml), [m-two-numbers](lexer/cases/10-compiler-directives/m-two-numbers.yaml)).

- `stack` is rounded down to an even number and must then be from 1024 to
  65520: 1023 and 65522 are errors, 1025 is used as 1024 and 65521 as
  65520
  ([m-stack-1023](lexer/cases/10-compiler-directives/m-stack-1023.yaml), [m-stack-1024](lexer/cases/10-compiler-directives/m-stack-1024.yaml), [m-stack-1025](lexer/cases/10-compiler-directives/m-stack-1025.yaml), [m-stack-65520](lexer/cases/10-compiler-directives/m-stack-65520.yaml), [m-stack-65521](lexer/cases/10-compiler-directives/m-stack-65521.yaml), [m-stack-65522](lexer/cases/10-compiler-directives/m-stack-65522.yaml), [m-stack-65536](lexer/cases/10-compiler-directives/m-stack-65536.yaml)).
- `heapmin` and `heapmax` are rounded up to a whole number of 16-byte
  paragraphs ([m-heap-max-16](lexer/cases/10-compiler-directives/m-heap-max-16.yaml), [m-heap-max-17](lexer/cases/10-compiler-directives/m-heap-max-17.yaml)) and may be at most
  655360 ([m-heap-max-655360](lexer/cases/10-compiler-directives/m-heap-max-655360.yaml), [m-heap-max-655361](lexer/cases/10-compiler-directives/m-heap-max-655361.yaml), [m-heap-min-655361](lexer/cases/10-compiler-directives/m-heap-min-655361.yaml), [m-heap-max-1048576](lexer/cases/10-compiler-directives/m-heap-max-1048576.yaml), [m-heap-max-hex-huge](lexer/cases/10-compiler-directives/m-heap-max-hex-huge.yaml)).
  After rounding, `heapmax` may not be below `heapmin`:
  `{$M 16384,1024,1009}` is accepted, as both are 64 paragraphs, and
  `{$M 16384,1024,1008}` is an error
  ([m-heap-min-equals-max-rounded](lexer/cases/10-compiler-directives/m-heap-min-equals-max-rounded.yaml), [m-heap-min-above-max](lexer/cases/10-compiler-directives/m-heap-min-above-max.yaml)). A number too
  large for an integer is an error too
  ([m-heap-max-not-integer](lexer/cases/10-compiler-directives/m-heap-max-not-integer.yaml), [m-heap-min-not-integer](lexer/cases/10-compiler-directives/m-heap-min-not-integer.yaml)).

### Conditional symbols

`{$DEFINE name}` defines a conditional symbol and `{$UNDEF name}` removes
it ([ifdef-defined](lexer/cases/10-compiler-directives/ifdef-defined.yaml), [undef](lexer/cases/10-compiler-directives/undef.yaml), [undef-middle](lexer/cases/10-compiler-directives/undef-middle.yaml)). Defining a symbol that is
already defined, or removing one that isn't, does nothing: after defining
`X` twice and removing it once, `X` is undefined
([define-twice](lexer/cases/10-compiler-directives/define-twice.yaml), [undef-not-defined](lexer/cases/10-compiler-directives/undef-not-defined.yaml)).

A symbol's name is read like an identifier: a letter or underscore, then
letters, digits and underscores, with case not mattering and only the first
63 characters significant
([define-underscore](lexer/cases/10-compiler-directives/define-underscore.yaml), [define-case-insensitive](lexer/cases/10-compiler-directives/define-case-insensitive.yaml), [define-63-differ](lexer/cases/10-compiler-directives/define-63-differ.yaml), [define-64-same](lexer/cases/10-compiler-directives/define-64-same.yaml)).
It ends at the first other character, so `{$DEFINE A$}` defines `A`, and it
may be a reserved word
([define-name-ends-at-other-character](lexer/cases/10-compiler-directives/define-name-ends-at-other-character.yaml), [define-symbol-is-word](lexer/cases/10-compiler-directives/define-symbol-is-word.yaml)). A missing
name, or one starting with a digit, is error 2 where the name should start.
This goes for `{$UNDEF}`, `{$IFDEF}` and `{$IFNDEF}` too
([define-no-name](lexer/cases/10-compiler-directives/define-no-name.yaml), [define-digit-first](lexer/cases/10-compiler-directives/define-digit-first.yaml), [undef-no-name](lexer/cases/10-compiler-directives/undef-no-name.yaml), [ifdef-no-name](lexer/cases/10-compiler-directives/ifdef-no-name.yaml), [ifndef-no-name](lexer/cases/10-compiler-directives/ifndef-no-name.yaml)).

`VER70`, `MSDOS`, `CPU86` and `CPU87` are defined from the start;
`VER60`, `DPMI` and `WINDOWS` are not
([predefined-symbols](lexer/cases/10-compiler-directives/predefined-symbols.yaml), [not-predefined-symbols](lexer/cases/10-compiler-directives/not-predefined-symbols.yaml)). `CPU87` is defined when
`TPC` finds a floating-point unit as it starts, as it does on the reference
machine; nothing else turns it on or off.

`TPC`'s `/D` option defines more symbols before the program is read: names
separated by `;` or `,`, read like those of `{$DEFINE}`. `/D` alone defines
nothing. A name that can't be a symbol, such as `/D1X`, is error 130
("Error in initial conditional defines"), before any token
([d-option](lexer/cases/10-compiler-directives/d-option.yaml), [d-option-lower-case](lexer/cases/10-compiler-directives/d-option-lower-case.yaml), [d-option-two](lexer/cases/10-compiler-directives/d-option-two.yaml), [d-option-comma](lexer/cases/10-compiler-directives/d-option-comma.yaml), [d-option-empty](lexer/cases/10-compiler-directives/d-option-empty.yaml), [d-option-digit-first](lexer/cases/10-compiler-directives/d-option-digit-first.yaml)).

The
defined symbols, these four included, share 1024 bytes, each taking its
length plus one. A `{$DEFINE}` that doesn't fit is error 127 at its name.
Removing a symbol, even a predefined one, makes room again
([symbols-full](lexer/cases/10-compiler-directives/symbols-full.yaml), [symbols-over](lexer/cases/10-compiler-directives/symbols-over.yaml), [symbols-undef-frees](lexer/cases/10-compiler-directives/symbols-undef-frees.yaml), [symbols-undef-frees-over](lexer/cases/10-compiler-directives/symbols-undef-frees-over.yaml)).

### Conditional compilation

The conditional directives work at this level: skipped text produces no
tokens ([ifdef-skips](lexer/cases/10-compiler-directives/ifdef-skips.yaml)).

- `{$IFDEF name}` compiles the text up to its `{$ELSE}` or `{$ENDIF}` if
  `name` is defined, and skips it otherwise. `{$IFNDEF name}` does the
  opposite
  ([ifdef-defined](lexer/cases/10-compiler-directives/ifdef-defined.yaml), [else-defined](lexer/cases/10-compiler-directives/else-defined.yaml), [else-undefined](lexer/cases/10-compiler-directives/else-undefined.yaml), [ifndef-defined](lexer/cases/10-compiler-directives/ifndef-defined.yaml), [ifndef-undefined](lexer/cases/10-compiler-directives/ifndef-undefined.yaml)).
- `{$IFOPT X+}` and `{$IFOPT X-}` test whether switch `X` is on or off
  ([ifopt-r-plus](lexer/cases/10-compiler-directives/ifopt-r-plus.yaml), [ifopt-r-minus](lexer/cases/10-compiler-directives/ifopt-r-minus.yaml), [ifopt-after-switch](lexer/cases/10-compiler-directives/ifopt-after-switch.yaml), [ifopt-i](lexer/cases/10-compiler-directives/ifopt-i.yaml), [ifopt-lower-case](lexer/cases/10-compiler-directives/ifopt-lower-case.yaml)).
  After any blanks comes a switch letter and its sign; anything after that
  is ignored ([ifopt-blanks](lexer/cases/10-compiler-directives/ifopt-blanks.yaml), [ifopt-trailing-text](lexer/cases/10-compiler-directives/ifopt-trailing-text.yaml)). A letter that isn't
  a switch (`Z`), one that is only a parameter directive (`M`), or a
  missing sign is error 17 at the letter
  ([ifopt-unknown-switch](lexer/cases/10-compiler-directives/ifopt-unknown-switch.yaml), [ifopt-parameter-directive](lexer/cases/10-compiler-directives/ifopt-parameter-directive.yaml), [ifopt-no-sign](lexer/cases/10-compiler-directives/ifopt-no-sign.yaml)).
- `{$ELSE}` switches from compiling to skipping or back. A second `{$ELSE}`
  at the same level switches again: in `{$IFDEF X} a {$ELSE} b {$ELSE} c
  {$ENDIF}`, `a` and `c` are compiled when `X` is defined, and only `b`
  when it isn't ([else-twice-defined](lexer/cases/10-compiler-directives/else-twice-defined.yaml), [else-twice-undefined](lexer/cases/10-compiler-directives/else-twice-undefined.yaml)).
- Conditionals nest, in compiled and in skipped text alike
  ([nested-compiled](lexer/cases/10-compiler-directives/nested-compiled.yaml), [nested-ifdef-skipped](lexer/cases/10-compiler-directives/nested-ifdef-skipped.yaml), [nested-ifndef-skipped](lexer/cases/10-compiler-directives/nested-ifndef-skipped.yaml), [nested-ifopt-skipped](lexer/cases/10-compiler-directives/nested-ifopt-skipped.yaml), [nested-else-skipped](lexer/cases/10-compiler-directives/nested-else-skipped.yaml)).
  In skipped text, only the conditional directives count: `{$IFDEF}`,
  `{$IFNDEF}` and `{$IFOPT}` open a level, `{$ENDIF}` closes one, and an
  `{$ELSE}` or `{$ENDIF}` at the outermost level ends the skipping. All
  other directives there are ignored, even unknown ones, and so is anything
  after a directive's name: `{$ENDIF junk}` ends skipped text but
  `{$ENDIFX}` doesn't
  ([skipped-unknown-directive](lexer/cases/10-compiler-directives/skipped-unknown-directive.yaml), [skipped-define](lexer/cases/10-compiler-directives/skipped-define.yaml), [skipped-endif-with-text](lexer/cases/10-compiler-directives/skipped-endif-with-text.yaml), [skipped-endif-longer-name](lexer/cases/10-compiler-directives/skipped-endif-longer-name.yaml)).
- `{$ELSE}` or `{$ENDIF}` with no conditional open is error 128 at its
  name ([else-without-ifdef](lexer/cases/10-compiler-directives/else-without-ifdef.yaml), [endif-without-ifdef](lexer/cases/10-compiler-directives/endif-without-ifdef.yaml)). A conditional still
  open at the program's final `end.` is error 129 at the `.`
  ([ifdef-open-at-final-end](lexer/cases/10-compiler-directives/ifdef-open-at-final-end.yaml)).

Skipped text is still read for comments and quoted strings, though: a
`{$ENDIF}` inside a comment or after an apostrophe on the same line doesn't
count ([ifdef-skips-comments](lexer/cases/10-compiler-directives/ifdef-skips-comments.yaml), [ifdef-skips-strings](lexer/cases/10-compiler-directives/ifdef-skips-strings.yaml)). A string still open
at the end of a line just ends there ([ifdef-skips](lexer/cases/10-compiler-directives/ifdef-skips.yaml)). A comment still
open at the end of the file is error 10, and a missing `{$ENDIF}` is error
129, both at the end of the file
([ifdef-unterminated-comment](lexer/cases/10-compiler-directives/ifdef-unterminated-comment.yaml), [ifdef-unterminated](lexer/cases/10-compiler-directives/ifdef-unterminated.yaml)).

### Include files

`{$I name}` reads the named file in place of the directive, then goes on
with the rest of the directive's line. Include files may include others
([include](lexer/cases/14-include-files/include.yaml), [rest-of-line](lexer/cases/14-include-files/rest-of-line.yaml), [two-on-a-line](lexer/cases/14-include-files/two-on-a-line.yaml), [nested](lexer/cases/14-include-files/nested.yaml)).

- The name is the text after the `I` and any blanks, up to the next blank,
  `*` or `}`; text after a blank is ignored. Its letters are read in upper
  case, other characters as they are, and only its first 79 characters are
  kept. A name without an extension gets
  `.PAS`, and `{$I}` alone looks for `.PAS`. A colon right after the `I` is
  part of the name
  ([lower-case-name](lexer/cases/14-include-files/lower-case-name.yaml), [name-then-text](lexer/cases/14-include-files/name-then-text.yaml), [name-ends-at-star](lexer/cases/14-include-files/name-ends-at-star.yaml), [name-with-colon](lexer/cases/14-include-files/name-with-colon.yaml), [i-colon-missing](lexer/cases/14-include-files/i-colon-missing.yaml), [name-79-characters](lexer/cases/14-include-files/name-79-characters.yaml), [default-extension](lexer/cases/14-include-files/default-extension.yaml), [default-extension-only](lexer/cases/14-include-files/default-extension-only.yaml), [no-name](lexer/cases/14-include-files/no-name.yaml), [name-tilde](lexer/cases/14-include-files/name-tilde.yaml)).
- A missing file is error 15, just after the directive; the message names
  the file that was looked for ([missing-file](lexer/cases/14-include-files/missing-file.yaml)).
- Open include files share a limited room, and longer names take more of
  it: 218 nested files with 8-character names fit but 219 don't, and 191
  with 12-character names fit but 192 don't. The one that doesn't fit is
  error 18 just after its directive, in the file that includes it. A file
  that includes itself ends the same way
  ([depth-218-short-names](lexer/cases/14-include-files/depth-218-short-names.yaml), [depth-219-short-names](lexer/cases/14-include-files/depth-219-short-names.yaml), [depth-191-long-names](lexer/cases/14-include-files/depth-191-long-names.yaml), [depth-192-long-names](lexer/cases/14-include-files/depth-192-long-names.yaml), [includes-itself](lexer/cases/14-include-files/includes-itself.yaml)).
- Each file is read on its own terms: its own lines, with error 11 for a
  long one, and ^Z ending just that file. Its last line needs no line end
  ([long-line-in-include](lexer/cases/14-include-files/long-line-in-include.yaml), [ctrl-z-ends-include](lexer/cases/14-include-files/ctrl-z-ends-include.yaml), [no-final-line-end](lexer/cases/14-include-files/no-final-line-end.yaml)).
  An error is reported in the file it is in, at that file's line
  ([error-in-include](lexer/cases/14-include-files/error-in-include.yaml), [error-after-include](lexer/cases/14-include-files/error-after-include.yaml)).
- Nothing crosses the end of an include file. A token ends there: in
  `1{$I DIGIT.INC}2`, `1` and the include's first token are separate
  tokens ([token-across-files](lexer/cases/14-include-files/token-across-files.yaml)). A comment still open there is error 10,
  and a conditional still open there, compiled or skipped, is error 129,
  both at the line after its last line, in the include file
  ([comment-open-at-end](lexer/cases/14-include-files/comment-open-at-end.yaml), [brace-comment-open-at-end](lexer/cases/14-include-files/brace-comment-open-at-end.yaml), [ifdef-open-at-end](lexer/cases/14-include-files/ifdef-open-at-end.yaml), [ifdef-skipping-at-end](lexer/cases/14-include-files/ifdef-skipping-at-end.yaml)).
  An `{$ENDIF}` in an include file can't close an `{$IFDEF}` of the file
  that includes it: error 128 ([endif-closes-outer-ifdef](lexer/cases/14-include-files/endif-closes-outer-ifdef.yaml)).
- Defined symbols and switches set in an include file stay set after it
  ([define-carries-over](lexer/cases/14-include-files/define-carries-over.yaml), [switch-carries-over](lexer/cases/14-include-files/switch-carries-over.yaml)).
- In skipped text, `{$I}` is skipped like any other directive
  ([include-in-skipped-text](lexer/cases/14-include-files/include-in-skipped-text.yaml)).
- `{$I}` inside any statement part is error 118, just after the directive,
  before `TPC` looks for the file ([in-statement](lexer/cases/14-include-files/in-statement.yaml), [in-procedure-body](lexer/cases/14-include-files/in-procedure-body.yaml)).
- The program can't end in an include file: with the main `begin … end.`
  in one, `TPC` reads on to the include file's end and reports error 10
  just after the `.` ([final-end-in-include](lexer/cases/14-include-files/final-end-in-include.yaml)).

### Overlays

`{$O name}` marks the program's unit `name` for overlaying. The name isn't
case sensitive, and text after it is ignored
([o-overlay-unit](lexer/cases/10-compiler-directives/o-overlay-unit.yaml), [o-lower-case](lexer/cases/10-compiler-directives/o-lower-case.yaml), [o-text-after-name](lexer/cases/10-compiler-directives/o-text-after-name.yaml), [o-without-far-calls](lexer/cases/10-compiler-directives/o-without-far-calls.yaml)).
Errors:

- no name, as in `{$O}`: error 2 where the name should start
  ([o-no-name](lexer/cases/10-compiler-directives/o-no-name.yaml));
- a unit the program doesn't use: error 3 ([o-unknown-unit](lexer/cases/10-compiler-directives/o-unknown-unit.yaml));
- a unit not compiled with `{$O+}`, or one of the standard units such as
  `Crt`: error 144 ([o-unit-not-overlay](lexer/cases/10-compiler-directives/o-unit-not-overlay.yaml), [o-without-overlay-unit](lexer/cases/10-compiler-directives/o-without-overlay-unit.yaml));
- `{$O name}` in a unit: error 17 ([o-in-unit](lexer/cases/10-compiler-directives/o-in-unit.yaml)).

### `)` ending a `(*$` directive

In a directive written with `(*$`, a `)` directly after the directive's
last item ends the comment, as `*)` would, in exactly these cases:

- `(*$M stack,heapmin,heapmax)`, when `heapmax` in paragraphs (rounded up)
  is 42 more than a multiple of 256: 672 bytes (42 paragraphs) and 4768
  bytes (298 paragraphs) end the comment, and 688 bytes (43 paragraphs)
  doesn't
  ([paren-m-close-42](lexer/cases/10-compiler-directives/paren-m-close-42.yaml), [paren-m-close-298](lexer/cases/10-compiler-directives/paren-m-close-298.yaml), [paren-m-close-43](lexer/cases/10-compiler-directives/paren-m-close-43.yaml), [paren-m-close-junk](lexer/cases/10-compiler-directives/paren-m-close-junk.yaml)).
- `(*$UNDEF name)`, when `name` is defined and 42 characters long
  ([paren-undef-close-42](lexer/cases/10-compiler-directives/paren-undef-close-42.yaml), [paren-undef-close-41](lexer/cases/10-compiler-directives/paren-undef-close-41.yaml)).
- `(*$DEFINE name)`, when `name` isn't defined yet and, once it is, the
  defined symbols take up 222 more than a multiple of 256 bytes, counted as
  under [conditional symbols](#conditional-symbols)
  ([paren-define-close](lexer/cases/10-compiler-directives/paren-define-close.yaml), [paren-define-no-close](lexer/cases/10-compiler-directives/paren-define-no-close.yaml)).
- `(*$R)` in skipped text. In compiled text, `(*$R)` stays open
  ([paren-r-close-skipped](lexer/cases/10-compiler-directives/paren-r-close-skipped.yaml), [paren-s-skipped](lexer/cases/10-compiler-directives/paren-s-skipped.yaml), [paren-r-compiled](lexer/cases/10-compiler-directives/paren-r-compiled.yaml)).

All other directives stay open past such a `)`: switches and switch lists,
the other parameter directives (`{$L}` included), `{$IFDEF}`, `{$IFNDEF}`,
`{$IFOPT}`, `{$ELSE}`, `{$ENDIF}`, `{$DEFINE}` of a defined symbol and
`{$UNDEF}` of an undefined one
([paren-switch-no-close](lexer/cases/10-compiler-directives/paren-switch-no-close.yaml), [paren-switch-list-no-close](lexer/cases/10-compiler-directives/paren-switch-list-no-close.yaml), [paren-parameter-no-close](lexer/cases/10-compiler-directives/paren-parameter-no-close.yaml), [paren-l-no-close](lexer/cases/10-compiler-directives/paren-l-no-close.yaml), [paren-ifdef-no-close](lexer/cases/10-compiler-directives/paren-ifdef-no-close.yaml), [paren-ifndef-no-close](lexer/cases/10-compiler-directives/paren-ifndef-no-close.yaml), [paren-ifopt-no-close](lexer/cases/10-compiler-directives/paren-ifopt-no-close.yaml), [paren-else-no-close](lexer/cases/10-compiler-directives/paren-else-no-close.yaml), [paren-endif-no-close](lexer/cases/10-compiler-directives/paren-endif-no-close.yaml), [paren-define-defined-no-close](lexer/cases/10-compiler-directives/paren-define-defined-no-close.yaml), [paren-undef-not-defined-no-close](lexer/cases/10-compiler-directives/paren-undef-not-defined-no-close.yaml)).
`{$O}` is untested, as it needs units.

## `asm` blocks

After the reserved word `asm`, the text up to the block's `end` is read by
`TPC`'s built-in assembler, not by the Pascal lexer. No tokens are
delivered for it: the token after `ASM` is the one after the block's `end`
([block](lexer/cases/15-asm-blocks/block.yaml), [empty-block](lexer/cases/15-asm-blocks/empty-block.yaml)). The body of an `assembler` procedure is such a
block too ([assembler-procedure](lexer/cases/15-asm-blocks/assembler-procedure.yaml)). This section says how the assembler
splits a block into statements and words. Which instructions and operands
it accepts, and how it encodes them, are not covered.

### Statements

- A statement lies on one line: a line end ends it, so a statement can't go
  on to the next line ([block](lexer/cases/15-asm-blocks/block.yaml), [statement-across-lines](lexer/cases/15-asm-blocks/statement-across-lines.yaml)).
- `;` ends a statement too. Any number of `;` may stand between and around
  statements ([semicolons](lexer/cases/15-asm-blocks/semicolons.yaml)). `;` doesn't start a comment: the text after
  it is the next statement ([semicolon-is-not-a-comment](lexer/cases/15-asm-blocks/semicolon-is-not-a-comment.yaml)). Two statements
  on one line need something between them: in `mov ax, 4 mov W, ax` the
  second `mov` is an operand, and is error 3
  ([two-statements-no-separator](lexer/cases/15-asm-blocks/two-statements-no-separator.yaml)).
- Between statements, the text is read as Pascal text is between tokens:
  blanks, line ends, comments of both kinds and compiler directives,
  conditional directives included, which choose the statements that are
  assembled
  ([brace-comment-between](lexer/cases/15-asm-blocks/brace-comment-between.yaml), [paren-star-comment-between](lexer/cases/15-asm-blocks/paren-star-comment-between.yaml), [comment-across-lines](lexer/cases/15-asm-blocks/comment-across-lines.yaml), [ifdef-between-statements](lexer/cases/15-asm-blocks/ifdef-between-statements.yaml)).
  So a comment separates two statements as `;` does. `{$I}` there is error
  118, as everywhere in a statement part ([include-in-block](lexer/cases/15-asm-blocks/include-in-block.yaml)).
- Inside a statement, `{` and `(*` end the statement where they stand, and
  the comment is then read as between statements. A comment or directive in
  the middle of a statement leaves the statement incomplete, error 5 at the
  `{` or `(`
  ([brace-comment-in-operand](lexer/cases/15-asm-blocks/brace-comment-in-operand.yaml), [paren-star-comment-in-operand](lexer/cases/15-asm-blocks/paren-star-comment-in-operand.yaml), [ifdef-in-operand](lexer/cases/15-asm-blocks/ifdef-in-operand.yaml)).
  A `(` not followed directly by `*` is a symbol ([paren-not-comment](lexer/cases/15-asm-blocks/paren-not-comment.yaml)), and
  so is `}`: `mov ax, 4 }` is error 5 at the `}` ([close-brace](lexer/cases/15-asm-blocks/close-brace.yaml)).
- The lines of a block are read like other lines: a line over 127
  characters is error 11, NULs are dropped, and the end of the file, or ^Z,
  inside a block is error 10 ([line-127](lexer/cases/15-asm-blocks/line-127.yaml), [line-128](lexer/cases/15-asm-blocks/line-128.yaml), [nul-dropped](lexer/cases/15-asm-blocks/nul-dropped.yaml), [end-of-file](lexer/cases/15-asm-blocks/end-of-file.yaml), [ctrl-z](lexer/cases/15-asm-blocks/ctrl-z.yaml)).

### Where a block ends

- At the start of a statement, `end` in any case ends the block unless the
  next character is a letter, a digit or `_`: `end1`, `endx` and `end_`
  start a statement and are error 5 just after the word, and a statement
  may start with other words beginning with `e`
  ([end-mixed-case](lexer/cases/15-asm-blocks/end-mixed-case.yaml), [end-then-digit](lexer/cases/15-asm-blocks/end-then-digit.yaml), [end-then-letter](lexer/cases/15-asm-blocks/end-then-letter.yaml), [end-then-underscore](lexer/cases/15-asm-blocks/end-then-underscore.yaml), [label-starting-with-e](lexer/cases/15-asm-blocks/label-starting-with-e.yaml)).
  Any other character after `end`, such as `$`, `?` or character 233, ends
  the block and is then read as Pascal text
  ([end-then-dollar](lexer/cases/15-asm-blocks/end-then-dollar.yaml), [end-then-question-mark](lexer/cases/15-asm-blocks/end-then-question-mark.yaml), [end-then-high-character](lexer/cases/15-asm-blocks/end-then-high-character.yaml)).
- Inside a statement, the word `end` ends the statement where it starts,
  and so ends the block. `mov W, ax end` needs no `;` before `end`, and
  `@@x: end` ends the block after the label
  ([end-after-statement](lexer/cases/15-asm-blocks/end-after-statement.yaml), [end-after-label](lexer/cases/15-asm-blocks/end-after-label.yaml)). Where an operand is still
  missing, as in `mov ax, end`, it is error 5 at `end` ([end-in-operand](lexer/cases/15-asm-blocks/end-in-operand.yaml)).
  Character 233 before `end` is a [blank](#blanks-in-a-statement), so
  `end` still ends the block ([high-character-before-end](lexer/cases/15-asm-blocks/high-character-before-end.yaml)).
- `end` followed directly by DEL (127) at the start of a statement makes
  `TPC` loop forever: it never finishes compiling the program
  ([end-then-del](lexer/cases/15-asm-blocks/end-then-del.yaml)).
- `end` inside a string is part of the string ([end-in-string](lexer/cases/15-asm-blocks/end-in-string.yaml)).

### Blanks in a statement

Inside a statement, characters 1 to 32, DEL (127) and characters 128 to
255 are blanks: they separate words and are otherwise ignored. Character
233 inside `ax` makes two words, `a` and `x`, and `a` is error 3. Blanks
at the end of a line are ignored
([control-characters](lexer/cases/15-asm-blocks/control-characters.yaml), [high-characters-are-blanks](lexer/cases/15-asm-blocks/high-characters-are-blanks.yaml), [del-is-blank](lexer/cases/15-asm-blocks/del-is-blank.yaml), [high-character-splits-word](lexer/cases/15-asm-blocks/high-character-splits-word.yaml), [blanks-at-end-of-line](lexer/cases/15-asm-blocks/blanks-at-end-of-line.yaml)).

### Words

- A word is a run of letters, digits and the characters `_ @ $ & ?`:
  `@@a?$&@b` is one label ([word-characters](lexer/cases/15-asm-blocks/word-characters.yaml)). Case doesn't matter
  ([case-insensitive](lexer/cases/15-asm-blocks/case-insensitive.yaml)).
- Only the first 32 characters of a word count; the rest are read and
  ignored. A Pascal identifier longer than 32 characters can't be named in
  full in a block, and one of exactly 32 characters is found by any longer
  word that starts with it
  ([identifier-39-characters](lexer/cases/15-asm-blocks/identifier-39-characters.yaml), [identifier-32-significant](lexer/cases/15-asm-blocks/identifier-32-significant.yaml)). For numbers,
  see [below](#numbers-in-a-statement).
- A word that starts with a digit or `$` is a
  [number](#numbers-in-a-statement).
- The first word of a statement is an instruction, unless `:` follows it,
  which makes it a label: one declared in a `label` part, or one starting
  with `@@`, which needs no declaration. An undeclared label is error 3
  just after the word. After a label, the next word is again an
  instruction; a second label there is error 5 at its start
  ([label-then-instruction](lexer/cases/15-asm-blocks/label-then-instruction.yaml), [label-starting-with-e](lexer/cases/15-asm-blocks/label-starting-with-e.yaml), [label-undeclared](lexer/cases/15-asm-blocks/label-undeclared.yaml), [two-labels](lexer/cases/15-asm-blocks/two-labels.yaml)).
  After a prefix such as `rep`, the next word is an instruction too, and a
  prefix may stand alone ([prefix-then-instruction](lexer/cases/15-asm-blocks/prefix-then-instruction.yaml), [prefix-alone](lexer/cases/15-asm-blocks/prefix-alone.yaml)). A
  first word that isn't an instruction, such as a register, is error 5
  just after it ([register-first](lexer/cases/15-asm-blocks/register-first.yaml)).
- In the operands, these 41 words are reserved: they never name a Pascal
  identifier ([reserved-*](lexer/cases/15-asm-blocks/), [operator-*](lexer/cases/15-asm-blocks/)):

  `ah al and ax bh bl bp bx byte ch cl cs cx dh di dl ds dword dx es far
  high low mod near not offset or ptr qword seg shl shr si sp ss st tbyte
  type word xor`

  Every other word in the operands names a Pascal identifier, instruction
  names included: `mov Mov, ax` stores into the variable `Mov`
  ([instruction-as-variable](lexer/cases/15-asm-blocks/instruction-as-variable.yaml)). A Pascal reserved word such as `begin` is
  error 3 there, as an unknown identifier
  ([pascal-reserved-word-as-operand](lexer/cases/15-asm-blocks/pascal-reserved-word-as-operand.yaml)).
- `&` before a word makes it name a Pascal identifier even when it is
  reserved: `&AX` is the variable `AX` and `ax` the register
  ([ampersand-register-name](lexer/cases/15-asm-blocks/ampersand-register-name.yaml)). Only one `&` is taken off: `&&W` is error 3.
  `&` alone is error 5 ([ampersand-twice](lexer/cases/15-asm-blocks/ampersand-twice.yaml), [ampersand-alone](lexer/cases/15-asm-blocks/ampersand-alone.yaml)).

### Numbers in a statement

A number is a word that starts with a digit or with `$`. A word that
starts with a letter is never a number: `FFh` is an identifier
([hex-letter-first](lexer/cases/15-asm-blocks/hex-letter-first.yaml)). Errors in a number are reported at its start.

- After `$` come hex digits. `$` alone is 0
  ([hex-dollar](lexer/cases/15-asm-blocks/hex-dollar.yaml), [dollar-alone](lexer/cases/15-asm-blocks/dollar-alone.yaml)).
- Otherwise, when the last character is a digit, the number is decimal
  ([decimal](lexer/cases/15-asm-blocks/decimal.yaml)). When it is a letter, it is a suffix, and the characters
  before it are the digits: `D` for decimal, `B` binary, `O` octal and `H`
  hex, in either case
  ([decimal-suffix](lexer/cases/15-asm-blocks/decimal-suffix.yaml), [decimal-suffix-upper](lexer/cases/15-asm-blocks/decimal-suffix-upper.yaml), [binary](lexer/cases/15-asm-blocks/binary.yaml), [octal](lexer/cases/15-asm-blocks/octal.yaml), [hex-suffix](lexer/cases/15-asm-blocks/hex-suffix.yaml), [hex-suffix-upper](lexer/cases/15-asm-blocks/hex-suffix-upper.yaml), [zero-h](lexer/cases/15-asm-blocks/zero-h.yaml)).
  Any other last character, such as `Q` or `X`, is error 7
  ([octal-q](lexer/cases/15-asm-blocks/octal-q.yaml), [bad-suffix](lexer/cases/15-asm-blocks/bad-suffix.yaml), [one-end](lexer/cases/15-asm-blocks/one-end.yaml)). Only the last character is a
  suffix: `0Bh` is 11 ([hex-b-digit](lexer/cases/15-asm-blocks/hex-b-digit.yaml)).
- The digits are `0` to `9` for decimal, `0` and `1` for binary, `0` to
  `7` for octal, and `0` to `9` and `A` to `F` for hex, where `@` and `?`
  are hex digits too, worth 9 and 8: `$1@` and `1@h` are 25, `$?` and
  `0?h` are 8
  ([hex-at-dollar](lexer/cases/15-asm-blocks/hex-at-dollar.yaml), [hex-at-suffix](lexer/cases/15-asm-blocks/hex-at-suffix.yaml), [hex-question-dollar](lexer/cases/15-asm-blocks/hex-question-dollar.yaml), [hex-question-suffix](lexer/cases/15-asm-blocks/hex-question-suffix.yaml)).
  Any other character among the digits is error 7, `H` after `$` included
  ([bad-decimal-digit](lexer/cases/15-asm-blocks/bad-decimal-digit.yaml), [bad-binary-digit](lexer/cases/15-asm-blocks/bad-binary-digit.yaml), [bad-octal-digit](lexer/cases/15-asm-blocks/bad-octal-digit.yaml), [bad-hex-digit](lexer/cases/15-asm-blocks/bad-hex-digit.yaml), [bad-hex-underscore](lexer/cases/15-asm-blocks/bad-hex-underscore.yaml), [bad-hex-ampersand](lexer/cases/15-asm-blocks/bad-hex-ampersand.yaml), [bad-hex-dollar-suffix](lexer/cases/15-asm-blocks/bad-hex-dollar-suffix.yaml)).
- The value is a 32-bit number: `4294967295`, `0FFFFFFFFh` and
  `37777777777o` are the largest, and a value one more is error 76
  ([decimal-max](lexer/cases/15-asm-blocks/decimal-max.yaml), [decimal-over](lexer/cases/15-asm-blocks/decimal-over.yaml), [hex-max](lexer/cases/15-asm-blocks/hex-max.yaml), [hex-over](lexer/cases/15-asm-blocks/hex-over.yaml), [octal-max](lexer/cases/15-asm-blocks/octal-max.yaml), [octal-over](lexer/cases/15-asm-blocks/octal-over.yaml)).
  The digits are read from the left. For each one, the value so far is
  first multiplied by the base, which is error 76 if the result needs more
  than 32 bits; then a character that isn't a digit of the base is error
  7; then the digit is added, again error 76 if the sum needs more than 32
  bits. So `429496729A0` is error 7 and `4294967295A0` is error 76
  ([decimal-over-multiplying](lexer/cases/15-asm-blocks/decimal-over-multiplying.yaml), [bad-digit-before-overflow](lexer/cases/15-asm-blocks/bad-digit-before-overflow.yaml), [overflow-before-bad-digit](lexer/cases/15-asm-blocks/overflow-before-bad-digit.yaml)).
- Only a number's first 32 characters count, so a longer number loses its
  end, suffix and all: 32 zeros and a `1` is 0, and 31 zeros, `F` and `h`
  is error 7, since `F` is then its last character
  ([digits-32](lexer/cases/15-asm-blocks/digits-32.yaml), [digits-33](lexer/cases/15-asm-blocks/digits-33.yaml), [hex-32-characters](lexer/cases/15-asm-blocks/hex-32-characters.yaml), [hex-33-characters](lexer/cases/15-asm-blocks/hex-33-characters.yaml)).
  A binary number with 32 digits is read as a decimal number, which is
  error 76: the longest binary number has 31 digits
  ([binary-31-digits](lexer/cases/15-asm-blocks/binary-31-digits.yaml), [binary-32-digits](lexer/cases/15-asm-blocks/binary-32-digits.yaml)).

### Strings in a statement

- A string is the characters between two `'` or two `"` on one line. The
  same quote twice stands for one, and the other quote is an ordinary
  character
  ([string-double-quotes](lexer/cases/15-asm-blocks/string-double-quotes.yaml), [string-doubled-apostrophe](lexer/cases/15-asm-blocks/string-doubled-apostrophe.yaml), [db-doubled-double-quote](lexer/cases/15-asm-blocks/db-doubled-double-quote.yaml), [string-apostrophe-in-double-quotes](lexer/cases/15-asm-blocks/string-apostrophe-in-double-quotes.yaml), [db-quotes](lexer/cases/15-asm-blocks/db-quotes.yaml)).
  A line end before the closing quote is error 8 at the opening quote
  ([string-unterminated](lexer/cases/15-asm-blocks/string-unterminated.yaml)). Inside a string, `;`, `{`, `(*`, `end`, DEL and
  characters above 127 are characters like any other
  ([string-semicolon](lexer/cases/15-asm-blocks/string-semicolon.yaml), [string-brace](lexer/cases/15-asm-blocks/string-brace.yaml), [db-separators-in-string](lexer/cases/15-asm-blocks/db-separators-in-string.yaml), [db-high-characters](lexer/cases/15-asm-blocks/db-high-characters.yaml), [end-in-string](lexer/cases/15-asm-blocks/end-in-string.yaml)).
- After `db`, a string stands for all its characters ([db-string](lexer/cases/15-asm-blocks/db-string.yaml)).
  Elsewhere it is a number: its character codes as digits in base 256, the
  last character lowest, keeping the low 32 bits. `'A'` is 65, `'AB'` is
  16706, `''` is 0, `'ABCD'` is 1094861636, and `'ABCDE'` is 1111704645,
  the value of `'BCDE'`
  ([string-one](lexer/cases/15-asm-blocks/string-one.yaml), [string-two](lexer/cases/15-asm-blocks/string-two.yaml), [string-empty](lexer/cases/15-asm-blocks/string-empty.yaml), [string-four](lexer/cases/15-asm-blocks/string-four.yaml), [string-five](lexer/cases/15-asm-blocks/string-five.yaml)).
  A value too large for where it is used is error 76, such as `'ABC'` as a
  16-bit operand ([string-three](lexer/cases/15-asm-blocks/string-three.yaml)).

### Symbols in a statement

Every other character is a symbol by itself. `! # % \ ^ = < > | ~` and
`` ` `` between two numbers in an operand are error 5 at the symbol
([symbol-*](lexer/cases/15-asm-blocks/)).

## Real values

Each case here prints the exact 80-bit Extended value of a real literal.
`TPC`'s conversion is not correctly rounded, so an implementation has to
reproduce `TPC`'s own arithmetic. That arithmetic isn't known yet
(issue #10). What is known, and checked against every case here by
`bazel test //harness:cases_test`:

- Only the first 19 significant digits count; any digits after them are
  ignored, as if they were 0
  ([digits-*](lexer/cases/13-real-values/), [long-mantissa](lexer/cases/13-real-values/long-mantissa.yaml), [many-integer-digits](lexer/cases/13-real-values/many-integer-digits.yaml), [third](lexer/cases/13-real-values/third.yaml), [leading-zeros](lexer/cases/13-real-values/leading-zeros.yaml), [trailing-zeros-exponent](lexer/cases/13-real-values/trailing-zeros-exponent.yaml)).
  Below, N is those digits read as an integer, without trailing zeros, and
  k is the power of ten that scales N to the literal's value.
- A literal whose first 19 digits are `1.189731495357231765e4932` or
  more is error 6, although that is still a little below the largest
  Extended value, `1.18973149535723176502…e4932`. So
  `1.189731495357231764e4932` is the largest accepted literal, and the
  largest Extended value written to 20 digits is an error
  ([largest-accepted](lexer/cases/13-real-values/largest-accepted.yaml), [largest-accepted-plus-1](lexer/cases/13-real-values/largest-accepted-plus-1.yaml), [max](lexer/cases/13-real-values/max.yaml), [limit-1_1897314e4932](lexer/cases/13-real-values/limit-1_1897314e4932.yaml), [limit-1_189731e4932](lexer/cases/13-real-values/limit-1_189731e4932.yaml), [limit-1_18973e4932](lexer/cases/13-real-values/limit-1_18973e4932.yaml), [limit-1_1897e4932](lexer/cases/13-real-values/limit-1_1897e4932.yaml), [limit-1_189e4932](lexer/cases/13-real-values/limit-1_189e4932.yaml), [limit-1_18e4932](lexer/cases/13-real-values/limit-1_18e4932.yaml), [limit-1_1e4932](lexer/cases/13-real-values/limit-1_1e4932.yaml), [limit-1e4932](lexer/cases/13-real-values/limit-1e4932.yaml)).
- A literal whose first 19 digits are below the smallest normal Extended
  value (`3.36210314311209350626…e-4932`) becomes 0. There are no
  denormals. So `3.362103143112093507e-4932` is the smallest literal that
  isn't 0, and `3.362103143112093506e-4932` is 0
  ([smallest-nonzero](lexer/cases/13-real-values/smallest-nonzero.yaml), [smallest-nonzero-minus-1](lexer/cases/13-real-values/smallest-nonzero-minus-1.yaml), [min-normal](lexer/cases/13-real-values/min-normal.yaml), [denormal](lexer/cases/13-real-values/denormal.yaml), [underflow](lexer/cases/13-real-values/underflow.yaml), [limit-1em4000](lexer/cases/13-real-values/limit-1em4000.yaml), [limit-1em4400](lexer/cases/13-real-values/limit-1em4400.yaml), [limit-1em4900](lexer/cases/13-real-values/limit-1em4900.yaml), [limit-1em4920](lexer/cases/13-real-values/limit-1em4920.yaml), [limit-1em4930](lexer/cases/13-real-values/limit-1em4930.yaml), [limit-1em4931](lexer/cases/13-real-values/limit-1em4931.yaml), [limit-2em4932](lexer/cases/13-real-values/limit-2em4932.yaml), [limit-3em4932](lexer/cases/13-real-values/limit-3em4932.yaml), [limit-3_4em4932](lexer/cases/13-real-values/limit-3_4em4932.yaml), [limit-4em4932](lexer/cases/13-real-values/limit-4em4932.yaml), [limit-5em4932](lexer/cases/13-real-values/limit-5em4932.yaml)).
- With k from 0 to 27, the value is correctly rounded
  ([one](lexer/cases/13-real-values/one.yaml), [halfway](lexer/cases/13-real-values/halfway.yaml), [scale-up-*](lexer/cases/13-real-values/)). 10^27 is the largest power of ten that
  Extended holds exactly. With k above 27, it is at most one unit in the
  last place off, either way. With k below 0, it is from 10 units below to
  2 units above the correctly rounded value
  ([tenth](lexer/cases/13-real-values/tenth.yaml), [scale-??](lexer/cases/13-real-values/), [random-*](lexer/cases/13-real-values/)).

## Not covered yet

- Which instructions and operands an [`asm` block](#asm-blocks) accepts,
  and how they are encoded.
- `CPU87` on a machine without a floating-point unit: QEMU always has
  one, so no case shows it undefined.
- `{$O name}` while `TPC` looks for a run-time error (its `/F` option),
  which needs a unit compiled beforehand.
- The exact value of real literals (see [real values](#real-values)).
