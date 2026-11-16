"""Human-readable CLI output: tables, in plain ASCII or (optionally) with Rich.

Two renderers draw the same :class:`Table`:

``plain``
    Standard library only, ASCII borders. Used when output is piped or
    redirected, when ``NO_COLOR`` is set, with ``--color never``, or when Rich is
    not installed. It is the stable look: the same text on every console and
    code page, so a script or an AI tool can read it.
``rich``
    Colours, rounded borders and wrapping to the window, via the optional
    ``rich`` package. Used only on a real terminal (or ``--color always``).
    ``rich`` is imported at that point and never before, so ``--help`` and the
    other fast paths do not pay for it.

``--json`` never reaches this module; it prints data, not a picture of it.

Choosing the renderer, first match wins: ``--color never`` / ``always``; the
``TRIGGER_DESIGNER_COLOR`` variable (``never`` / ``always``); ``NO_COLOR``
set -> plain; output is not a terminal, or ``TERM=dumb`` -> plain; ``rich`` not
installed -> plain; otherwise rich.
"""

from __future__ import annotations

import os
import shutil
import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any, TextIO

PLAIN = "plain"
RICH = "rich"
COLOR_MODES = ("auto", "always", "never")
ENV_COLOR = "TRIGGER_DESIGNER_COLOR"

#: Wrapped columns are never squeezed narrower than this.
MIN_WRAP_WIDTH = 16
#: Width used when it cannot be asked of a terminal (a pipe, a test).
DEFAULT_WIDTH = 120

_color_override: str | None = None


def set_color(mode: str | None) -> None:
    """Set from ``--color``; ``None`` or ``auto`` leaves it to the environment."""
    global _color_override
    if mode not in (None, *COLOR_MODES):
        raise ValueError(f"color must be one of {COLOR_MODES}, not {mode!r}")
    _color_override = None if mode in (None, "auto") else mode


def rich_available() -> bool:
    import importlib.util

    return importlib.util.find_spec("rich") is not None


def _wanted() -> str:
    """``never`` / ``always`` from ``--color`` or the environment, else ``""``."""
    return _color_override or os.environ.get(ENV_COLOR, "").strip().lower()


def resolve_mode(stream: TextIO | None = None) -> str:
    """``plain`` or ``rich`` for ``stream`` (see the module docstring)."""
    stream = stream or sys.stdout
    wanted = _wanted()
    if wanted == "never":
        return PLAIN
    if wanted == "always":
        return RICH if rich_available() else PLAIN
    if os.environ.get("NO_COLOR"):
        return PLAIN
    isatty = getattr(stream, "isatty", None)
    if not (callable(isatty) and isatty()) or os.environ.get("TERM") == "dumb":
        return PLAIN
    return RICH if rich_available() else PLAIN


def terminal_width() -> int:
    return shutil.get_terminal_size((DEFAULT_WIDTH, 24)).columns


