# Lexer

How `TPC.EXE` (Borland Pascal 7.01, real-mode command-line compiler) splits a
source file into tokens. Every rule ends with links to the cases in
[`lexer/cases/`](lexer/cases) that show it, and every case is linked from
some rule; `bazel test //spec:cases_test` checks both. A link whose text
holds a `*` stands for all the cases in its folder that match it. A case's
`tpc:` and `output:` lines are recorded from the real compiler and are the
final word; where this text and a case disagree, the case is right and this
text needs fixing.

Every case's `tokens:` line matches the token stream captured from `TPC`.
Between them, the cases take both sides of every branch in `TPC`'s scanner
that a single source file can reach, except as noted under
[not covered yet](#not-covered-yet). A case's token list ends where `TPC`
stops asking for tokens: at the end of the program, or at the token where
it reports an error. When the error is in the lexer itself, the bad token
is not delivered.

## Notation

Tokens in cases are written as names, some with a value in parentheses:

| Token | Meaning |
| --- | --- |
| `AND`, `ARRAY`, … `XOR` | a [reserved word](#reserved-words), named by the word in upper case |
| `IDENT(NAME)` | an [identifier](#identifiers); the value is its first 63 characters in upper case |
| `INTEGER(n)` | an [integer number](#numbers); the value is a signed 32-bit decimal |
| `REAL(text)` | a [real number](#numbers), as written |
| `STRING(s)` | a [character string](#character-strings), in the string notation below |
| `PLUS` `MINUS` `STAR` `SLASH` | `+` `-` `*` `/` |
| `EQ` `NE` `LT` `LE` `GT` `GE` | `=` `<>` `<` `<=` `>` `>=` |
| `LPAREN` `RPAREN` | `(` `)` |
| `LBRACKET` `RBRACKET` | `[` or `(.`, and `]` or `.)` |
| `DOT` `DOTDOT` `COMMA` `COLON` `SEMI` | `.` `..` `,` `:` `;` |
| `ASSIGN` | `:=` |
| `CARET` `AT` | `^` `@` |

**String notation**, used in `STRING(...)` and in `output:` lines: runs of
printable characters (32 to 126) in apostrophes, with an apostrophe doubled,
and every other character as `#n` with its decimal code. `''` is the empty
string. For example `'Line 1'#13#10`.

## Source text

- A file is a sequence of bytes. Line feed (10) ends a line, alone or after
  a carriage return. Carriage return (13) does not: a file with CR alone is
  one long line ([lf-ends-a-line](lexer/cases/01-separators/lf-ends-a-line.case), [crlf-ends-a-line](lexer/cases/01-separators/crlf-ends-a-line.case), [cr-does-not-end-a-line](lexer/cases/01-separators/cr-does-not-end-a-line.case)).
- A line may hold at most 127 characters, not counting CRs. A tab counts as
  one character ([line-127](lexer/cases/11-program-lines/line-127.case), [line-127-crlf](lexer/cases/11-program-lines/line-127-crlf.case), [line-127-two-crs](lexer/cases/11-program-lines/line-127-two-crs.case), [line-127-with-cr-inside](lexer/cases/11-program-lines/line-127-with-cr-inside.case), [line-127-tab](lexer/cases/11-program-lines/line-127-tab.case)).
- A longer line is error 11 at column 128, before any token on that line is
  delivered ([line-128](lexer/cases/11-program-lines/line-128.case), [line-128-tab](lexer/cases/11-program-lines/line-128-tab.case), [line-128-with-cr-inside](lexer/cases/11-program-lines/line-128-with-cr-inside.case)). This
  happens wherever the line is: inside a comment, an unterminated string or
  text skipped by `{$IFDEF}` too
  ([line-128-in-comment-before-end](lexer/cases/11-program-lines/line-128-in-comment-before-end.case), [line-128-in-string](lexer/cases/11-program-lines/line-128-in-string.case), [line-128-in-skipped-text](lexer/cases/11-program-lines/line-128-in-skipped-text.case)).
- NUL (0) bytes are dropped as a line is read, as if they weren't in the
  file: `pro`, NUL, `gram` is `program`, a NUL between two digits or inside
  a quoted string disappears, and NULs don't count toward the line length
  ([nul-in-word](lexer/cases/02-character-set/nul-in-word.case), [nul-in-number](lexer/cases/02-character-set/nul-in-number.case), [nul-in-string](lexer/cases/02-character-set/nul-in-string.case), [nul-not-counted](lexer/cases/02-character-set/nul-not-counted.case), [nul-after-semicolon](lexer/cases/02-character-set/nul-after-semicolon.case)).
- Nothing changes where a token crosses a 4096-byte boundary of the file
  ([string-across-4096](lexer/cases/11-program-lines/string-across-4096.case)).
- ^Z (26) ends the file; nothing after it is read
  ([ctrl-z-ends-file](lexer/cases/12-end-of-file/ctrl-z-ends-file.case)). When the file ends too early, the error is
  reported at column 1 of the line after the last line read, and a line
  that ^Z cuts short still counts as read
  ([ctrl-z-early](lexer/cases/12-end-of-file/ctrl-z-early.case), [ctrl-z-early-more-lines](lexer/cases/12-end-of-file/ctrl-z-early-more-lines.case), [ctrl-z-line-3](lexer/cases/12-end-of-file/ctrl-z-line-3.case), [missing-final-dot](lexer/cases/12-end-of-file/missing-final-dot.case)).
  The last line needs no line end ([no-final-newline](lexer/cases/12-end-of-file/no-final-newline.case)).
- Scanning stops after the program's final `end.`. Anything after it is
  never read ([after-final-end](lexer/cases/12-end-of-file/after-final-end.case)).

## Separators

- Characters 1 to 32 are blanks (0 never gets this far, see
  [source text](#source-text)). Blanks and comments separate tokens and are
  otherwise ignored ([control-characters-are-blanks](lexer/cases/01-separators/control-characters-are-blanks.case), [comment-is-a-separator](lexer/cases/01-separators/comment-is-a-separator.case)).
- A separator is needed only between two tokens that would otherwise run
  together: two words (reserved words or identifiers) or a word and a
  number. `programP` is a single identifier
  ([words-joined](lexer/cases/01-separators/words-joined.case), [no-separator-next-to-symbols](lexer/cases/01-separators/no-separator-next-to-symbols.case)).
- A blank inside a two-character symbol splits it: `: =` is `:` then `=`
  ([assign-split](lexer/cases/03-special-symbols/assign-split.case), [dotdot-split](lexer/cases/03-special-symbols/dotdot-split.case), [le-split](lexer/cases/03-special-symbols/le-split.case), [ne-split](lexer/cases/03-special-symbols/ne-split.case), [ge-split](lexer/cases/03-special-symbols/ge-split.case), [lbracket-digraph-split](lexer/cases/03-special-symbols/lbracket-digraph-split.case), [rbracket-digraph-split](lexer/cases/03-special-symbols/rbracket-digraph-split.case)).

## Character set

- Reserved words and identifiers are made of the letters A–Z and a–z, the
  digits 0–9 and the underscore. Case doesn't matter
  ([upper-case-words](lexer/cases/02-character-set/upper-case-words.case), [mixed-case-words](lexer/cases/02-character-set/mixed-case-words.case)).
- The printable characters ``! " % & ? \ ` | ~``, DEL (127) and the
  characters 128 to 255 are allowed only inside strings and comments
  ([high-characters-in-string](lexer/cases/02-character-set/high-characters-in-string.case), [del-in-string](lexer/cases/02-character-set/del-in-string.case), [not-a-symbol-in-comment](lexer/cases/02-character-set/not-a-symbol-in-comment.case)).
  Elsewhere each is error 5, and no token is delivered for it
  ([not-a-symbol-exclamation](lexer/cases/02-character-set/not-a-symbol-exclamation.case), [not-a-symbol-double-quote](lexer/cases/02-character-set/not-a-symbol-double-quote.case), [not-a-symbol-percent](lexer/cases/02-character-set/not-a-symbol-percent.case), [not-a-symbol-ampersand](lexer/cases/02-character-set/not-a-symbol-ampersand.case), [not-a-symbol-question-mark](lexer/cases/02-character-set/not-a-symbol-question-mark.case), [not-a-symbol-backslash](lexer/cases/02-character-set/not-a-symbol-backslash.case), [not-a-symbol-backquote](lexer/cases/02-character-set/not-a-symbol-backquote.case), [not-a-symbol-vertical-bar](lexer/cases/02-character-set/not-a-symbol-vertical-bar.case), [not-a-symbol-tilde](lexer/cases/02-character-set/not-a-symbol-tilde.case), [not-a-symbol-del](lexer/cases/02-character-set/not-a-symbol-del.case), [high-character-outside-string](lexer/cases/02-character-set/high-character-outside-string.case)).

## Special symbols

Single characters `+ - * / = < > [ ] . , ( ) : ; ^ @` and pairs
`<= >= <> := .. (. .)`
([arithmetic](lexer/cases/03-special-symbols/arithmetic.case), [relational](lexer/cases/03-special-symbols/relational.case), [brackets](lexer/cases/03-special-symbols/brackets.case), [caret-and-at](lexer/cases/03-special-symbols/caret-and-at.case)). `(.` and `.)` mean
the same as `[` and `]` ([bracket-digraphs](lexer/cases/03-special-symbols/bracket-digraphs.case)). `{ } (* *)` delimit
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
  ([digits-after-first](lexer/cases/05-identifiers/digits-after-first.case), [underscore-first](lexer/cases/05-identifiers/underscore-first.case), [underscore-only](lexer/cases/05-identifiers/underscore-only.case), [digit-first](lexer/cases/05-identifiers/digit-first.case)).
- Case doesn't matter, and only the first 63 characters are significant:
  identifiers that agree in their first 63 characters are the same
  identifier ([case-insensitive](lexer/cases/05-identifiers/case-insensitive.case), [63-significant-same](lexer/cases/05-identifiers/63-significant-same.case), [63-significant-differ](lexer/cases/05-identifiers/63-significant-differ.case)).
- A qualified identifier such as `System.WriteLn` is three tokens
  ([qualified](lexer/cases/05-identifiers/qualified.case)).

## Numbers

- **Decimal integers** are digit sequences with values from 0 to
  2147483647 ([decimal](lexer/cases/06-numbers/decimal.case), [decimal-max](lexer/cases/06-numbers/decimal-max.case)). Leading zeros don't matter
  ([leading-zeros](lexer/cases/06-numbers/leading-zeros.case), [decimal-many-leading-zeros](lexer/cases/06-numbers/decimal-many-leading-zeros.case)). A larger value is
  error 7, at the digit where the value first goes over: in a run of twenty
  `1`s, that's the 11th ([decimal-over](lexer/cases/06-numbers/decimal-over.case), [decimal-overflow-position](lexer/cases/06-numbers/decimal-overflow-position.case)). A
  minus sign is a separate token, so `-2147483648` is an error
  ([decimal-min](lexer/cases/06-numbers/decimal-min.case)).
- **Hex integers** are `$` and one or more hex digits, either case, with a
  value up to `$FFFFFFFF`, and error 7 likewise at the digit that goes over
  ([hex](lexer/cases/06-numbers/hex.case), [hex-lower](lexer/cases/06-numbers/hex-lower.case), [hex-over](lexer/cases/06-numbers/hex-over.case), [hex-overflow-position](lexer/cases/06-numbers/hex-overflow-position.case)). Leading zeros
  don't count ([hex-leading-zeros](lexer/cases/06-numbers/hex-leading-zeros.case)). The value is a 32-bit pattern read
  as signed: `$FFFFFFFF` is -1 and `$80000000` is -2147483648
  ([hex-max](lexer/cases/06-numbers/hex-max.case), [hex-sign-bit](lexer/cases/06-numbers/hex-sign-bit.case)). `$` without a hex digit right after it is
  error 7 ([dollar-alone](lexer/cases/06-numbers/dollar-alone.case), [dollar-space](lexer/cases/06-numbers/dollar-space.case)).
- **Reals** are digits, then a fraction (`.` and digits), an exponent
  (`E` or `e`, an optional sign and digits), or both
  ([real-fraction](lexer/cases/06-numbers/real-fraction.case), [real-exponent](lexer/cases/06-numbers/real-exponent.case), [real-exponent-negative](lexer/cases/06-numbers/real-exponent-negative.case), [real-exponent-upper-signed](lexer/cases/06-numbers/real-exponent-upper-signed.case), [real-many-fraction-digits](lexer/cases/06-numbers/real-many-fraction-digits.case), [real-many-integer-digits](lexer/cases/06-numbers/real-many-integer-digits.case)).
  The digits after `.` and after `E` may be missing: `1.`, `1.e5`, `1e`,
  `1e+` and `1e-` are all accepted, and a missing exponent counts as 0
  ([real-no-fraction-digits](lexer/cases/06-numbers/real-no-fraction-digits.case), [real-dot-exponent](lexer/cases/06-numbers/real-dot-exponent.case), [real-exponent-no-digits](lexer/cases/06-numbers/real-exponent-no-digits.case), [real-exponent-plus-no-digits](lexer/cases/06-numbers/real-exponent-plus-no-digits.case), [real-exponent-minus-no-digits](lexer/cases/06-numbers/real-exponent-minus-no-digits.case)).
  The exponent's digits are read only while its value stays at most 9999,
  and the next digit starts a new token: `1e12345` is `REAL(1e1234)` then
  `INTEGER(5)`
  ([real-exponent-4-digits](lexer/cases/06-numbers/real-exponent-4-digits.case), [real-exponent-1000](lexer/cases/06-numbers/real-exponent-1000.case), [real-exponent-9999](lexer/cases/06-numbers/real-exponent-9999.case), [real-exponent-10000](lexer/cases/06-numbers/real-exponent-10000.case), [real-exponent-5-digits](lexer/cases/06-numbers/real-exponent-5-digits.case), [real-exponent-5-digits-small](lexer/cases/06-numbers/real-exponent-5-digits-small.case)).
  Leading zeros in the exponent don't count
  ([real-exponent-leading-zeros-9999](lexer/cases/06-numbers/real-exponent-leading-zeros-9999.case)). A number can't start with `.`
  ([real-no-integer-digits](lexer/cases/06-numbers/real-no-integer-digits.case)). A value beyond the Extended range is
  error 6, just after the number ([real-overflow](lexer/cases/06-numbers/real-overflow.case)); a value that fits
  Extended is a valid token even where it doesn't fit the type it is used
  as ([real-huge](lexer/cases/06-numbers/real-huge.case)).
- `1..2` is `1`, `..`, `2`, and `1.)` is `1`, `.)`: a `.` directly
  followed by another `.` or by `)` doesn't make a real
  ([integer-then-dotdot](lexer/cases/06-numbers/integer-then-dotdot.case)) ([bracket-digraphs](lexer/cases/03-special-symbols/bracket-digraphs.case)). `1. )` is
  `REAL(1.)` and `)` ([real-dot-then-blank-paren](lexer/cases/06-numbers/real-dot-then-blank-paren.case)).

## Labels

A label is an identifier or a number from 0 to 9999; leading zeros don't
matter, so `01` and `1` are the same label
([label-identifier](lexer/cases/07-labels/label-identifier.case), [label-max](lexer/cases/07-labels/label-max.case), [label-leading-zeros](lexer/cases/07-labels/label-leading-zeros.case)). To the lexer a
numeric label is an ordinary `INTEGER`: `10000` is delivered as a number and
then rejected where a label is expected ([label-over](lexer/cases/07-labels/label-over.case)).

## Character strings

A string is a run of parts with no separators between them
([mixed](lexer/cases/08-strings/mixed.case), [mixed-around](lexer/cases/08-strings/mixed-around.case), [caret-mixed](lexer/cases/08-strings/caret-mixed.case), [caret-pair-in-write](lexer/cases/08-strings/caret-pair-in-write.case)). A blank
between parts ends the string, and the next part starts a new one
([separator-between-parts](lexer/cases/08-strings/separator-between-parts.case)). The parts are:

- **Quoted strings**: characters between apostrophes on one line, with two
  apostrophes standing for one
  ([quoted](lexer/cases/08-strings/quoted.case), [empty](lexer/cases/08-strings/empty.case), [blank](lexer/cases/08-strings/blank.case), [doubled-apostrophe](lexer/cases/08-strings/doubled-apostrophe.case), [long-string](lexer/cases/08-strings/long-string.case)) ([brace-in-string](lexer/cases/09-comments/brace-in-string.case)).
  A line end before the closing apostrophe is error 8 ([unterminated](lexer/cases/08-strings/unterminated.case)).
- **`#` and a number**, decimal or hex, with no blank after `#`
  ([control-characters](lexer/cases/08-strings/control-characters.case), [hash-hex](lexer/cases/08-strings/hash-hex.case), [hash-space](lexer/cases/08-strings/hash-space.case)). The number is read like
  any integer, with the same limits and error 7 when it overflows
  ([hash-overflow](lexer/cases/08-strings/hash-overflow.case)). Then only its low 8 bits are used: `#256` is `#0`,
  `#65601` is `'A'` and `#2147483647` is `#255`
  ([hash-255](lexer/cases/08-strings/hash-255.case), [hash-256](lexer/cases/08-strings/hash-256.case), [hash-large](lexer/cases/08-strings/hash-large.case), [hash-max-integer](lexer/cases/08-strings/hash-max-integer.case)).
- **`^` and the very next character**, whatever it is, a blank included:
  the character with bit 64 flipped, after changing `a` to `z` to upper
  case. `^M` and `^m` are `#13`, `^@` is `#0`, `^[` is `#27`, `^1` is
  `'q'`, `^'` is `'g'`, and `^` then a space is `` ` `` (96)
  ([caret-letter](lexer/cases/08-strings/caret-letter.case), [caret-lower](lexer/cases/08-strings/caret-lower.case), [caret-at](lexer/cases/08-strings/caret-at.case), [caret-bracket](lexer/cases/08-strings/caret-bracket.case), [caret-digit](lexer/cases/08-strings/caret-digit.case), [caret-quote](lexer/cases/08-strings/caret-quote.case), [caret-space](lexer/cases/08-strings/caret-space.case)).
  Only `a` to `z` change case: `` ^` `` is `' '`, `^z` is `#26`, `^{` is
  `';'`, `^~` is `'>'`, `^` then DEL (127) is `'?'` and `^` then character
  233 is `#169`
  ([caret-backquote](lexer/cases/08-strings/caret-backquote.case), [caret-z](lexer/cases/08-strings/caret-z.case), [caret-brace](lexer/cases/08-strings/caret-brace.case), [caret-tilde](lexer/cases/08-strings/caret-tilde.case), [caret-del](lexer/cases/08-strings/caret-del.case), [caret-high](lexer/cases/08-strings/caret-high.case)).
  Only one character is taken: `^Integer` is `^I` followed by the
  identifier `nteger` ([caret-word](lexer/cases/08-strings/caret-word.case)). Where an operand is expected but
  `^` is the last character on its line, `TPC` delivers `CARET` and then
  reports error 8 just after it, as for an unterminated string
  ([caret-end-of-line](lexer/cases/08-strings/caret-end-of-line.case)).

Any number of strings, however long, may appear in one statement
([many-long-strings](lexer/cases/08-strings/many-long-strings.case)).

Whether `^` starts a string depends on where it appears. Where an operand
of an expression is expected, `^` and the next character are a character
string as above, and join with neighbouring parts: in constant expressions,
statements, set constructors and `case` labels
([caret-in-const-expression](lexer/cases/08-strings/caret-in-const-expression.case), [caret-in-expression](lexer/cases/08-strings/caret-in-expression.case), [caret-in-comparison](lexer/cases/08-strings/caret-in-comparison.case), [caret-in-write](lexer/cases/08-strings/caret-in-write.case), [caret-in-set](lexer/cases/08-strings/caret-in-set.case), [caret-case-label](lexer/cases/08-strings/caret-case-label.case)).
Everywhere else `^` is `CARET`:

- wherever a type is expected: after `=` in a type declaration, after `:`
  in a variable, record field or typed constant declaration, and after `of`
  in an array type
  ([caret-type-pointer](lexer/cases/08-strings/caret-type-pointer.case), [caret-var-pointer](lexer/cases/08-strings/caret-var-pointer.case), [caret-record-field](lexer/cases/08-strings/caret-record-field.case), [caret-typed-constant](lexer/cases/08-strings/caret-typed-constant.case), [caret-array-of](lexer/cases/08-strings/caret-array-of.case)).
  There `^M` is always a pointer to type `M`, so a subrange of characters
  can't be written with `^`: `type T = ^A..^Z` is an error
  ([caret-char-subrange](lexer/cases/08-strings/caret-char-subrange.case), [caret-var-subrange](lexer/cases/08-strings/caret-var-subrange.case)). `^1` there is
  `CARET INTEGER(1)` ([caret-type-digit](lexer/cases/08-strings/caret-type-digit.case)).
- after an operand, where it dereferences a pointer: `Q^.F`, `(Q)^`
  ([caret-after-identifier](lexer/cases/08-strings/caret-after-identifier.case), [caret-after-paren](lexer/cases/08-strings/caret-after-paren.case)).

## Comments

- `{` to the next `}`, or `(*` to the next `*)` ([braces](lexer/cases/09-comments/braces.case), [paren-star](lexer/cases/09-comments/paren-star.case)).
  Comments of both kinds may span lines
  ([multi-line](lexer/cases/09-comments/multi-line.case), [paren-star-multi-line](lexer/cases/09-comments/paren-star-multi-line.case)). A `*` at the end of one line
  and a `)` at the start of the next don't end a `(*` comment
  ([paren-star-split-close](lexer/cases/09-comments/paren-star-split-close.case)).
- They don't nest, and the other kind of delimiter has no effect inside
  one: `{ (* }` is a complete comment
  ([braces-dont-nest](lexer/cases/09-comments/braces-dont-nest.case), [paren-star-dont-nest](lexer/cases/09-comments/paren-star-dont-nest.case), [paren-star-inside-braces](lexer/cases/09-comments/paren-star-inside-braces.case), [brace-inside-paren-star](lexer/cases/09-comments/brace-inside-paren-star.case)).
- `(*)` opens a comment; the `)` is part of it
  ([paren-star-close-paren](lexer/cases/09-comments/paren-star-close-paren.case)).
- A `}` outside a comment is a syntax error ([stray-close-brace](lexer/cases/09-comments/stray-close-brace.case)). A
  `*)` outside a comment is simply `*` followed by `)`
  ([paren-star-dont-nest](lexer/cases/09-comments/paren-star-dont-nest.case)). A comment still open at the end of the file
  is error 10 ([unterminated-brace](lexer/cases/09-comments/unterminated-brace.case), [unterminated-paren-star](lexer/cases/09-comments/unterminated-paren-star.case)).

## Compiler directives

A comment whose first character is `$` is a compiler directive
([brace-directive](lexer/cases/10-compiler-directives/brace-directive.case), [paren-star-directive](lexer/cases/10-compiler-directives/paren-star-directive.case)). Directives are not tokens.
Their names aren't case sensitive ([lower-case-directive](lexer/cases/10-compiler-directives/lower-case-directive.case), [switch-lower-sign](lexer/cases/10-compiler-directives/switch-lower-sign.case)).
`{ $R+}` is an ordinary comment ([blank-before-dollar](lexer/cases/10-compiler-directives/blank-before-dollar.case)).

A directive is checked as soon as `{$` or `(*$` is read, before the end of
the comment is looked for, so a bad directive is error 17 even in a comment
that never ends
([invalid-directive-unterminated](lexer/cases/10-compiler-directives/invalid-directive-unterminated.case), [unterminated-directive](lexer/cases/10-compiler-directives/unterminated-directive.case)). Its name is
the run of letters and digits after the `$`, so `{$M16384}` has the unknown
name `M16384` ([m-no-blank-number](lexer/cases/10-compiler-directives/m-no-blank-number.case), [long-unknown-name](lexer/cases/10-compiler-directives/long-unknown-name.case)). The name is one
of:

- a conditional directive name (`DEFINE`, `UNDEF`, `IFDEF`, `IFNDEF`,
  `IFOPT`, `ELSE`, `ENDIF`), see below;
- a list of switches, each a switch letter and `+` or `-`, separated by
  commas with no blanks: `{$R+,X-}` ([switch-list](lexer/cases/10-compiler-directives/switch-list.case)). A blank after a
  comma is error 17 ([switch-list-blank-after-comma](lexer/cases/10-compiler-directives/switch-list-blank-after-comma.case)). Anything after
  the last sign that isn't a comma is ignored, a blank or not: `{$R+ text}`
  is accepted, and `{$R-B+}` turns R off and leaves B alone
  ([switch-trailing-text](lexer/cases/10-compiler-directives/switch-trailing-text.case), [switch-text-after-sign](lexer/cases/10-compiler-directives/switch-text-after-sign.case));
- a parameter directive letter (`C D G I L M O R S`) and its parameter.
  For `C`, `D`, `G`, `R` and `S`, everything after the letter up to the
  end of the comment is ignored, whatever it is and nothing at all
  included: `{$R}`, `{$R }` and `{$R=X}` are accepted
  ([parameter-c-text](lexer/cases/10-compiler-directives/parameter-c-text.case), [parameter-c-empty](lexer/cases/10-compiler-directives/parameter-c-empty.case), [parameter-d-text](lexer/cases/10-compiler-directives/parameter-d-text.case), [parameter-d-empty](lexer/cases/10-compiler-directives/parameter-d-empty.case), [parameter-g-text](lexer/cases/10-compiler-directives/parameter-g-text.case), [parameter-g-empty](lexer/cases/10-compiler-directives/parameter-g-empty.case), [parameter-s-text](lexer/cases/10-compiler-directives/parameter-s-text.case), [parameter-s-empty](lexer/cases/10-compiler-directives/parameter-s-empty.case), [switch-without-sign](lexer/cases/10-compiler-directives/switch-without-sign.case), [switch-r-blank](lexer/cases/10-compiler-directives/switch-r-blank.case), [r-equals](lexer/cases/10-compiler-directives/r-equals.case)).
  `I` and `L` take a file name, even right after the letter; a missing
  file is error 15, but that's not the lexer's business
  ([include-missing-file](lexer/cases/10-compiler-directives/include-missing-file.case), [i-colon](lexer/cases/10-compiler-directives/i-colon.case), [l-colon](lexer/cases/10-compiler-directives/l-colon.case)). `O` takes a unit name.
  `M` takes numbers, see [memory sizes](#memory-sizes)
  ([parameter-with-blank](lexer/cases/10-compiler-directives/parameter-with-blank.case)).

Anything else is error 17, at the column of the offending item: a blank
right after `$` ([dollar-blank](lexer/cases/10-compiler-directives/dollar-blank.case)), an unknown name such as `{$FOO}` or
`{$Z+}` ([unknown-directive](lexer/cases/10-compiler-directives/unknown-directive.case)), a switch list with a bad item
([switch-list-bad-second](lexer/cases/10-compiler-directives/switch-list-bad-second.case)), a switch letter that isn't also a parameter
directive written without its sign (`{$T}`, `{$T }`)
([switch-t-no-sign](lexer/cases/10-compiler-directives/switch-t-no-sign.case), [switch-b-no-sign](lexer/cases/10-compiler-directives/switch-b-no-sign.case), [switch-t-blank](lexer/cases/10-compiler-directives/switch-t-blank.case)), or a missing item
after a comma (`{$R+,}`) ([switch-trailing-comma](lexer/cases/10-compiler-directives/switch-trailing-comma.case)).

### Switches that must come first

The switches `A D E G K L N O T X Y` may appear only before the program
heading or right after it ([switch-n-before-header](lexer/cases/10-compiler-directives/switch-n-before-header.case), [switch-n-after-header](lexer/cases/10-compiler-directives/switch-n-after-header.case)).
After a `uses` clause or a declaration, or inside a statement part, any of
them is error 17 at the switch letter
([switch-*-after-declaration](lexer/cases/10-compiler-directives/), [switch-n-after-uses](lexer/cases/10-compiler-directives/switch-n-after-uses.case), [switch-n-in-statement](lexer/cases/10-compiler-directives/switch-n-in-statement.case)).
The other switches (`B F I P Q R S V W`) and `{$M}` may appear anywhere
([switches-local-after-declaration](lexer/cases/10-compiler-directives/switches-local-after-declaration.case), [m-after-declaration](lexer/cases/10-compiler-directives/m-after-declaration.case), [m-in-statement](lexer/cases/10-compiler-directives/m-in-statement.case)).

### Memory sizes

`{$M stack,heapmin,heapmax}` takes three numbers, decimal or hex
([m-hex](lexer/cases/10-compiler-directives/m-hex.case)). Before each number, any run of blanks, commas and semicolons
is skipped, so `{$M 16384 0 655360}`, `{$M 16384;0;655360}` and
`{$M ,16384,,0, ,655360}` are all accepted
([m-blanks](lexer/cases/10-compiler-directives/m-blanks.case), [m-semicolons](lexer/cases/10-compiler-directives/m-semicolons.case), [m-extra-commas](lexer/cases/10-compiler-directives/m-extra-commas.case)). Anything after the third
number is ignored ([m-trailing-text](lexer/cases/10-compiler-directives/m-trailing-text.case)). A number that is missing or out
of range is error 17 at the place where it starts or should start, so
`{$M}`, `{$M ABC}`, `{$M=16384}`, `{$M 16384}` and `{$M 16384,0}` are all
errors
([m-empty](lexer/cases/10-compiler-directives/m-empty.case), [m-letters](lexer/cases/10-compiler-directives/m-letters.case), [parameter-without-blank](lexer/cases/10-compiler-directives/parameter-without-blank.case), [m-one-number](lexer/cases/10-compiler-directives/m-one-number.case), [m-two-numbers](lexer/cases/10-compiler-directives/m-two-numbers.case)).

- `stack` is rounded down to an even number and must then be from 1024 to
  65520: 1023 and 65522 are errors, 1025 is used as 1024 and 65521 as
  65520
  ([m-stack-1023](lexer/cases/10-compiler-directives/m-stack-1023.case), [m-stack-1024](lexer/cases/10-compiler-directives/m-stack-1024.case), [m-stack-1025](lexer/cases/10-compiler-directives/m-stack-1025.case), [m-stack-65520](lexer/cases/10-compiler-directives/m-stack-65520.case), [m-stack-65521](lexer/cases/10-compiler-directives/m-stack-65521.case), [m-stack-65522](lexer/cases/10-compiler-directives/m-stack-65522.case), [m-stack-65536](lexer/cases/10-compiler-directives/m-stack-65536.case)).
- `heapmin` and `heapmax` are rounded up to a whole number of 16-byte
  paragraphs ([m-heap-max-16](lexer/cases/10-compiler-directives/m-heap-max-16.case), [m-heap-max-17](lexer/cases/10-compiler-directives/m-heap-max-17.case)) and may be at most
  655360 ([m-heap-max-655360](lexer/cases/10-compiler-directives/m-heap-max-655360.case), [m-heap-max-655361](lexer/cases/10-compiler-directives/m-heap-max-655361.case), [m-heap-min-655361](lexer/cases/10-compiler-directives/m-heap-min-655361.case), [m-heap-max-1048576](lexer/cases/10-compiler-directives/m-heap-max-1048576.case), [m-heap-max-hex-huge](lexer/cases/10-compiler-directives/m-heap-max-hex-huge.case)).
  After rounding, `heapmax` may not be below `heapmin`:
  `{$M 16384,1024,1009}` is accepted, as both are 64 paragraphs, and
  `{$M 16384,1024,1008}` is an error
  ([m-heap-min-equals-max-rounded](lexer/cases/10-compiler-directives/m-heap-min-equals-max-rounded.case), [m-heap-min-above-max](lexer/cases/10-compiler-directives/m-heap-min-above-max.case)). A number too
  large for an integer is an error too
  ([m-heap-max-not-integer](lexer/cases/10-compiler-directives/m-heap-max-not-integer.case), [m-heap-min-not-integer](lexer/cases/10-compiler-directives/m-heap-min-not-integer.case)).

### Conditional symbols

`{$DEFINE name}` defines a conditional symbol and `{$UNDEF name}` removes
it ([ifdef-defined](lexer/cases/10-compiler-directives/ifdef-defined.case), [undef](lexer/cases/10-compiler-directives/undef.case), [undef-middle](lexer/cases/10-compiler-directives/undef-middle.case)). Defining a symbol that is
already defined, or removing one that isn't, does nothing: after defining
`X` twice and removing it once, `X` is undefined
([define-twice](lexer/cases/10-compiler-directives/define-twice.case), [undef-not-defined](lexer/cases/10-compiler-directives/undef-not-defined.case)).

A symbol's name is read like an identifier: a letter or underscore, then
letters, digits and underscores, with case not mattering and only the first
63 characters significant
([define-underscore](lexer/cases/10-compiler-directives/define-underscore.case), [define-case-insensitive](lexer/cases/10-compiler-directives/define-case-insensitive.case), [define-63-differ](lexer/cases/10-compiler-directives/define-63-differ.case), [define-64-same](lexer/cases/10-compiler-directives/define-64-same.case)).
It ends at the first other character, so `{$DEFINE A$}` defines `A`, and it
may be a reserved word
([define-name-ends-at-other-character](lexer/cases/10-compiler-directives/define-name-ends-at-other-character.case), [define-symbol-is-word](lexer/cases/10-compiler-directives/define-symbol-is-word.case)). A missing
name, or one starting with a digit, is error 2 where the name should start.
This goes for `{$UNDEF}`, `{$IFDEF}` and `{$IFNDEF}` too
([define-no-name](lexer/cases/10-compiler-directives/define-no-name.case), [define-digit-first](lexer/cases/10-compiler-directives/define-digit-first.case), [undef-no-name](lexer/cases/10-compiler-directives/undef-no-name.case), [ifdef-no-name](lexer/cases/10-compiler-directives/ifdef-no-name.case), [ifndef-no-name](lexer/cases/10-compiler-directives/ifndef-no-name.case)).

`VER70`, `MSDOS`, `CPU86` and `CPU87` are defined from the start;
`VER60`, `DPMI` and `WINDOWS` are not
([predefined-symbols](lexer/cases/10-compiler-directives/predefined-symbols.case), [not-predefined-symbols](lexer/cases/10-compiler-directives/not-predefined-symbols.case)). The reference machine has
a floating-point unit; whether `CPU87` depends on one is untested. The
defined symbols, these four included, share 1024 bytes, each taking its
length plus one. A `{$DEFINE}` that doesn't fit is error 127 at its name.
Removing a symbol, even a predefined one, makes room again
([symbols-full](lexer/cases/10-compiler-directives/symbols-full.case), [symbols-over](lexer/cases/10-compiler-directives/symbols-over.case), [symbols-undef-frees](lexer/cases/10-compiler-directives/symbols-undef-frees.case), [symbols-undef-frees-over](lexer/cases/10-compiler-directives/symbols-undef-frees-over.case)).

### Conditional compilation

The conditional directives work at this level: skipped text produces no
tokens ([ifdef-skips](lexer/cases/10-compiler-directives/ifdef-skips.case)).

- `{$IFDEF name}` compiles the text up to its `{$ELSE}` or `{$ENDIF}` if
  `name` is defined, and skips it otherwise. `{$IFNDEF name}` does the
  opposite
  ([ifdef-defined](lexer/cases/10-compiler-directives/ifdef-defined.case), [else-defined](lexer/cases/10-compiler-directives/else-defined.case), [else-undefined](lexer/cases/10-compiler-directives/else-undefined.case), [ifndef-defined](lexer/cases/10-compiler-directives/ifndef-defined.case), [ifndef-undefined](lexer/cases/10-compiler-directives/ifndef-undefined.case)).
- `{$IFOPT X+}` and `{$IFOPT X-}` test whether switch `X` is on or off
  ([ifopt-r-plus](lexer/cases/10-compiler-directives/ifopt-r-plus.case), [ifopt-r-minus](lexer/cases/10-compiler-directives/ifopt-r-minus.case), [ifopt-after-switch](lexer/cases/10-compiler-directives/ifopt-after-switch.case), [ifopt-i](lexer/cases/10-compiler-directives/ifopt-i.case), [ifopt-lower-case](lexer/cases/10-compiler-directives/ifopt-lower-case.case)).
  After any blanks comes a switch letter and its sign; anything after that
  is ignored ([ifopt-blanks](lexer/cases/10-compiler-directives/ifopt-blanks.case), [ifopt-trailing-text](lexer/cases/10-compiler-directives/ifopt-trailing-text.case)). A letter that isn't
  a switch (`Z`), one that is only a parameter directive (`M`), or a
  missing sign is error 17 at the letter
  ([ifopt-unknown-switch](lexer/cases/10-compiler-directives/ifopt-unknown-switch.case), [ifopt-parameter-directive](lexer/cases/10-compiler-directives/ifopt-parameter-directive.case), [ifopt-no-sign](lexer/cases/10-compiler-directives/ifopt-no-sign.case)).
- `{$ELSE}` switches from compiling to skipping or back. A second `{$ELSE}`
  at the same level switches again: in `{$IFDEF X} a {$ELSE} b {$ELSE} c
  {$ENDIF}`, `a` and `c` are compiled when `X` is defined, and only `b`
  when it isn't ([else-twice-defined](lexer/cases/10-compiler-directives/else-twice-defined.case), [else-twice-undefined](lexer/cases/10-compiler-directives/else-twice-undefined.case)).
- Conditionals nest, in compiled and in skipped text alike
  ([nested-compiled](lexer/cases/10-compiler-directives/nested-compiled.case), [nested-ifdef-skipped](lexer/cases/10-compiler-directives/nested-ifdef-skipped.case), [nested-ifndef-skipped](lexer/cases/10-compiler-directives/nested-ifndef-skipped.case), [nested-ifopt-skipped](lexer/cases/10-compiler-directives/nested-ifopt-skipped.case), [nested-else-skipped](lexer/cases/10-compiler-directives/nested-else-skipped.case)).
  In skipped text, only the conditional directives count: `{$IFDEF}`,
  `{$IFNDEF}` and `{$IFOPT}` open a level, `{$ENDIF}` closes one, and an
  `{$ELSE}` or `{$ENDIF}` at the outermost level ends the skipping. All
  other directives there are ignored, even unknown ones, and so is anything
  after a directive's name: `{$ENDIF junk}` ends skipped text but
  `{$ENDIFX}` doesn't
  ([skipped-unknown-directive](lexer/cases/10-compiler-directives/skipped-unknown-directive.case), [skipped-define](lexer/cases/10-compiler-directives/skipped-define.case), [skipped-endif-with-text](lexer/cases/10-compiler-directives/skipped-endif-with-text.case), [skipped-endif-longer-name](lexer/cases/10-compiler-directives/skipped-endif-longer-name.case)).
- `{$ELSE}` or `{$ENDIF}` with no conditional open is error 128 at its
  name ([else-without-ifdef](lexer/cases/10-compiler-directives/else-without-ifdef.case), [endif-without-ifdef](lexer/cases/10-compiler-directives/endif-without-ifdef.case)). A conditional still
  open at the program's final `end.` is error 129 at the `.`
  ([ifdef-open-at-final-end](lexer/cases/10-compiler-directives/ifdef-open-at-final-end.case)).

Skipped text is still read for comments and quoted strings, though: a
`{$ENDIF}` inside a comment or after an apostrophe on the same line doesn't
count ([ifdef-skips-comments](lexer/cases/10-compiler-directives/ifdef-skips-comments.case), [ifdef-skips-strings](lexer/cases/10-compiler-directives/ifdef-skips-strings.case)). A string still open
at the end of a line just ends there ([ifdef-skips](lexer/cases/10-compiler-directives/ifdef-skips.case)). A comment still
open at the end of the file is error 10, and a missing `{$ENDIF}` is error
129, both at the end of the file
([ifdef-unterminated-comment](lexer/cases/10-compiler-directives/ifdef-unterminated-comment.case), [ifdef-unterminated](lexer/cases/10-compiler-directives/ifdef-unterminated.case)).

### Include files

`{$I name}` inside a statement part is error 118, just after the
directive, before `TPC` looks for the file ([include-in-statement](lexer/cases/10-compiler-directives/include-in-statement.case)).

### `)` ending a `(*$` directive

In a directive written with `(*$`, a `)` directly after the directive's
last item ends the comment, as `*)` would, in exactly these cases:

- `(*$M stack,heapmin,heapmax)`, when `heapmax` in paragraphs (rounded up)
  is 42 more than a multiple of 256: 672 bytes (42 paragraphs) and 4768
  bytes (298 paragraphs) end the comment, and 688 bytes (43 paragraphs)
  doesn't
  ([paren-m-close-42](lexer/cases/10-compiler-directives/paren-m-close-42.case), [paren-m-close-298](lexer/cases/10-compiler-directives/paren-m-close-298.case), [paren-m-close-43](lexer/cases/10-compiler-directives/paren-m-close-43.case), [paren-m-close-junk](lexer/cases/10-compiler-directives/paren-m-close-junk.case)).
- `(*$UNDEF name)`, when `name` is defined and 42 characters long
  ([paren-undef-close-42](lexer/cases/10-compiler-directives/paren-undef-close-42.case), [paren-undef-close-41](lexer/cases/10-compiler-directives/paren-undef-close-41.case)).
- `(*$DEFINE name)`, when `name` isn't defined yet and, once it is, the
  defined symbols take up 222 more than a multiple of 256 bytes, counted as
  under [conditional symbols](#conditional-symbols)
  ([paren-define-close](lexer/cases/10-compiler-directives/paren-define-close.case), [paren-define-no-close](lexer/cases/10-compiler-directives/paren-define-no-close.case)).
- `(*$R)` in skipped text. In compiled text, `(*$R)` stays open
  ([paren-r-close-skipped](lexer/cases/10-compiler-directives/paren-r-close-skipped.case), [paren-s-skipped](lexer/cases/10-compiler-directives/paren-s-skipped.case), [paren-r-compiled](lexer/cases/10-compiler-directives/paren-r-compiled.case)).

All other directives stay open past such a `)`: switches and switch lists,
the other parameter directives (`{$L}` included), `{$IFDEF}`, `{$IFNDEF}`,
`{$IFOPT}`, `{$ELSE}`, `{$ENDIF}`, `{$DEFINE}` of a defined symbol and
`{$UNDEF}` of an undefined one
([paren-switch-no-close](lexer/cases/10-compiler-directives/paren-switch-no-close.case), [paren-switch-list-no-close](lexer/cases/10-compiler-directives/paren-switch-list-no-close.case), [paren-parameter-no-close](lexer/cases/10-compiler-directives/paren-parameter-no-close.case), [paren-l-no-close](lexer/cases/10-compiler-directives/paren-l-no-close.case), [paren-ifdef-no-close](lexer/cases/10-compiler-directives/paren-ifdef-no-close.case), [paren-ifndef-no-close](lexer/cases/10-compiler-directives/paren-ifndef-no-close.case), [paren-ifopt-no-close](lexer/cases/10-compiler-directives/paren-ifopt-no-close.case), [paren-else-no-close](lexer/cases/10-compiler-directives/paren-else-no-close.case), [paren-endif-no-close](lexer/cases/10-compiler-directives/paren-endif-no-close.case), [paren-define-defined-no-close](lexer/cases/10-compiler-directives/paren-define-defined-no-close.case), [paren-undef-not-defined-no-close](lexer/cases/10-compiler-directives/paren-undef-not-defined-no-close.case)).
`{$O}` is untested, as it needs units.

## Real values

Each case here prints the exact 80-bit Extended value of a real literal.
`TPC`'s conversion is not correctly rounded, so an implementation has to
reproduce `TPC`'s own arithmetic. That arithmetic isn't known yet
(issue #10). What is known, and checked against every case here by
`bazel test //spec:cases_test`:

- Only the first 19 significant digits count; any digits after them are
  ignored, as if they were 0
  ([digits-*](lexer/cases/13-real-values/), [long-mantissa](lexer/cases/13-real-values/long-mantissa.case), [many-integer-digits](lexer/cases/13-real-values/many-integer-digits.case), [third](lexer/cases/13-real-values/third.case), [leading-zeros](lexer/cases/13-real-values/leading-zeros.case), [trailing-zeros-exponent](lexer/cases/13-real-values/trailing-zeros-exponent.case)).
  Below, N is those digits read as an integer, without trailing zeros, and
  k is the power of ten that scales N to the literal's value.
- A literal whose first 19 digits are `1.189731495357231765e4932` or
  more is error 6, although that is still a little below the largest
  Extended value, `1.18973149535723176502…e4932`. So
  `1.189731495357231764e4932` is the largest accepted literal, and the
  largest Extended value written to 20 digits is an error
  ([largest-accepted](lexer/cases/13-real-values/largest-accepted.case), [largest-accepted-plus-1](lexer/cases/13-real-values/largest-accepted-plus-1.case), [max](lexer/cases/13-real-values/max.case), [limit-1_1897314e4932](lexer/cases/13-real-values/limit-1_1897314e4932.case), [limit-1_189731e4932](lexer/cases/13-real-values/limit-1_189731e4932.case), [limit-1_18973e4932](lexer/cases/13-real-values/limit-1_18973e4932.case), [limit-1_1897e4932](lexer/cases/13-real-values/limit-1_1897e4932.case), [limit-1_189e4932](lexer/cases/13-real-values/limit-1_189e4932.case), [limit-1_18e4932](lexer/cases/13-real-values/limit-1_18e4932.case), [limit-1_1e4932](lexer/cases/13-real-values/limit-1_1e4932.case), [limit-1e4932](lexer/cases/13-real-values/limit-1e4932.case)).
- A literal whose first 19 digits are below the smallest normal Extended
  value (`3.36210314311209350626…e-4932`) becomes 0. There are no
  denormals. So `3.362103143112093507e-4932` is the smallest literal that
  isn't 0, and `3.362103143112093506e-4932` is 0
  ([smallest-nonzero](lexer/cases/13-real-values/smallest-nonzero.case), [smallest-nonzero-minus-1](lexer/cases/13-real-values/smallest-nonzero-minus-1.case), [min-normal](lexer/cases/13-real-values/min-normal.case), [denormal](lexer/cases/13-real-values/denormal.case), [underflow](lexer/cases/13-real-values/underflow.case), [limit-1em4000](lexer/cases/13-real-values/limit-1em4000.case), [limit-1em4400](lexer/cases/13-real-values/limit-1em4400.case), [limit-1em4900](lexer/cases/13-real-values/limit-1em4900.case), [limit-1em4920](lexer/cases/13-real-values/limit-1em4920.case), [limit-1em4930](lexer/cases/13-real-values/limit-1em4930.case), [limit-1em4931](lexer/cases/13-real-values/limit-1em4931.case), [limit-2em4932](lexer/cases/13-real-values/limit-2em4932.case), [limit-3em4932](lexer/cases/13-real-values/limit-3em4932.case), [limit-3_4em4932](lexer/cases/13-real-values/limit-3_4em4932.case), [limit-4em4932](lexer/cases/13-real-values/limit-4em4932.case), [limit-5em4932](lexer/cases/13-real-values/limit-5em4932.case)).
- With k from 0 to 27, the value is correctly rounded
  ([one](lexer/cases/13-real-values/one.case), [halfway](lexer/cases/13-real-values/halfway.case), [scale-up-*](lexer/cases/13-real-values/)). 10^27 is the largest power of ten that
  Extended holds exactly. With k above 27, it is at most one unit in the
  last place off, either way. With k below 0, it is from 10 units below to
  2 units above the correctly rounded value
  ([tenth](lexer/cases/13-real-values/tenth.case), [scale-??](lexer/cases/13-real-values/), [random-*](lexer/cases/13-real-values/)).

## Not covered yet

- The scanner inside `asm` blocks, which is a separate scanner: after `asm`,
  no further tokens reach the Pascal parser until the block's `end`.
- Include files (`{$I name}`), beyond the rule that they can't start
  inside a statement part. The cases are single files, so nesting, the
  return to the including file and the limit on open files are untested.
  How the file name is read (where it ends, its case, its length) shows
  only in error 15's message, which the cases don't record.
- `{$O unit}`, which needs units.
- Whether `CPU87` is predefined on a machine without a floating-point
  unit.
- The exact value of real literals (see [real values](#real-values)).
