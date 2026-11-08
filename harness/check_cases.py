"""Checks the cases and how spec/lexer.md cites them, without running TPC.

Every case must match spec/case.schema.yaml and have a recorded verdict
(run `bazel run //harness:record` after adding or changing a case).

Every link from spec/lexer.md or spec/lexer-limits.md into lexer/cases/
must name an existing case, or, for a link to a folder, have text that is
a pattern matching at least one case in it; and every case must be cited
by some link.

Every case in 13-real-values must have the value that the arithmetic in
spec/lexer.md ("Real values") gives (see check_real_values).
"""

import fnmatch
import os
import re
import sys
from fractions import Fraction

import jsonschema
import yaml

import cases

# The spec files whose links cite the cases.
SPEC_FILES = ["lexer.md", "lexer-limits.md"]


def schema_checker(root):
    with open(os.path.join(root, "case.schema.yaml")) as f:
        schema = yaml.safe_load(f)
    return jsonschema.Draft202012Validator(schema)


def check(case, checker):
    """Problems with one case's form: the schema, and a recorded verdict."""
    problems = [f"{'/'.join(map(str, e.absolute_path)) or 'case'}: {e.message}"
                for e in checker.iter_errors(case.data)]
    if case.data.get("compile") is None:
        problems.append("no recorded verdict; run bazel run //harness:record")
    return problems


def check_citations(spec_paths, found):
    """Problems with the spec files' links to cases, as (where, problem) pairs."""
    cited, problems = set(), []
    for spec_path in spec_paths:
        spec_dir, name = os.path.dirname(spec_path), os.path.basename(spec_path)
        with open(spec_path, encoding="utf-8") as f:
            text = f.read()
        for label, target in re.findall(r"\[([^\]]+)\]\((lexer/cases/[^)]*)\)", text):
            path = os.path.normpath(os.path.join(spec_dir, target))
            if target.endswith(cases.EXTENSION):
                if os.path.isfile(path):
                    cited.add(path)
                else:
                    problems.append((name, f"link to missing case {target}"))
            elif any(c in label for c in "*?["):
                matches = [c.path for c in found
                           if os.path.dirname(c.path) == path and fnmatch.fnmatch(c.name, label)]
                if matches:
                    cited.update(matches)
                else:
                    problems.append((name, f"pattern {label} matches no case in {target}"))
            elif target.rstrip("/") != "lexer/cases":
                problems.append((name, f"link to {target} should name a case or a pattern"))
    names = " or ".join(os.path.basename(p) for p in spec_paths)
    for case in found:
        if case.path not in cited:
            problems.append((case.path, f"not cited in {names}"))
    return problems


# The arithmetic that spec/lexer.md gives under "Real values". An Extended
# value is ZERO, INFINITE, NAN, or a pair (m, e) for m * 2**(e - 63).
ZERO, INFINITE, NAN = "zero", "infinite", "nan"
BETA = 1 << 16
DIGIT_LIMIT = 922112023704109056
LITERAL = re.compile(r"const C = (\d*)(?:\.(\d*))?(?:[eE]([+-]?\d*))?;")


def words(x):
    return [(x >> (16 * i)) & 0xFFFF for i in range(4)]


def finish(m, e):
    """A result (m, e), or what it becomes outside the normal range."""
    if e > 16383:
        return INFINITE
    return ZERO if e < -16382 else (m, e)


def multiply(x, y):
    if NAN in (x, y) or {x, y} == {ZERO, INFINITE}:
        return NAN
    if INFINITE in (x, y):
        return INFINITE
    if ZERO in (x, y):
        return ZERO
    (a, ea), (b, eb) = x, y
    aw, bw = words(a), words(b)
    total = sum(aw[i] * bw[j] * BETA ** (i + j)
                for i in range(4) for j in range(4) if i + j >= 2 and (i, j) != (1, 1))
    c = 0
    if bw[1] >= 1 << 15:
        c += aw[1] * BETA + aw[0]
    if aw[1] >= 1 << 15:
        c += bw[1] * BETA + bw[0]
    if bw[1] >= 1 << 15 and aw[1] >= 1 << 15:
        c -= BETA ** 2
    s = (total + c * BETA ** 2) // BETA ** 3
    if s < 1 << 79:
        s, e = 2 * s, ea + eb
    else:
        e = ea + eb + 1
    m = s // BETA + (s >> 15 & 1)
    if m == 1 << 64:
        m, e = 1 << 63, e + 1
    return finish(m, e)


def rounded_divisor(b):
    bw = words(b)
    return bw[3] + (1 if bw[2] >= 1 << 15 else 0)


