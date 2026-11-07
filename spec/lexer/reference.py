"""A reference lexer that follows spec/lexer.md.

It exists to check the spec: it predicts the token stream for any source, and
those predictions are compared with the cases and with tokens captured from
TPC. It is written from the spec's text, not from TPC.

`lex(source)` returns (tokens, error). Tokens are in the spec's notation.
error is None, or (code, line, column) for an error the lexer itself
reports. The lexer knows nothing of the parser, so where TPC stops early at
a parser error, TPC's tokens are a prefix of these.

Where `^` is a character and where it is CARET depends on the parser; this
lexer approximates it from the previous token and the declaration part it
is in (see `_caret_is_char`).
"""

import decimal
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cases import pascal_string  # noqa: E402

RESERVED = set("""and array asm begin case const constructor destructor div do downto else
end file for function goto if implementation in inherited inline interface label mod
nil not object of or packed procedure program record repeat set shl shr string then
to type unit until uses var while with xor""".split())
PAIRS = {b":=": "ASSIGN", b"<=": "LE", b">=": "GE", b"<>": "NE", b"..": "DOTDOT",
         b"(.": "LBRACKET", b".)": "RBRACKET"}
SINGLES = {b"+": "PLUS", b"-": "MINUS", b"*": "STAR", b"/": "SLASH", b"=": "EQ", b"<": "LT",
           b">": "GT", b"[": "LBRACKET", b"]": "RBRACKET", b".": "DOT", b",": "COMMA",
           b"(": "LPAREN", b")": "RPAREN", b":": "COLON", b";": "SEMI", b"^": "CARET", b"@": "AT"}
# Tokens after which an operand is expected, so ^ starts a character.
OPERAND_EXPECTED = {"ASSIGN", "LPAREN", "COMMA", "LBRACKET", "PLUS", "MINUS", "STAR", "SLASH",
                    "EQ", "NE", "LT", "LE", "GT", "GE", "DIV", "MOD", "AND", "OR", "XOR", "SHL",
                    "SHR", "NOT", "IN", "DOTDOT", "THEN", "ELSE", "DO", "TO", "DOWNTO", "UNTIL",
                    "BEGIN", "SEMI", "CASE", "OF", "IF", "WHILE", "REPEAT", "COLON"}
# Declaration parts in which = and : are followed by a type.
TYPE_PARTS = {"TYPE", "VAR"}
SECTION_WORDS = {"CONST", "TYPE", "VAR", "LABEL", "BEGIN", "PROCEDURE", "FUNCTION",
                 "CONSTRUCTOR", "DESTRUCTOR", "IMPLEMENTATION", "INTERFACE"}
PREDEFINED = {"VER70", "MSDOS", "CPU86", "CPU87"}
MAX_LINE = 127
EXTENDED_MAX = "1.18973149535723176502e4932"
# Errors only the lexer reports; when TPC reports one, the spec must too.
LEXICAL_ERRORS = {6, 7, 8, 11}


class LexError(Exception):
    def __init__(self, code, line, column):
        self.code, self.line, self.column = code, line, column


def _lines(source):
    """Splits at LF after cutting at ^Z; checks line lengths (CRs don't count)."""
    end = source.find(b"\x1a")
    if end >= 0:
        source = source[:end]
    lines = source.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


