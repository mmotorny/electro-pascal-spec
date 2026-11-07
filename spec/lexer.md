# Lexer

How `TPC.EXE` (Borland Pascal 7.01, real-mode command-line compiler) splits a
source file into tokens. Each rule links to the cases in
[`lexer/cases/`](lexer/cases) that show it. A case's `tpc:` and `output:`
lines are recorded from the real compiler and are the final word; where this
text and a case disagree, the case is right and this text needs fixing.

Status: first draft, from the Language Guide, the IDE help and black-box
probes. Every case's `tokens:` line matches the token stream captured from
`TPC` (issue #6). A case's token list ends where `TPC` stops asking for
tokens: at the end of the program, or at the token where it reports an
error. When the error is in the lexer itself, the bad token is not
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
  one character. A longer line is error 11 at column 128, wherever it is,
  even inside a comment ([program lines](lexer/cases/11-program-lines)).
  The error comes before any token on that line is delivered. The Language
  Guide's figure of 126 is wrong.
- ^Z (26) ends the file; nothing after it is read. When the file ends too
  early, the error is reported at column 1 of the line after the last line
  read, and a line that ^Z cuts short still counts as read
  ([end of file](lexer/cases/12-end-of-file)).
- Scanning stops after the program's final `end.`. Anything after it is
  never read ([end of file](lexer/cases/12-end-of-file)).

## Separators

- Characters 0 to 32 are blanks. Blanks and comments separate tokens and are
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
- Characters 128 to 255 are allowed only inside strings and comments.
  Elsewhere they are a syntax error (error 5)
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
  diagrams, the digits after `.` and after `E` may be missing: `1.`, `1.e5`
  and `1e` are all accepted, and a missing exponent counts as 0. The
  exponent's digits are read only while its value stays at most 9999, and
  the next digit starts a new token: `1e12345` is `REAL(1e1234)` then
  `INTEGER(5)`. Leading zeros in the exponent don't count. A number can't
  start with `.`. A value beyond the Extended range is error 6, just after
  the number.
- `1..2` is `1`, `..`, `2`: a `.` directly followed by another `.` doesn't
  make a real.

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
  the character in upper case with bit 64 flipped. `^M` and `^m` are `#13`,
  `^@` is `#0`, `^[` is `#27`, `^1` is `'q'`, `^'` is `'g'`, and `^` then a
  space is `` ` `` (96). Only one character is taken: `^Integer` is `^I`
  followed by the identifier `nteger`.

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

- `{` to the next `}`, or `(*` to the next `*)`. Comments may span lines.
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
that never ends. After the `$` comes one of:

- a conditional directive name (`DEFINE`, `UNDEF`, `IFDEF`, `IFNDEF`,
  `IFOPT`, `ELSE`, `ENDIF`);
- a list of switches, each a switch letter and `+` or `-`, separated by
  commas with no blanks: `{$R+,X-}`. Anything after the list and a blank
  is ignored;
- a parameter directive letter (`C D G I L M O R S`), followed by its
  parameter or nothing at all: `{$R}` is accepted.

Anything else is error 17, at the column of the offending item: a blank
right after `$`, an unknown name such as `{$FOO}` or `{$Z+}`, a switch
letter that isn't also a parameter directive written without its sign
(`{$T}`), or a missing item after a comma (`{$R+,}`).

The conditional directives work at this level: text skipped by `{$IFDEF}`
and similar produces no tokens. It is still read for comments and quoted
strings, though: a `{$ENDIF}` inside a comment or after an apostrophe on the
same line doesn't count. A string still open at the end of a line just ends
there. A comment still open at the end of the file is error 10, and a
missing `{$ENDIF}` is error 129, both at the end of the file.

## Real values

([real values](lexer/cases/13-real-values))

Each case here prints the exact 80-bit Extended value of a real literal.
`TPC`'s conversion is not correctly rounded: it is often a few units off in
the last place, so an implementation has to reproduce `TPC`'s own
arithmetic. That arithmetic isn't known yet (issue #10). What is known:

- The largest accepted value is about `1.1897314e4932`. The largest
  Extended value itself, `1.18973149535723176502e4932`, is already error 6.
- Values below the smallest normal Extended value (about
  `3.3621e-4932`) become 0. There are no denormals.

## Not covered yet

- The scanner inside `asm` blocks, which is a separate scanner: after `asm`,
  no further tokens reach the Pascal parser until the block's `end`.
- Include files (`{$I name}`).
- The exact value of real literals (see [real values](#real-values)).
- Why real overflow is reported just after the number, while integer
  overflow is reported at the digit that overflows.