def divide(x, y):
    if NAN in (x, y) or x == y == INFINITE or y == ZERO:
        raise ValueError("lexer.md doesn't define this division")
    if x == ZERO or y == INFINITE:
        return ZERO
    if x == INFINITE:
        return INFINITE
    (a, ea), (b, eb) = x, y
    aw, bw = words(a), words(b)
    c = 1 if aw[3] >= bw[3] else 0
    t = c * BETA + ((aw[3] - c * bw[3]) * BETA + aw[2]) // bw[3] + 1
    r1 = t * b - a * BETA
    if r1 < 0:
        raise ValueError("lexer.md says R1 is never negative")
    d1 = r1 // BETA ** 2 // bw[3] + 1
    r2 = (d1 * b // BETA - r1) % BETA ** 4
    d2 = r2 // BETA // bw[3] + 1
    r3 = (d2 * (b // BETA) // BETA - r2) % BETA ** 3
    d = rounded_divisor(b)
    if d >= BETA:
        raise ValueError("lexer.md says d is below 2^16 here")
    v = 2 * r3 % BETA ** 3
    f = v // d * 2 ** 7 + v % d // 2 ** 9
    big = (t * BETA ** 2 - d1 * BETA + d2) * 2 ** 24 - f
    if big >= 1 << 72:
        big, e = big // 2, ea - eb
    else:
        e = ea - eb - 1
    m = big // 2 ** 8 + (big >> 7 & 1)
    if m == 1 << 64:
        m, e = 1 << 63, e + 1
    return finish(m, e)


def nearest(value):
    """The Extended value nearest to a positive Fraction."""
    e = value.numerator.bit_length() - value.denominator.bit_length()
    while Fraction(2) ** e > value:
        e -= 1
    while Fraction(2) ** (e + 1) <= value:
        e += 1
    scaled = value / Fraction(2) ** (e - 63)
    m = scaled.numerator // scaled.denominator
    if scaled - m >= Fraction(1, 2):  # never exactly half for these values
        m += 1
    return (m >> 1, e + 1) if m == 1 << 64 else (m, e)


TABLE = [nearest(Fraction(10) ** (8 << i)) for i in range(10)]


def power_of_ten(n):
    n = min(n, 4999)
    p = from_integer(10 ** (n % 8))
    for i in range(10):
        if (n // 8) >> i & 1:
            p = multiply(p, TABLE[i])
    return p


def from_integer(n):
    if n == 0:
        return ZERO
    e = n.bit_length() - 1
    return n << (63 - e), e


def literal(source):
    """(N, k) for the case's real literal, as lexer.md defines them."""
    match = LITERAL.search(source)
    if not match:
        return None
    whole, fraction, exponent = match[1] or "", match[2] or "", match[3] or ""
    n = k = 0
    for part, digits in (("whole", whole), ("fraction", fraction)):
        for digit in digits:
            if n >= DIGIT_LIMIT:
                k += part == "whole"
            else:
                n = 10 * n + int(digit)
                k -= part == "fraction"
    k += int(exponent) if exponent.strip("+-") else 0
    return n, k


def value(n, k):
    x = from_integer(n)
    if k >= 0:
        return multiply(x, power_of_ten(k))
    if k >= -4096:
        return divide(x, power_of_ten(-k))
    return divide(divide(x, power_of_ten(4096)), power_of_ten(-k - 4096))


def hex_of(x):
    """The value as the cases print it: 10 bytes in hex, most significant first."""
    if x == ZERO:
        return "0" * 20
    m, e = x
    return f"{e + 16383:04X}{m:016X}"


def check_powers_of_ten():
    """The facts lexer.md states about T(i) and P(n)."""
    problems = []
    if any(rounded_divisor(m) >= BETA for m, _ in TABLE):
        problems.append("some T(i) has d = 2^16")
    for n in range(1, 10000):
        p = power_of_ten(n)
        if (p == INFINITE) != (n >= 4933):
            problems.append(f"P({n}) is {'' if p == INFINITE else 'not '}infinite")
        elif p != INFINITE and rounded_divisor(p[0]) >= BETA:
            problems.append(f"P({n}) has d = 2^16")
    return problems


def check_real_values(case):
    """The case's recorded result must be the value lexer.md computes."""
    parsed = literal(case.source.decode("latin-1"))
    if parsed is None:
        return ["no 'const C = <real>;' to check"]
    result = value(*parsed)
    tpc = case.compile
    if result in (INFINITE, NAN):
        return [] if tpc != "ok" and tpc.get("error") == 6 else [f"lexer.md gives error 6, TPC {cases.verdict_text(tpc)}"]
    if tpc != "ok":
        return [f"lexer.md gives {hex_of(result)}, TPC {cases.verdict_text(tpc)}"]
    output = case.data.get("output", "")
    return [] if output == hex_of(result) else [f"lexer.md gives {hex_of(result)}, TPC {output}"]


def main():
    root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spec")
    problems = []
    found = cases.find(root)
    checker = schema_checker(root)
    for case in found:
        problems += [(case.path, p) for p in check(case, checker)]
        if os.path.basename(os.path.dirname(case.path)) == "13-real-values":
            problems += [(case.path, p) for p in check_real_values(case)]
    problems += [("lexer.md", p) for p in check_powers_of_ten()]
    problems += check_citations([os.path.join(root, f) for f in SPEC_FILES], found)
    for where, problem in problems:
        print(f"{os.path.relpath(where, root) if os.path.isabs(where) else where}: {problem}")
    print(f"{len(found)} cases, {len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