class _Lexer:
    def __init__(self, source):
        self.lines = _lines(source)
        self.n = 0          # index of the current line
        self.text = b""     # current line, without CRs, as columns
        self.pos = 0
        self.loaded = False
        self.tokens = []
        self.part = None    # current declaration part
        self.defines = set(PREDEFINED)

    # Reading characters ------------------------------------------------------

    def _load(self):
        while True:
            if self.n >= len(self.lines):
                return False
            text = self.lines[self.n].replace(b"\r", b"")
            if len(text) > MAX_LINE:
                raise LexError(11, self.n + 1, MAX_LINE + 1)
            self.text, self.pos, self.loaded = text, 0, True
            return True

    def peek(self, k=0):
        """The character k ahead on the current line, or None at its end."""
        i = self.pos + k
        return self.text[i:i + 1] if i < len(self.text) else None

    def at_eof(self):
        return self.n >= len(self.lines)

    def next_line(self):
        self.n += 1
        self.loaded = False
        return self._load()

    def where(self, offset=0):
        return self.n + 1, self.pos + 1 + offset

    def eof_error(self, code=10):
        return LexError(code, len(self.lines) + 1, 1)

    # Skipping blanks, comments and directives --------------------------------------

    def skip(self):
        """Skips blanks and comments. Returns False at the end of the file."""
        if not self.loaded and not self._load():
            return False
        while True:
            c = self.peek()
            if c is None:
                if not self.next_line():
                    return False
            elif c[0] <= 32:
                self.pos += 1
            elif c == b"{":
                self.pos += 1
                self.comment(b"}")
            elif c == b"(" and self.peek(1) == b"*":
                self.pos += 2
                self.comment(b"*)")
            else:
                return True

    def comment(self, close):
        """Reads a comment up to `close`; handles directives."""
        body = bytearray()
        while True:
            if self.text.startswith(close, self.pos):
                self.pos += len(close)
                break
            c = self.peek()
            if c is None:
                body += b"\n"
                if not self.next_line():
                    raise self.eof_error()
                continue
            body += c
            self.pos += 1
        if body[:1] == b"$":
            self.directive(bytes(body[1:]))

    def directive(self, body):
        words = body.decode("latin-1").split()
        name = words[0].upper() if words else ""
        arg = words[1].upper() if len(words) > 1 else ""
        if name == "DEFINE":
            self.defines.add(arg)
        elif name == "UNDEF":
            self.defines.discard(arg)
        elif name in ("IFDEF", "IFNDEF", "IFOPT"):
            if name == "IFDEF":
                taken = arg in self.defines
            elif name == "IFNDEF":
                taken = arg not in self.defines
            else:
                taken = arg in ("N-", "E+", "R-", "S+", "I+", "B-", "X+", "V+", "A+", "D+", "L+", "F-", "G-", "O-", "P-", "Q-", "T-")
            if not taken:
                self.skip_conditional()

    def skip_conditional(self):
        """Skips text up to the matching {$ELSE} or {$ENDIF}, minding comments."""
        depth = 0
        while True:
            c = self.peek()
            if c is None:
                if not self.next_line():
                    raise self.eof_error(129)
                continue
            if c == b"{" or (c == b"(" and self.peek(1) == b"*"):
                close = b"}" if c == b"{" else b"*)"
                self.pos += 1 if c == b"{" else 2
                body = bytearray()
                while not self.text.startswith(close, self.pos):
                    ch = self.peek()
                    if ch is None:
                        if not self.next_line():
                            raise self.eof_error(129)
                        continue
                    body += ch
                    self.pos += 1
                self.pos += len(close)
                if body[:1] == b"$":
                    name = bytes(body[1:]).decode("latin-1").split()[:1]
                    name = name[0].upper() if name else ""
                    if name in ("IFDEF", "IFNDEF", "IFOPT"):
                        depth += 1
                    elif name == "ENDIF":
                        if depth == 0:
                            return
                        depth -= 1
                    elif name == "ELSE" and depth == 0:
                        return
            elif c == b"'":
                # Strings in skipped text aren't scanned; an apostrophe is just a character.
                self.pos += 1
            else:
                self.pos += 1

    # Tokens ------------------------------------------------------------------

    def emit(self, token):
        self.tokens.append(token)
        name = token.split("(")[0]
        if name in SECTION_WORDS:
            self.part = name

    def last(self):
        return self.tokens[-1].split("(")[0] if self.tokens else None

    def _caret_is_char(self):
        prev = self.last()
        if prev in ("EQ", "COLON", "OF") and self.part in TYPE_PARTS:
            return False
        if prev == "COLON" and self.part == "CONST":
            return False
        return prev in OPERAND_EXPECTED

    def run(self):
        while self.skip():
            c = self.peek()
            line, column = self.where()
            if c.isalpha() or c == b"_":
                self.word()
            elif c.isdigit():
                self.number()
            elif c == b"$":
                self.hex_number()
            elif c in (b"'", b"#") or (c == b"^" and self._caret_is_char()):
                self.string()
            else:
                pair = self.text[self.pos:self.pos + 2]
                if pair in PAIRS:
                    self.pos += 2
                    self.emit(PAIRS[pair])
                elif c in SINGLES:
                    self.pos += 1
                    self.emit(SINGLES[c])
                else:
                    raise LexError(5, line, column)
            if self.tokens[-2:] == ["END", "DOT"]:
                return

    def word(self):
        start = self.pos
        while (c := self.peek()) is not None and (c.isalnum() or c == b"_") and c[0] < 128:
            self.pos += 1
        word = self.text[start:self.pos].decode("ascii")
        if word.lower() in RESERVED:
            self.emit(word.upper())
        else:
            self.emit(f"IDENT({word.upper()[:63]})")

    def digits(self, hex_digits=False):
        start = self.pos
        ok = b"0123456789abcdefABCDEF" if hex_digits else b"0123456789"
        while (c := self.peek()) is not None and c in ok:
            self.pos += 1
        return self.text[start:self.pos]

    def number(self):
        start = self.pos
        whole = self.digits()
        real = False
        if self.peek() == b"." and self.peek(1) not in (b".", b")"):
            real = True
            self.pos += 1
            self.digits()
        if self.peek() in (b"e", b"E"):
            real = True
            self.pos += 1
            if self.peek() in (b"+", b"-"):
                self.pos += 1
            self.digits()
        text = self.text[start:self.pos].decode("ascii")
        if real:
            number = text.rstrip("eE+-")
            if decimal.Decimal(number if not number.endswith(".") else number + "0") > decimal.Decimal(EXTENDED_MAX):
                raise LexError(6, self.n + 1, self.pos + 1)
            self.emit(f"REAL({text})")
            return
        value = int(whole)
        if value > 2147483647:
            raise LexError(7, self.n + 1, start + len(whole))
        self.emit(f"INTEGER({value})")

    def hex_number(self):
        self.pos += 1
        digits = self.digits(hex_digits=True)
        if not digits:
            raise LexError(7, *self.where())
        value = int(digits, 16)
        if value > 0xFFFFFFFF:
            raise LexError(7, self.n + 1, self.pos)
        self.emit(f"INTEGER({value - (1 << 32) if value >= 1 << 31 else value})")

    def string(self):
        value = bytearray()
        while True:
            c = self.peek()
            if c == b"'":
                self.pos += 1
                while True:
                    ch = self.peek()
                    if ch is None:
                        raise LexError(8, *self.where())
                    self.pos += 1
                    if ch == b"'":
                        if self.peek() == b"'":
                            self.pos += 1
                            value += b"'"
                        else:
                            break
                    else:
                        value += ch
            elif c == b"#":
                self.pos += 1
                if self.peek() == b"$":
                    self.pos += 1
                    digits = self.digits(hex_digits=True)
                    number = int(digits, 16) if digits else None
                else:
                    digits = self.digits()
                    number = int(digits) if digits else None
                if number is None:
                    raise LexError(7, *self.where())
                value.append(number & 255)
            elif c == b"^" and (value or self._caret_is_char()):
                ch = self.peek(1)
                if ch is None:
                    break
                self.pos += 2
                value.append(ord(ch.upper()) ^ 64)
            else:
                break
        self.emit(f"STRING({pascal_string(bytes(value))})")


def lex(source):
    lexer = _Lexer(source)
    try:
        lexer.run()
        return lexer.tokens, None
    except LexError as e:
        return lexer.tokens, (e.code, e.line, e.column)


def check(tokens, error, captured, verdict):
    """Compares a prediction with what TPC did; returns a problem or None.

    captured: TPC's tokens in the spec's notation; verdict: "ok" or
    "error N at L:C".
    """
    if captured != tokens[:len(captured)]:
        i = next(i for i, (a, b) in enumerate(zip(captured, tokens + [None] * len(captured))) if a != b)
        return f"token {i + 1}: TPC {captured[i]}, spec {tokens[i] if i < len(tokens) else '(end)'}"
    if error:
        expected = f"error {error[0]} at {error[1]}:{error[2]}"
        if len(captured) == len(tokens) and verdict != expected:
            return f"spec predicts {expected} after token {len(tokens)}, TPC: {verdict}"
    words = verdict.split()
    if len(words) > 1 and words[0] == "error" and int(words[1]) in LEXICAL_ERRORS:
        if not error or len(captured) != len(tokens):
            return f"TPC reports {verdict} after token {len(captured)}; the spec predicts no lexer error there"
    return None
