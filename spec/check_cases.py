"""Checks the cases and how spec/lexer.md cites them, without running TPC.

Every case must have a description, a token list that uses only the
notation of spec/lexer.md, and a recorded verdict (run `bazel run
//spec:record` after adding or changing a case).

Every link from spec/lexer.md into lexer/cases/ must name an existing case,
or, for a link to a folder, have text that is a pattern matching at least
one case in it; and every case must be cited by some link.

The rules that spec/lexer.md gives for real values must hold for every case
in 13-real-values (see check_real_values).
"""

import fnmatch
import os
import re
import sys
from fractions import Fraction

import cases

RESERVED = set("""AND ARRAY ASM BEGIN CASE CONST CONSTRUCTOR DESTRUCTOR DIV DO DOWNTO
ELSE END FILE FOR FUNCTION GOTO IF IMPLEMENTATION IN INHERITED INLINE INTERFACE
LABEL MOD NIL NOT OBJECT OF OR PACKED PROCEDURE PROGRAM RECORD REPEAT SET SHL
SHR STRING THEN TO TYPE UNIT UNTIL USES VAR WHILE WITH XOR""".split())
SYMBOLS = set("""PLUS MINUS STAR SLASH EQ NE LT LE GT GE LPAREN RPAREN LBRACKET RBRACKET
DOT DOTDOT COMMA COLON SEMI ASSIGN CARET AT""".split())
STRING_VALUE = r"(?:'(?:[^']|'')*'|#\d+)+"
VALUED = {
    "IDENT": r"[A-Z_][A-Z0-9_]{0,62}",
    "INTEGER": r"-?\d+",
    "REAL": r"\d+(?:\.\d*)?(?:[eE][+-]?\d*)?",
    "STRING": STRING_VALUE,
}


def check(case):
    problems = []
    if not case.comments:
        problems.append("no description")
    if "tokens" not in case.fields:
        problems.append("no tokens: line")
    for token in case.tokens():
        match = re.fullmatch(r"([A-Z]+)\((.*)\)", token)
        if match:
            kind, value = match.groups()
            if kind not in VALUED or not re.fullmatch(VALUED[kind], value):
                problems.append(f"bad token {token}")
        elif token not in RESERVED and token not in SYMBOLS:
            problems.append(f"unknown token {token}")
    verdict = case.fields.get("tpc")
    if not verdict or not re.fullmatch(r"ok|error \d+(?: at \d+:\d+)?", verdict):
        problems.append("no recorded verdict; run bazel run //spec:record")
    if verdict == "ok" and "output" not in case.fields:
        problems.append("no recorded output; run bazel run //spec:record")
    if "output" in case.fields and not re.fullmatch(STRING_VALUE, case.fields["output"]):
        problems.append("bad output")
    return problems


def check_citations(spec_path, found):
    """Problems with the spec's links to cases, as (where, problem) pairs."""
    spec_dir = os.path.dirname(spec_path)
    with open(spec_path, encoding="utf-8") as f:
        text = f.read()
    cited, problems = set(), []
    for label, target in re.findall(r"\[([^\]]+)\]\((lexer/cases/[^)]*)\)", text):
        path = os.path.normpath(os.path.join(spec_dir, target))
        if target.endswith(".case"):
            if os.path.isfile(path):
                cited.add(path)
            else:
                problems.append(("lexer.md", f"link to missing case {target}"))
        elif any(c in label for c in "*?["):
            matches = [c.path for c in found
                       if os.path.dirname(c.path) == path and fnmatch.fnmatch(c.name, label)]
            if matches:
                cited.update(matches)
            else:
                problems.append(("lexer.md", f"pattern {label} matches no case in {target}"))
        elif target.rstrip("/") != "lexer/cases":
            problems.append(("lexer.md", f"link to {target} should name a case or a pattern"))
    for case in found:
        if case.path not in cited:
            problems.append((case.path, "not cited in lexer.md"))
    return problems


