"""Minimal S-expression reader/writer for KiCad files.

KiCad stores symbols, footprints, schematics and boards as S-expressions.
The parser keeps quoted strings and bare atoms apart so that a file can be
read, modified and written back without changing its meaning:

    parse(text)  -> nested python lists; bare atoms are ``Sym`` (a ``str``
                    subclass), quoted strings are plain ``str``
    dumps(node)  -> text, re-quoting whatever was quoted on the way in
"""

from __future__ import annotations


class Sym(str):
    """A bare (unquoted) atom: keywords, numbers, ``yes``/``no``."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Sym({str.__repr__(self)})"


_WS = " \t\r\n"


def parse(text: str):
    """Parse the first S-expression found in *text*."""
    node, _ = _parse_at(text, _skip(text, 0))
    return node


def _skip(text: str, i: int) -> int:
    while i < len(text):
        c = text[i]
        if c in _WS:
            i += 1
        elif c == "#":  # not KiCad syntax, but harmless to tolerate
            while i < len(text) and text[i] != "\n":
                i += 1
        else:
            break
    return i


def _parse_at(text: str, i: int):
    if text[i] != "(":
        raise ValueError(f"expected '(' at offset {i}, found {text[i]!r}")
    i += 1
    out = []
    while True:
        i = _skip(text, i)
        if i >= len(text):
            raise ValueError("unexpected end of input")
        c = text[i]
        if c == ")":
            return out, i + 1
        if c == "(":
            child, i = _parse_at(text, i)
            out.append(child)
        elif c == '"':
            value, i = _parse_string(text, i)
            out.append(value)
        else:
            j = i
            while j < len(text) and text[j] not in _WS and text[j] not in "()":
                j += 1
            out.append(Sym(text[i:j]))
            i = j


def _parse_string(text: str, i: int):
    i += 1  # opening quote
    buf = []
    while True:
        c = text[i]
        if c == "\\":
            nxt = text[i + 1]
            buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(nxt, nxt))
            i += 2
        elif c == '"':
            return "".join(buf), i + 1
        else:
            buf.append(c)
            i += 1


def quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def atom(value) -> str:
    if isinstance(value, Sym):
        return str(value)
    if isinstance(value, str):
        return quote(value)
    raise TypeError(f"unsupported atom: {value!r}")


def _inline(node) -> str:
    if not isinstance(node, list):
        return atom(node)
    return "(" + " ".join(_inline(child) for child in node) + ")"


def dumps(node, indent: int = 0, width: int = 96) -> str:
    """Render *node*, keeping short sub-trees on a single line."""
    pad = "\t" * indent
    if not isinstance(node, list):
        return pad + atom(node)
    flat = _inline(node)
    if len(flat) + len(pad) <= width:
        return pad + flat
    if not node:
        return pad + "()"
    head = node[0]
    lines = [pad + "(" + (atom(head) if not isinstance(head, list) else "")]
    rest = node if isinstance(head, list) else node[1:]
    # keep leading atoms on the head line, e.g. (property "Reference" "AE1"
    start = 0
    if not isinstance(head, list):
        while start < len(rest) and not isinstance(rest[start], list):
            lines[0] += " " + atom(rest[start])
            start += 1
    for child in rest[start:]:
        lines.append(dumps(child, indent + 1, width))
    lines.append(pad + ")")
    return "\n".join(lines)


def num(value, digits: int = 6) -> Sym:
    """Format a number the way KiCad does: no exponent, no trailing zeros."""
    text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    return Sym("0" if text in ("", "-0") else text)


def find(node, key: str):
    """First direct child list whose head is *key*."""
    for child in node:
        if isinstance(child, list) and child and child[0] == key:
            return child
    return None


def find_all(node, key: str):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]
