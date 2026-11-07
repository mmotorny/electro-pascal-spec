"""Reads and writes spec test cases (*.case).

A case file is a header, a line holding only "---", and the source:

    # Free text describing what the case shows.
    tokens: PROGRAM IDENT(P) SEMI BEGIN END DOT
    tpc: ok
    ---
    program P; begin end.

The source is everything after the "---" line, byte for byte (the files are
marked binary in .gitattributes so git never changes them).

Header fields:
  tokens  the tokens the spec says TPC's scanner delivers, up to the end of
          the file or the error, in the notation of spec/lexer.md. May
          continue on following lines that start with whitespace.
  tpc     TPC's verdict, written only by `bazel run //spec:record`:
          "ok", or "error N at LINE:COLUMN" (1-based).
  output  What the compiled program writes when run, also written only by
          the record tool, in the string notation of spec/lexer.md.
          Present only when the program compiles.
"""

import os

SEPARATOR = b"\n---\n"


class Case:
    def __init__(self, path):
        self.path = path
        with open(path, "rb") as f:
            data = f.read()
        head, sep, self.source = data.partition(SEPARATOR)
        if not sep:
            raise ValueError(f"{path}: no '---' line")
        self.comments = []
        self.fields = {}
        last = None
        for line in head.decode("utf-8").split("\n"):
            if line.startswith("#"):
                self.comments.append(line)
            elif line[:1].isspace() and last:
                self.fields[last] += " " + line.strip()
            elif line.strip():
                key, _, value = line.partition(":")
                last = key.strip()
                self.fields[last] = value.strip()

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    def tokens(self):
        return split_tokens(self.fields.get("tokens", ""))

    def save(self):
        lines = list(self.comments)
        for key in ("tokens", "tpc", "output"):
            if key in self.fields:
                lines.append(f"{key}: {self.fields[key]}")
        for key, value in self.fields.items():
            if key not in ("tokens", "tpc", "output"):
                lines.append(f"{key}: {value}")
        with open(self.path, "wb") as f:
            f.write("\n".join(lines).encode("utf-8") + SEPARATOR + self.source)


def split_tokens(text):
    """Splits a token list, keeping each NAME(...) value whole, quotes included."""
    tokens, i = [], 0
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        j = i
        while j < len(text) and not text[j].isspace() and text[j] != "(":
            j += 1
        if j < len(text) and text[j] == "(":
            depth, quoted = 0, False
            while j < len(text):
                c = text[j]
                if c == "'":
                    quoted = not quoted
                elif not quoted and c == "(":
                    depth += 1
                elif not quoted and c == ")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                j += 1
        tokens.append(text[i:j])
        i = j
    return tokens


def find(root):
    """All cases under a directory, in file name order."""
    paths = []
    for dirpath, _, files in os.walk(root):
        paths += [os.path.join(dirpath, f) for f in files if f.endswith(".case")]
    return [Case(p) for p in sorted(paths)]


def verdict_text(result):
    if result["verdict"] == "ok":
        return "ok"
    if result["verdict"] == "error":
        where = f" at {result['line']}:{result['column']}" if result["line"] else ""
        return f"error {result['code']}{where}"
    return result["verdict"]


def pascal_string(data):
    """Bytes in the spec's string notation: 'quoted' runs and #n for others."""
    if not data:
        return "''"
    out, quoted = [], False
    for byte in data:
        if 32 <= byte < 127:
            if not quoted:
                out.append("'")
                quoted = True
            out.append("''" if byte == 39 else chr(byte))
        else:
            if quoted:
                out.append("'")
                quoted = False
            out.append(f"#{byte}")
    if quoted:
        out.append("'")
    return "".join(out)