# The smallest literal value that is error 6, a little below the largest
# Extended value, and the smallest normal Extended value, below which a
# literal becomes 0.
OVERFLOW = Fraction(1189731495357231765) * Fraction(10) ** (4932 - 18)
EXTENDED_MIN_NORMAL = Fraction(2) ** -16382
LITERAL = re.compile(r"const C = (\d*)(?:\.(\d*))?(?:[eE]([+-]?\d*))?;")


def literal(source):
    """(N, k) for the case's real literal: its first 19 significant digits
    as an integer without trailing zeros, and the power of ten scaling it."""
    match = LITERAL.search(source)
    if not match:
        return None
    whole, fraction, exponent = match[1] or "", match[2] or "", match[3] or ""
    digits = whole + fraction
    significant = digits.lstrip("0")[:19]
    if not significant:
        return 0, 0
    exponent = int(exponent) if exponent.strip("+-") else 0
    skipped = len(digits) - len(digits.lstrip("0"))
    k = exponent + len(whole) - skipped - len(significant)
    stripped = significant.rstrip("0")
    return int(stripped), k + len(significant) - len(stripped)


def extended(hex_text):
    """The value of an 80-bit Extended written in hex, most significant byte
    first, and the size of one unit in its last place."""
    data = bytes.fromhex(hex_text)
    sign_exponent, mantissa = int.from_bytes(data[:2], "big"), int.from_bytes(data[2:], "big")
    exponent = sign_exponent & 0x7FFF
    if exponent == 0:
        return Fraction(mantissa) * Fraction(2) ** (-16382 - 63), Fraction(2) ** (-16382 - 63)
    unit = Fraction(2) ** (exponent - 16383 - 63)
    return mantissa * unit, unit


def nearest(value):
    """value correctly rounded to Extended (round half to even), and the
    size of one unit in the last place there."""
    exponent = value.numerator.bit_length() - value.denominator.bit_length()
    while Fraction(2) ** exponent > value:
        exponent -= 1
    while Fraction(2) ** (exponent + 1) <= value:
        exponent += 1
    unit = Fraction(2) ** (exponent - 63)
    scaled = value / unit
    low = scaled.numerator // scaled.denominator
    rest = scaled - low
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and low % 2):
        low += 1
    return low * unit, unit


def check_real_values(case):
    """The rules spec/lexer.md states under "Real values"."""
    parsed = literal(case.source.decode("latin-1"))
    if parsed is None:
        return ["no 'const C = <real>;' to check"]
    n, k = parsed
    value = n * Fraction(10) ** k
    verdict, output = case.fields.get("tpc", ""), case.fields.get("output", "").strip("'")
    if value >= OVERFLOW:
        return [] if verdict.startswith("error 6 ") else ["at or above the overflow edge but not error 6"]
    if verdict != "ok":
        return [f"within the Extended range but {verdict}"]
    got, got_unit = extended(output)
    if value < EXTENDED_MIN_NORMAL:
        return [] if got == 0 else ["below the smallest normal value but not 0"]
    if got == 0:
        return ["0, but not below the smallest normal value"]
    expected, unit = nearest(value)
    off = (got - expected) / unit
    low, high = (0, 0) if 0 <= k <= 27 else (-1, 1) if k > 27 else (-10, 2)
    if not low <= off <= high:
        return [f"{off} units off correct rounding with k = {k}; lexer.md allows {low} to {high}"]
    return []


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    problems = []
    found = cases.find(root)
    for case in found:
        problems += [(case.path, p) for p in check(case)]
        if os.path.basename(os.path.dirname(case.path)) == "13-real-values":
            problems += [(case.path, p) for p in check_real_values(case)]
    problems += check_citations(os.path.join(root, "lexer.md"), found)
    for where, problem in problems:
        print(f"{os.path.relpath(where, root) if os.path.isabs(where) else where}: {problem}")
    print(f"{len(found)} cases, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
