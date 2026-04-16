"""Tiny indented line buffer. Nothing fancy."""

from __future__ import annotations


class CodeBuilder:
    INDENT = "    "

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0

    def line(self, text: str = "") -> None:
        if text:
            self._lines.append(self.INDENT * self._indent + text)
        else:
            self._lines.append("")

    def extend(self, lines: list[str]) -> None:
        for ln in lines:
            self.line(ln)

    def indent(self) -> None:
        self._indent += 1

    def dedent(self) -> None:
        if self._indent > 0:
            self._indent -= 1

    def render(self) -> str:
        return "\n".join(self._lines) + "\n"
