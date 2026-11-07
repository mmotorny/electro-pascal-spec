"""Checks that the reference lexer agrees with every lexer case."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cases  # noqa: E402
import reference  # noqa: E402


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases")
    problems = 0
    found = cases.find(root)
    for case in found:
        tokens, error = reference.lex(case.source)
        problem = reference.check(tokens, error, case.tokens(), case.fields.get("tpc", ""))
        if problem:
            problems += 1
            print(f"{os.path.relpath(case.path, root)}: {problem}")
    print(f"{len(found)} cases, {problems} disagree with the reference lexer")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
