# Lexer

How `TPC.EXE` (Borland Pascal 7.01, real-mode command-line compiler) splits a
source file into tokens. Each rule links to the cases in
[`lexer/cases/`](lexer/cases) that show it. A case's `tpc:` and `output:`
lines are recorded from the real compiler and are the final word; where this
text and a case disagree, the case is right and this text needs fixing.

Status: first draft, from the Language Guide, the IDE help and black-box
probes. Every case's `tokens:` line matches the token stream captured from
`TPC` (issue #6). Between them, the cases take both sides of every branch
in `TPC`'s scanner that a single source file can reach, except as noted
under [not covered yet](#not-covered-yet). A case's token list ends where
`TPC` stops asking for tokens: at the end of the program, or at the token
where it reports an error. When the error is in the lexer itself, the bad token is not
delivered.

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

- A file is a sequence of bytes. Line feed (10) ends a line. Carriage return
  (13) does not: a file with CR alone is one long line
  ([separators](lexer/cases/01-separators)).
- A line may hold at most 127 characters, not counting CRs. A tab counts as
  one character. A longer line is error 11 at column 128, wherever it is:
  inside a comment, an unterminated string or text skipped by `{$IFDEF}`
  too ([program lines](lexer/cases/11-program-lines)).
  The error comes before any token on that line is delivered. The Language
  Guide's figure of 126 is wrong.
- NUL (0) bytes are dropped as a line is read, as if they weren't in the
  file: `pro`, NUL, `gram` is `program`, a NUL between two digits or inside
  a quoted string disappears, and NULs don't count toward the line length
  ([character set](lexer/cases/02-character-set)).
- Nothing changes where a token crosses a 4096-byte boundary of the file
  ([program lines](lexer/cases/11-program-lines)).
- ^Z (26) ends the file; nothing after it is read. When the file ends too
  early, the error is reported at column 1 of the line after the last line
  read, and a line that ^Z cuts short still counts as read
  ([end of file](lexer/cases/12-end-of-file)).
- Scanning stops after the program's final `end.`. Anything after it is
  never read ([end of file](lexer/cases/12-end-of-file)).

## Separators

- Characters 1 to 32 are blanks (0 never gets this far, see
  [source text](#source-text)). Blanks and comments separate tokens and are
  otherwise ignored.
- A separator is needed only between two tokens that would otherwise run
  together: two words (reserved words or identifiers) or a word and a
  number. `programP` is a single identifier
  ([separators](lexer/cases/01-separators)).
- A blank inside a two-character symbol splits it: `: =` is `:` then `=`
  ([special symbols](lexer/cases/03-special-symbols)).

## Character set

- Reserved words and identifiers are made of the letters A–Z and a–z, the
  digits 0–9 and the underscore. Case doesn't matter.
- The printable characters ``! " % & ? \ ` | ~``, DEL (127) and the
  characters 128 to 255 are allowed only inside strings and comments.
  Elsewhere each is error 5, and no token is delivered for it
  ([character set](lexer/cases/02-character-set)).

## Special symbols

Single characters `+ - * / = < > [ ] . , ( ) : ; ^ @` and pairs
`<= >= <> := .. (. .)` ([special symbols](lexer/cases/03-special-symbols)).
`(.` and `.)` mean the same as `[` and `]`. `{ } (* *)` delimit
[comments](#comments). `$` and `#` start [hex numbers](#numbers) and
[control characters](#character-strings). The Language Guide leaves `<>`
out of its list, but it is a symbol.

## Reserved words

These 49 words are reserved and can't be used as identifiers
([reserved words](lexer/cases/04-reserved-words)):

`and array asm begin case const constructor destructor div do downto else
end file for function goto if implementation in inherited inline interface
label mod nil not object of or packed procedure program record repeat set
shl shr string then to type unit until uses var while with xor`

Not reserved in `TPC`, although the IDE help lists the first two as
reserved: `exports library`. The standard directives `absolute assembler
export external far forward index interrupt near private public resident
virtual` are ordinary identifiers to the lexer.

## Identifiers

- A letter or underscore, then any number of letters, digits and
  underscores. `_` alone is an identifier. The IDE help's claim that the
  first character must be a letter is wrong
  ([identifiers](lexer/cases/05-identifiers)).
- Only the first 63 characters are significant: identifiers that agree in
  their first 63 characters are the same identifier.
- A qualified identifier such as `System.WriteLn` is three tokens.

## Numbers

([numbers](lexer/cases/06-numbers))

- **Decimal integers** are digit sequences with values from 0 to
  2147483647. Leading zeros don't matter. A larger value is error 7, at the
  digit where the value first goes over: in a run of twenty `1`s, that's
  the 11th. A minus sign is a separate token, so `-2147483648` is an error.
- **Hex integers** are `$` and one or more hex digits, either case, with a
  value up to `$FFFFFFFF`, and error 7 likewise at the digit that goes over.
  Leading zeros don't count. The value is a 32-bit pattern read as signed:
  `$FFFFFFFF` is -1 and `$80000000` is -2147483648. `$` without a hex digit
  right after it is error 7.
- **Reals** are digits, then a fraction (`.` and digits), an exponent
  (`E` or `e`, an optional sign and digits), or both. Unlike the syntax
  diagrams, the digits after `.` and after `E` may be missing: `1.`, `1.e5`,
  `1e`, `1e+` and `1e-` are all accepted, and a missing exponent counts
  as 0. The
  exponent's digits are read only while its value stays at most 9999, and
  the next digit starts a new token: `1e12345` is `REAL(1e1234)` then
  `INTEGER(5)`. Leading zeros in the exponent don't count. A number can't
  start with `.`. A value beyond the Extended range is error 6, just after
  the number.
- `1..2` is `1`, `..`, `2`, and `1.)` is `1`, `.)`: a `.` directly
  followed by another `.` or by `)` doesn't make a real. `1. )` is
  `REAL(1.)` and `)`.

## Labels

A label is an identifier or a number from 0 to 9999; leading zeros don't
matter, so `01` and `1` are the same label ([labels](lexer/cases/07-labels)).
To the lexer a numeric label is an ordinary `INTEGER`: `10000` is delivered
as a number and then rejected where a label is expected.

## Character strings

([character strings](lexer/cases/08-strings))

A string is a run of parts with no separators between them. A blank between
parts ends the string, and the next part starts a new one. The parts are:

- **Quoted strings**: characters between apostrophes on one line, with two
  apostrophes standing for one. A line end before the closing apostrophe is
  error 8.
- **`#` and a number**, decimal or hex, with no blank after `#`. The
  number is read like any integer, with the same limits and error 7 when it
  overflows. Then only its low 8 bits are used: `#256` is `#0`, `#65601` is
  `'A'` and `#2147483647` is `#255`.
- **`^` and the very next character**, whatever it is, a blank included:
  the character with bit 64 flipped, after changing `a` to `z` to upper
  case. `^M` and `^m` are `#13`, `^@` is `#0`, `^[` is `#27`, `^1` is `'q'`,
  `^'` is `'g'`, and `^` then a space is `` ` `` (96). Only `a` to `z`
  change case: `` ^` `` is `' '`, `^z` is `#26`, `^{` is `';'`, `^~` is
  `'>'`, `^` then DEL (127) is `'?'` and `^` then character 233 is `#169`.
  Only one character is taken: `^Integer` is `^I`
  followed by the identifier `nteger`. Where an operand is expected but `^`
  is the last character on its line, `TPC` delivers `CARET` and then
  reports error 8 just after it, as for an unterminated string.

Whether `^` starts a string depends on where it appears. Where an operand
of an expression is expected, `^` and the next character are a character
string as above, and join with neighbouring parts: in constant expressions,
statements, set constructors and `case` labels. Everywhere else `^` is
`CARET`:

- wherever a type is expected: after `=` in a type declaration, after `:`
  in a variable, record field or typed constant declaration, and after `of`
  in an array type. There `^M` is always a pointer to type `M`, so a
  subrange of characters can't be written with `^`: `type T = ^A..^Z` is an
  error. `^1` there is `CARET INTEGER(1)`.
- after an operand, where it dereferences a pointer: `Q^.F`, `(Q)^`.

## Comments

([comments](lexer/cases/09-comments))

- `{` to the next `}`, or `(*` to the next `*)`. Comments of both kinds may
  span lines. A `*` at the end of one line and a `)` at the start of the
  next don't end a `(*` comment.
- They don't nest, and the other kind of delimiter has no effect inside
  one: `{ (* }` is a complete comment.
- `(*)` opens a comment; the `)` is part of it.
- A `}` outside a comment is a syntax error. A `*)` outside a comment is
  simply `*` followed by `)`. A comment still open at the end of the file is
  error 10.

## Compiler directives

([compiler directives](lexer/cases/10-compiler-directives))

A comment whose first character is `$` is a compiler directive. Directives
are not tokens. Their names aren't case sensitive. `{ $R+}` is an ordinary
comment.

A directive is checked as soon as `{$` or `(*$` is read, before the end of
the comment is looked for, so a bad directive is error 17 even in a comment
that never ends. Its name is the run of letters and digits after the `$`,
so `{$M16384}` has the unknown name `M16384`. The name is one of:

- a conditional directive name (`DEFINE`, `UNDEF`, `IFDEF`, `IFNDEF`,
  `IFOPT`, `ELSE`, `ENDIF`);
- a list of switches, each a switch letter and `+` or `-`, separated by
  commas with no blanks: `{$R+,X-}`. A blank after a comma is error 17.
  Anything after the last sign that isn't a comma is ignored, a blank or
  not: `{$R+ text}` is accepted, and `{$R-B+}` turns R off and leaves B
  alone;
- a parameter directive letter (`C D G I L M O R S`) and its parameter.
  For `C`, `D`, `G`, `R` and `S` the parameter is any text up to the end of
  the comment, nothing at all included, and is ignored: `{$R}` is accepted.
  `I` and `L` take a file name, and `{$L:X.OBJ}` is accepted (a missing
  file is error 15, but that's not the lexer's business). `O` takes a unit
  name. `M` takes numbers, see [memory sizes](#memory-sizes).

Anything else is error 17, at the column of the offending item: a blank
right after `$`, an unknown name such as `{$FOO}` or `{$Z+}`, a switch
letter that isn't also a parameter directive written without its sign
(`{$T}`), or a missing item after a comma (`{$R+,}`).

### Switches that must come first

The switches `A D E G K L N O T X Y` may appear only before the program
heading or right after it. After a `uses` clause or a declaration, or inside
a statement part, any of them is error 17 at the switch letter. The other
switches (`B F I P Q R S V W`) and `{$M}` may appear anywhere.

### Memory sizes

`{$M stack,heapmin,heapmax}` takes three numbers, decimal or hex. Before
each number, any run of blanks, commas and semicolons is skipped, so
`{$M 16384 0 655360}`, `{$M 16384;0;655360}` and `{$M ,16384,,0, ,655360}`
are all accepted. Anything after the third number is ignored. A number that
is missing or out of range is error 17 at the place where it starts or
should start, so `{$M}`, `{$M ABC}`, `{$M=16384}`, `{$M 16384}` and
`{$M 16384,0}` are all errors.

- `stack` is rounded down to an even number and must then be from 1024 to
  65520: 1023 and 65522 are errors, 1025 is used as 1024 and 65521 as
  65520.
- `heapmin` and `heapmax` are rounded up to a whole number of 16-byte
  paragraphs and may be at most 655360. After rounding, `heapmax` may not be
  below `heapmin`: `{$M 16384,1024,1009}` is accepted, as both are 64
  paragraphs, and `{$M 16384,1024,1008}` is an error. A number too large
  for an integer is an error too.

### Conditional symbols

`{$DEFINE name}` defines a conditional symbol and `{$UNDEF name}` removes
it. Defining a symbol that is already defined, or removing one that isn't,
does nothing: after defining `X` twice and removing it once, `X` is
undefined.

A symbol's name is read like an identifier: a letter or underscore, then
letters, digits and underscores, with case not mattering and only the first
63 characters significant. It ends at the first other character, so
`{$DEFINE A$}` defines `A`, and it may be a reserved word. A missing name,
or one starting with a digit, is error 2 where the name should start. This
goes for `{$UNDEF}`, `{$IFDEF}` and `{$IFNDEF}` too.

`VER70`, `MSDOS`, `CPU86` and `CPU87` are defined from the start;
`VER60`, `DPMI` and `WINDOWS` are not. The reference machine has a
floating-point unit; whether `CPU87` depends on one is untested. The defined
symbols, these four included, share 1024 bytes, each taking its length
plus one. A `{$DEFINE}` that doesn't fit is error 127 at its name.
Removing a symbol, even a predefined one, makes room again.

### Conditional compilation

The conditional directives work at this level: skipped text produces no
tokens.

- `{$IFDEF name}` compiles the text up to its `{$ELSE}` or `{$ENDIF}` if
  `name` is defined, and skips it otherwise. `{$IFNDEF name}` does the
  opposite.
- `{$IFOPT X+}` and `{$IFOPT X-}` test whether switch `X` is on or off.
  After any blanks comes a switch letter and its sign; anything after that
  is ignored. A letter that isn't a switch (`Z`), one that is only a
  parameter directive (`M`), or a missing sign is error 17 at the letter.
- `{$ELSE}` switches from compiling to skipping or back. A second `{$ELSE}`
  at the same level switches again: in `{$IFDEF X} a {$ELSE} b {$ELSE} c
  {$ENDIF}`, `a` and `c` are compiled when `X` is defined, and only `b`
  when it isn't.
- Conditionals nest, in compiled and in skipped text alike. In skipped
  text, only the conditional directives count: `{$IFDEF}`, `{$IFNDEF}` and
  `{$IFOPT}` open a level, `{$ENDIF}` closes one, and an `{$ELSE}` or
  `{$ENDIF}` at the outermost level ends the skipping. All other
  directives there are ignored, even unknown ones, and so is anything
  after a directive's name: `{$ENDIF junk}` ends skipped text but
  `{$ENDIFX}` doesn't.
- `{$ELSE}` or `{$ENDIF}` with no conditional open is error 128 at its
  name. A conditional still open at the program's final `end.` is error
  129 at the `.`.

Skipped text is still read for comments and quoted strings, though: a
`{$ENDIF}` inside a comment or after an apostrophe on the same line doesn't
count. A string still open at the end of a line just ends there. A comment
still open at the end of the file is error 10, and a missing `{$ENDIF}` is
error 129, both at the end of the file.

### Include files

`{$I name}` inside a statement part is error 118, just after the
directive, before `TPC` looks for the file.

### `)` ending a `(*$` directive

In a directive written with `(*$`, a `)` directly after the directive's
last item ends the comment, as `*)` would, in exactly these cases:

- `(*$M stack,heapmin,heapmax)`, when `heapmax` in paragraphs (rounded up)
  is 42 more than a multiple of 256: 672 bytes (42 paragraphs) and 4768
  bytes (298 paragraphs) end the comment, and 688 bytes (43 paragraphs)
  doesn't.
- `(*$UNDEF name)`, when `name` is defined and 42 characters long.
- `(*$DEFINE name)`, when `name` isn't defined yet and, once it is, the
  defined symbols take up 222 more than a multiple of 256 bytes, counted as
  under [conditional symbols](#conditional-symbols).
- `(*$R)` in skipped text. In compiled text, `(*$R)` stays open.

All other directives stay open past such a `)`: switches and switch lists,
the other parameter directives (`{$L}` included), `{$IFDEF}`, `{$IFNDEF}`,
`{$IFOPT}`, `{$ELSE}`, `{$ENDIF}`, `{$DEFINE}` of a defined symbol and
`{$UNDEF}` of an undefined one. `{$O}` is untested, as it needs units.

## Real values

([real values](lexer/cases/13-real-values))

Each case here prints the exact 80-bit Extended value of a real literal.
`TPC`'s conversion is not correctly rounded, so an implementation has to
reproduce `TPC`'s own arithmetic. That arithmetic isn't known yet
(issue #10). What is known:

- Only the first 19 significant digits count; any digits after them are
  ignored, as if they were 0. Below, N is those digits read as an integer,
  without trailing zeros, and k is the power of ten that scales N to the
  literal's value.
- A literal whose first 19 digits are above the largest Extended value
  (`1.18973149535723176502…e4932`) is error 6. So
  `1.189731495357231764e4932` is the largest accepted literal and
  `1.189731495357231765e4932` is an error, and so is the largest Extended
  value itself written to 20 digits.
- A literal whose first 19 digits are below the smallest normal Extended
  value (`3.36210314311209350626…e-4932`) becomes 0. There are no
  denormals. So `3.362103143112093507e-4932` is the smallest literal that
  isn't 0, and `3.362103143112093506e-4932` is 0.
- Every case with k from 0 to 27 is correctly rounded (19 cases). 10^27 is
  the largest power of ten that Extended holds exactly. Of the cases with k
  above 27, 5 of 21 are correctly rounded and the rest are off by one unit
  in the last place, either way. Of the cases with k below 0, 38 of 66 are
  correctly rounded and the rest are off by −10 to +2 units.

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
- Why real overflow is reported just after the number, while integer
  overflow is reported at the digit that overflows.
