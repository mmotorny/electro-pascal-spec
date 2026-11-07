"""Checks that every case file is well formed, without running TPC.

Every case must have a description, a token list that uses only the
notation of spec/lexer.md, and a recorded verdict (run `bazel run
//spec:record` after adding or changing a case).
"""

import os
import re
import sys

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


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)))
    failed = 0
    found = cases.find(root)
    for case in found:
        for problem in check(case):
            print(f"{os.path.relpath(case.path, root)}: {problem}")
            failed += 1
    print(f"{len(found)} cases, {failed} problems")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
