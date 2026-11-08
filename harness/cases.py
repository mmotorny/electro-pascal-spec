"""Reads and writes spec test cases (*.yaml).

A case is a YAML file holding one mapping (see spec/case.schema.yaml):

    description: Thirty leading zeros don't overflow.
    source: |
      program P;
      const C = 0000000000000000000000000000007;
      begin
        Write(C)
      end.
    tokens:
      - PROGRAM
      - IDENT: P
      ...
    compile: ok
    output: "7"

  description  what the input is and what it shows.
  options      optional: options for TPC's command line, such as /M or
               /DNAME, given before the program's name.
  source       the program, byte for byte. Each character of the string is
               one byte, U+0000 to U+00FF.
  files        optional: more files beside the program, such as include
               files, as a mapping from DOS file names (upper case, 8.3) to
               their contents, byte for byte like source.
  precompile   optional: names of some of those files, which TPC compiles,
               in that order and with no options, before the program; for
               units that the program needs compiled already.
  tokens       the tokens the spec says TPC's scanner delivers, up to the
               end of the program or the error: a kind alone, or a mapping
               from a kind to its value.
  compile      what compiling the source with TPC gives, written only by
               `bazel run //harness:record`:
               "ok"; "hang" when TPC never finishes compiling it; or a
               mapping with "error" (the error number), "line" and "column"
               (1-based) when TPC gives a position, "file" when the error is
               in one of the files rather than the program, and "message",
               TPC's error message.
  output       what the compiled program writes, also written only by the
               record tool; present only when the program compiles. One
               character per byte, like source.

Reading uses any YAML parser. Writing uses the emitter below, so that every
case has the same layout: plain scalars where YAML reads them back as the
same string, double-quoted ones with escapes otherwise, and the source as a
literal block when it is plain text. Every file written is read back and
must give the same data.
"""

import os
import re

import yaml

EXTENSION = ".yaml"
FIELDS = ("description", "options", "source", "files", "precompile", "tokens", "compile", "output")
VERDICT_FIELDS = ("error", "line", "column", "file", "message")
WIDTH = 76


class Case:
    def __init__(self, path, data=None):
        self.path = path
        if data is None:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        self.data = data

    @property
    def name(self):
        return os.path.splitext(os.path.basename(self.path))[0]

    @property
    def description(self):
        return self.data.get("description", "")

    @property
    def source(self):
        """The program as bytes."""
        return self.data["source"].encode("latin-1")

    @source.setter
    def source(self, value):
        self.data["source"] = value.decode("latin-1")

    @property
    def tokens(self):
        """The token list as (kind, value) pairs, value None for a bare kind."""
        return token_pairs(self.data.get("tokens") or [])

    @tokens.setter
    def tokens(self, pairs):
        self.data["tokens"] = [kind if value is None else {kind: value} for kind, value in pairs]

    @property
    def compile(self):
        return self.data.get("compile")

    @property
    def files(self):
        """The extra files as {name: bytes}."""
        return {k: v.encode("latin-1") for k, v in (self.data.get("files") or {}).items()}

    @property
    def options(self):
        return list(self.data.get("options") or [])

    @property
    def precompile(self):
        return list(self.data.get("precompile") or [])

    @property
    def input(self):
        """What to give machine/probe.py and machine/tokens.py: the source, or
        (source, files, options, precompile) when the case has files or
        options."""
        if self.files or self.options:
            return (self.source, self.files, self.options, self.precompile)
        return self.source

    @property
    def output(self):
        """What the program wrote, as bytes, or None."""
        value = self.data.get("output")
        return None if value is None else value.encode("latin-1")

    def save(self):
        text = dump(self.data)
        with open(self.path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)


def find(root):
    """All cases under a directory, in path order: the YAML files inside a
    folder named "cases"."""
    paths = []
    for dirpath, _, files in os.walk(root):
        inside = "cases" in os.path.abspath(dirpath).split(os.sep)
        paths += [os.path.join(dirpath, f) for f in files if inside and f.endswith(EXTENSION)]
    return [Case(p) for p in sorted(paths)]


def token_pairs(tokens):
    """A token list as (kind, value) pairs, value None for a bare kind."""
    return [next(iter(t.items())) if isinstance(t, dict) else (t, None) for t in tokens]


def verdict(result):
    """A probe result (see machine/probe.py) as a case's compile value."""
    if result["verdict"] in ("ok", "hang"):
        return result["verdict"]
    if result["verdict"] == "error":
        out = {"error": result["code"]}
        if result["line"]:
            out.update(line=result["line"], column=result["column"])
        if result.get("file"):
            out["file"] = result["file"]
        out["message"] = result["message"]
        return out
    raise ValueError(f"TPC's verdict is {result['verdict']!r}")


def verdict_text(value):
    """A compile value (or a probe result) in one short line, for messages."""
    if isinstance(value, dict) and "verdict" in value:
        if value["verdict"] not in ("ok", "error"):
            return value["verdict"]
        value = verdict(value)
    if value in ("ok", "hang"):
        return value
    where = f" at {value['line']}:{value['column']}" if "line" in value else ""
    if "file" in value:
        where += f" in {value['file']}"
    return f"error {value['error']}{where}"


