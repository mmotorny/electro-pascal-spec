# Where Borland's documents and TPC disagree

The spec describes only what `TPC` does. This file collects the places where
Borland's own documents (the Turbo Pascal 7.0 Language Guide and the IDE's
online help) describe something else, for whoever writes up the story of
this project. Each entry says what the document claims, in our own words,
what `TPC` does instead, and the cases that show it. `TPC` is right by
definition: it's the compiler people's programs were built with.

## Lexer

- **Line length.** The Language Guide gives 126 characters as the longest
  allowed line. `TPC` accepts 127 and rejects 128
  ([line-127](../spec/lexer/cases/11-program-lines/line-127.yaml),
  [line-128](../spec/lexer/cases/11-program-lines/line-128.yaml)).
- **`<>`.** The Language Guide's list of two-character special symbols
  leaves out `<>`. `TPC` treats it as one symbol like the others
  ([relational](../spec/lexer/cases/03-special-symbols/relational.yaml)).
- **`exports` and `library`.** The IDE help lists both as reserved words.
  `TPC` accepts them as ordinary identifiers
  ([not-reserved-exports](../spec/lexer/cases/04-reserved-words/not-reserved-exports.yaml),
  [not-reserved-library](../spec/lexer/cases/04-reserved-words/not-reserved-library.yaml)).
- **Identifiers starting with `_`.** The IDE help says an identifier must
  start with a letter. `TPC` accepts an underscore first, and `_` alone
  ([underscore-first](../spec/lexer/cases/05-identifiers/underscore-first.yaml),
  [underscore-only](../spec/lexer/cases/05-identifiers/underscore-only.yaml)).
- **Digits in reals.** The Language Guide's syntax diagrams require digits
  after the decimal point and after `E`. `TPC` accepts `1.`, `1.e5`, `1e`,
  `1e+` and `1e-`
  ([real-no-fraction-digits](../spec/lexer/cases/06-numbers/real-no-fraction-digits.yaml),
  [real-dot-exponent](../spec/lexer/cases/06-numbers/real-dot-exponent.yaml),
  [real-exponent-no-digits](../spec/lexer/cases/06-numbers/real-exponent-no-digits.yaml),
  [real-exponent-plus-no-digits](../spec/lexer/cases/06-numbers/real-exponent-plus-no-digits.yaml),
  [real-exponent-minus-no-digits](../spec/lexer/cases/06-numbers/real-exponent-minus-no-digits.yaml)).
