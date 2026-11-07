"""Decodes a Borland DOS IDE help file (.TPH) into plain text.

Format, as read from the files themselves:

  "TURBO PASCAL HELP FILE.\\0", 0x1A, "$*$* &&&&$*$", 0x00, version (word)
  then records until the end of the file: type (byte), length (word), data.

  0  header: options, main topic, maximum topic size (words), height, width,
     left margin (bytes)
  1  contexts: count (word), then a 24-bit file offset of a text record for
     each context number (0xFFFFFF for none)
  2  topic text, compressed (see below)
  3  links of the preceding topic: previous and next topic (words), count
     (word), then the context number of each link, in order
  4  index: count (word), then entries of: a byte whose top 3 bits say how
     many leading characters to keep from the previous name and whose low 5
     bits say how many new characters follow, those characters, and a
     context number (word)
  5  compression: type (byte, 2), then 14 characters
  6  index tags (not needed here)

Topic text is a stream of 4-bit codes, low half of each byte first:
  0-13  the character at that position in the compression table
  14    a run: a count n, then one character (in either form below),
        repeated n + 2 times
  15    a literal byte: two codes, low half first

Decoded text uses 0x00 for line ends, 0x01 to end the topic, 0x02 to start
and end a link, 0x05 to start a code sample. Other bytes are code page 437.
"""

import argparse
import struct

SIGNATURE = b"$*$* &&&&$*$"


def records(data):
    pos = data.index(SIGNATURE) + len(SIGNATURE) + 1 + 2
    while pos < len(data):
        kind, length = data[pos], struct.unpack_from("<H", data, pos + 1)[0]
        yield kind, pos, data[pos + 3:pos + 3 + length]
        pos += 3 + length
    if pos != len(data):
        raise ValueError("records overrun the end of the file")


def decompress(data, table):
    codes = []
    for byte in data:
        codes += (byte & 15, byte >> 4)
    out = bytearray()
    i = 0

    def char():
        nonlocal i
        code = codes[i]
        i += 1
        if code == 15:
            value = codes[i] | codes[i + 1] << 4
            i += 2
            return value
        return table[code]

    while i < len(codes):
        if codes[i] == 14:
            count = codes[i + 1]
            i += 2
            out += bytes([char()]) * (count + 2)
        else:
            out.append(char())
        if out and out[-1] == 1:  # End of topic; the rest is padding.
            break
    return bytes(out)


def render(text):
    """Turns decoded topic bytes into readable text, with links as «...»."""
    text = text.rstrip(b"\x01")
    out = []
    link_open = False
    for byte in text:
        if byte == 0:
            out.append("\n")
        elif byte == 2:
            out.append("»" if link_open else "«")
            link_open = not link_open
        elif byte == 5:
            pass  # Start of a code sample; the text already shows it.
        else:
            out.append(bytes([byte]).decode("cp437"))
    return "".join(out).strip("\n")


def decode(data):
    table = None
    offsets = []
    index = []
    topics = []  # (file offset of the text record, text)
    for kind, pos, body in records(data):
        if kind == 5:
            table = body[1:]
        elif kind == 1:
            count = struct.unpack_from("<H", body)[0]
            offsets = [int.from_bytes(body[2 + 3 * i:5 + 3 * i], "little") for i in range(count)]
        elif kind == 4:
            count = struct.unpack_from("<H", body)[0]
            p, previous = 2, b""
            for _ in range(count):
                keep, new = body[p] >> 5, body[p] & 31
                name = previous[:keep] + body[p + 1:p + 1 + new]
                p += 1 + new
                index.append((name.decode("cp437"), struct.unpack_from("<H", body, p)[0]))
                p += 2
                previous = name
        elif kind == 2:
            topics.append((pos, render(decompress(body, table))))

    names = {}
    for name, context in index:
        if context < len(offsets):
            names.setdefault(offsets[context], []).append(name)
    return [(names.get(pos, []), text) for pos, text in topics]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tph")
    parser.add_argument("out")
    args = parser.parse_args()
    with open(args.tph, "rb") as f:
        topics = decode(f.read())
    with open(args.out, "w", encoding="utf-8") as f:
        for number, (names, text) in enumerate(topics, 1):
            f.write(f"==== Topic {number}: {', '.join(names) or '(no index entry)'}\n\n{text}\n\n")


if __name__ == "__main__":
    main()