def token_text(kind, value):
    """One token in one short line, for messages."""
    return kind if value is None else f"{kind}: {scalar(value)}"


# --- Emitter -----------------------------------------------------------------

# What YAML 1.2 core reads as something other than a string. PyYAML follows
# YAML 1.1, which is checked separately by reading the scalar back.
NOT_STRING_12 = re.compile(
    r"true|True|TRUE|false|False|FALSE|null|Null|NULL|~"
    r"|[-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+"
    r"|[-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?"
    r"|[-+]?\.(inf|Inf|INF)|\.nan|\.NaN|\.NAN"
)
ESCAPES = {0: "\\0", 9: "\\t", 10: "\\n", 13: "\\r", 34: '\\"', 92: "\\\\"}


def plain_ok(text):
    """Whether text can be written as a plain scalar and read back as itself."""
    if not text or text != text.strip() or not all(" " <= c <= "~" for c in text):
        return False
    if text[0] in "-?:,[]{}#&*!|>'\"%@`" or ": " in text or " #" in text or text.endswith(":"):
        return False
    if NOT_STRING_12.fullmatch(text):
        return False
    try:
        return yaml.safe_load("x: " + text) == {"x": text}
    except yaml.YAMLError:  # Such as "=", which PyYAML reads as a special tag.
        return False


def quoted(text):
    out = []
    for c in text:
        code = ord(c)
        if code in ESCAPES:
            out.append(ESCAPES[code])
        elif code < 32 or code >= 127:
            out.append(f"\\x{code:02x}")
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def scalar(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"can't write {value!r}")
    if isinstance(value, int):
        return str(value)
    return value if plain_ok(value) else quoted(value)


def folded(key, text):
    """key: text, as a plain scalar wrapped at WIDTH, or quoted on one line."""
    if not plain_ok(text):
        return [f"{key}: {quoted(text)}"]
    lines, line = [], f"{key}:"
    for word in text.split(" "):
        if line != f"{key}:" and len(line) + 1 + len(word) > WIDTH and not word.startswith("#"):
            lines.append(line)
            line = "  " + word
        else:
            line += " " + word
    lines.append(line)
    return lines


def block_ok(text):
    """Whether text can be a literal block scalar, read back exactly."""
    if not text.strip("\n") or not all(c in "\t\n" or " " <= c <= "~" for c in text):
        return False
    lines = text.split("\n")
    if lines[0][:1] in (" ", "\t"):
        return False
    return all(line == line.rstrip(" \t") for line in lines)


def block(key, text, indent=""):
    if text.endswith("\n\n"):
        indicator, body = "|+", text[:-1]
    elif text.endswith("\n"):
        indicator, body = "|", text[:-1]
    else:
        indicator, body = "|-", text
    inner = indent + "  "
    return [f"{indent}{key}: {indicator}"] + [(inner + line) if line else "" for line in body.split("\n")]


def text_value(key, text, indent=""):
    """key: text, as a literal block when it's plain text, else quoted."""
    return block(key, text, indent) if block_ok(text) else [f"{indent}{key}: {quoted(text)}"]


def dump(data):
    """The case's YAML text. Raises if it wouldn't read back as data."""
    unknown = set(data) - set(FIELDS)
    if unknown:
        raise ValueError(f"unknown fields {sorted(unknown)}")
    lines = []
    for key in FIELDS:
        if key not in data:
            continue
        value = data[key]
        if key == "description":
            lines += folded(key, value)
        elif key == "source":
            lines += text_value(key, value)
        elif key == "options":
            lines.append("options:")
            lines += [f"  - {scalar(o)}" for o in value]
        elif key == "precompile":
            lines.append("precompile:")
            lines += [f"  - {scalar(o)}" for o in value]
        elif key == "files":
            lines.append("files:")
            for name, text in value.items():
                if not plain_ok(name):
                    raise ValueError(f"bad file name {name!r}")
                lines += text_value(name, text, "  ")
        elif key == "tokens":
            lines.append("tokens:" if value else "tokens: []")
            for token in value:
                if isinstance(token, dict):
                    ((kind, v),) = token.items()
                    lines.append(f"  - {kind}: {scalar(v)}")
                else:
                    if not plain_ok(token):
                        raise ValueError(f"bad token kind {token!r}")
                    lines.append(f"  - {token}")
        elif key == "compile":
            if value in ("ok", "hang"):
                lines.append(f"compile: {value}")
            else:
                lines.append("compile:")
                lines += [f"  {k}: {scalar(value[k])}" for k in VERDICT_FIELDS if k in value]
        else:
            lines.append(f"{key}: {scalar(value)}")
    text = "\n".join(lines) + "\n"
    if yaml.safe_load(text) != data:
        raise ValueError("emitted YAML doesn't read back the same:\n" + text)
    return text