# ------------------------------------------------------------------ values
def fmt(value: Any) -> str:
    """A cell as text: ``None`` is empty, integers get thousands separators,
    floats at most four decimals, booleans ``true`` / ``false``."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        text = f"{value:,.4f}".rstrip("0").rstrip(".")
        return text if text not in ("-0", "") else "0"
    return str(value)


def _cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return " ".join(text.split("\n")).replace("\r", "").replace("\t", " ")


@dataclass
class Table:
    """What to draw. ``right`` right-aligns numbers; ``wrap`` names the columns
    that may be folded onto several lines (the others stay on one line);
    ``max_cell`` shortens a longer cell in the other columns with ``...``."""

    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    right: tuple[str, ...] = ()
    wrap: tuple[str, ...] = ()
    title: str = ""
    max_cell: int = 0

    def cells(self) -> list[list[str]]:
        out = []
        for row in self.rows:
            cells = []
            for name, value in zip(self.columns, row, strict=False):
                text = _cell(value)
                if (
                    self.max_cell
                    and name not in self.wrap
                    and len(text) > self.max_cell
                ):
                    text = text[: self.max_cell - 3] + "..."
                cells.append(text)
            cells += [""] * (len(self.columns) - len(cells))
            out.append(cells)
        return out


# ------------------------------------------------------------------- plain
def render_plain(table: Table, width: int = DEFAULT_WIDTH) -> str:
    """The table as ASCII text (no trailing newline)."""
    columns = table.columns
    cells = table.cells()
    widths = [
        max([len(name), *(len(row[i]) for row in cells)])
        for i, name in enumerate(columns)
    ]
    wrappable = [i for i, name in enumerate(columns) if name in table.wrap]
    overhead = 3 * len(columns) + 1
    while wrappable and sum(widths) + overhead > width:
        widest = max(wrappable, key=lambda j: widths[j])
        cut = min(sum(widths) + overhead - width, widths[widest] - MIN_WRAP_WIDTH)
        if cut <= 0:
            break
        widths[widest] -= cut

    rule = "+" + "+".join("-" * (w + 2) for w in widths) + "+"

    def physical(values: list[str]) -> list[str]:
        folded = [
            (textwrap.wrap(v, widths[i], break_long_words=True) or [""])
            if columns[i] in table.wrap
            else [v]
            for i, v in enumerate(values)
        ]
        height = max((len(lines) for lines in folded), default=1)
        lines = []
        for n in range(height):
            parts = []
            for i, col in enumerate(folded):
                text = col[n] if n < len(col) else ""
                align = ">" if columns[i] in table.right else "<"
                parts.append(f" {text:{align}{widths[i]}} ")
            lines.append("|" + "|".join(parts) + "|")
        return lines

    out = [table.title] if table.title else []
    out += [rule, *physical(list(columns)), rule]
    for row in cells:
        out += physical(row)
    out.append(rule)
    return "\n".join(out)


# -------------------------------------------------------------------- rich
def _rich_table(table: Table):
    from rich import box
    from rich.table import Table as RichTable
    from rich.text import Text

    rich = RichTable(
        box=box.ROUNDED,
        header_style="bold cyan",
        title=table.title or None,
        title_style="bold",
        title_justify="left",
    )
    for name in table.columns:
        folds = name in table.wrap
        rich.add_column(
            name,
            justify="right" if name in table.right else "left",
            no_wrap=not folds,
            # A column that may not wrap shows "..." when the window is too
            # narrow instead of silently cutting the value.
            overflow="fold" if folds else "ellipsis",
        )
    for row in table.cells():
        # Text, not str: a cell such as "[red]" is data, never markup.
        rich.add_row(*[Text(c) if c else Text("-", style="dim") for c in row])
    return rich


class Out:
    """Writes lines and tables to a stream, choosing the renderer once."""

    def __init__(self, stream: TextIO | None = None, mode: str | None = None) -> None:
        self.stream = stream or sys.stdout
        self.mode = mode or resolve_mode(self.stream)
        self._console: Any = None

    def _rich_console(self):
        if self._console is None:
            from rich.console import Console

            self._console = Console(
                file=self.stream,
                force_terminal=True if _wanted() == "always" else None,
            )
        return self._console

    def line(self, text: str = "") -> None:
        self.stream.write(text + "\n")

    def heading(self, text: str) -> None:
        if self.mode == RICH:
            from rich.text import Text

            self._rich_console().print(Text(text, style="bold"))
        else:
            self.line(text)

    def note(self, text: str) -> None:
        """A side remark: dim on a terminal, plain otherwise."""
        if self.mode == RICH:
            from rich.text import Text

            self._rich_console().print(Text(text, style="dim"))
        else:
            self.line(text)

    def table(self, table: Table) -> None:
        if self.mode == RICH:
            self._rich_console().print(_rich_table(table))
        else:
            self.line(render_plain(table, terminal_width()))
