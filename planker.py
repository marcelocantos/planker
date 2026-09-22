#!/usr/bin/env python3
"""Cut available planks into desired lengths, and print a shop sheet.

Stdin (or a JSON file) supplies ``available`` and ``desired`` as
``[[count, length_mm], ...]``. The cutter is greedy best-fit: desired
pieces, longest first, each go on the board with the smallest leftover
that still fits.

Saw kerf defaults to 3 mm and sits between cuts on the same board, not
after the last cut. Pass ``--html`` for a printable cut plan and
lumber-yard list. With no flag, stdout stays tab-separated for the
spreadsheet paste.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, TextIO


KERF_MM = 3

# Categorical colours for piece lengths. Longest length takes the first
# colour. Text on the swatch is chosen from the colour's luminance.
_CUT_COLOURS = (
    "#8c2f1b",
    "#d85a1a",
    "#c48a00",
    "#5f7f24",
    "#1f7a4d",
    "#0f766e",
    "#1d6a93",
    "#2a4e8a",
    "#5b3f8c",
    "#8e3a78",
    "#a33b4a",
    "#6b4a2a",
    "#3e4c59",
    "#b45309",
    "#3f6212",
    "#57534e",
)


@dataclass(frozen=True)
class BoardPlan:
    """One available board, in TSV row order (1-based ``index``)."""

    index: int
    stock_mm: int
    cuts: tuple[int, ...]
    tsv_leftover_mm: int

    @property
    def used(self) -> bool:
        return bool(self.cuts)

    def kerf_spans(self) -> int:
        """Number of saw kerfs on this board (one between each pair of cuts)."""
        return max(0, len(self.cuts) - 1)

    def physical_leftover_mm(self, kerf_mm: int) -> int:
        """Millimetres of board left after pieces and the kerfs between them.

        The TSV leftover for an unused board is ``stock + kerf`` (the cutter's
        starting figure). That is not an offcut; the board is still whole.
        """
        if not self.used:
            return self.stock_mm
        return self.tsv_leftover_mm

    def consistent(self, kerf_mm: int) -> bool:
        if not self.used:
            return self.tsv_leftover_mm == self.stock_mm + kerf_mm
        used = sum(self.cuts) + kerf_mm * self.kerf_spans() + self.tsv_leftover_mm
        return used == self.stock_mm


@dataclass(frozen=True)
class Plan:
    kerf_mm: int
    available_rows: tuple[tuple[int, int], ...]
    desired_rows: tuple[tuple[int, int], ...]
    boards: tuple[BoardPlan, ...]
    unallocated: tuple[int, ...]

    def pull_counts(self) -> tuple[tuple[int, int], ...]:
        """``(length_mm, count)`` of boards this plan actually cuts."""
        return _counts(board.stock_mm for board in self.boards if board.used)

    def leave_counts(self) -> tuple[tuple[int, int], ...]:
        """``(length_mm, count)`` of available boards with no cuts."""
        return _counts(board.stock_mm for board in self.boards if not board.used)

    def project_counts(self) -> tuple[tuple[int, int], ...]:
        return _counts(_expand(self.desired_rows))

    def placed_counts(self) -> tuple[tuple[int, int], ...]:
        return _counts(cut for board in self.boards for cut in board.cuts)

    def unallocated_counts(self) -> tuple[tuple[int, int], ...]:
        return _counts(self.unallocated)

    def on_hand_counts(self) -> tuple[tuple[int, int], ...]:
        return _counts(board.stock_mm for board in self.boards)


def _counts(lengths: Iterable[int]) -> tuple[tuple[int, int], ...]:
    """``(length_mm, count)`` sorted longest first."""
    counter = Counter(lengths)
    return tuple(sorted(counter.items(), key=lambda item: item[0], reverse=True))


def _expand(rows: Iterable[tuple[int, int]]) -> list[int]:
    pieces: list[int] = []
    for count, length in rows:
        pieces.extend([length] * count)
    return pieces


def _rows(raw) -> tuple[tuple[int, int], ...]:
    return tuple((count, length) for count, length in raw)


def allocate_greedy(
    pieces: list[int], cuts: list[int], kerf: int = KERF_MM
) -> tuple[list[list[int]], list[int], list[int]]:
    """Best-fit greedy allocation.

    ``leftover`` starts at ``stock + kerf`` so each accepted cut consumes
    ``length + kerf``. That leaves ``(n - 1)`` kerfs between ``n`` pieces and
    no kerf after the last cut. A board that receives nothing keeps the
    starting figure ``stock + kerf`` in the leftover list (the TSV column).

    Unallocated entries are the desired piece lengths, without kerf added.
    """
    allocated: list[list[int]] = [[] for _ in pieces]
    unallocated: list[int] = []
    leftover = [length + kerf for length in pieces]
    for want in cuts:
        need = want + kerf
        candidates = {(remain, index) for index, remain in enumerate(leftover) if remain >= need}
        if candidates:
            _, best_i = min(candidates)
            allocated[best_i].append(want)
            leftover[best_i] -= need
        else:
            unallocated.append(want)
    return allocated, unallocated, leftover


def build_plan(data: dict, kerf_mm: int = KERF_MM) -> Plan:
    available_rows = _rows(data["available"])
    desired_rows = _rows(data["desired"])
    available = _expand(available_rows)
    desired = sorted(_expand(desired_rows), reverse=True)
    allocated, unallocated, leftover = allocate_greedy(available, desired, kerf_mm)
    boards = tuple(
        BoardPlan(
            index=index,
            stock_mm=stock,
            cuts=tuple(cuts),
            tsv_leftover_mm=remain,
        )
        for index, (stock, cuts, remain) in enumerate(
            zip(available, allocated, leftover), start=1
        )
    )
    plan = Plan(
        kerf_mm=kerf_mm,
        available_rows=available_rows,
        desired_rows=desired_rows,
        boards=boards,
        unallocated=tuple(unallocated),
    )
    for board in plan.boards:
        if not board.consistent(kerf_mm):
            raise RuntimeError(
                f"board {board.index} leftover does not match stock, cuts, and kerf"
            )
    return plan


def colour_for(lengths: Iterable[int]) -> dict[int, str]:
    unique = sorted(set(lengths), reverse=True)
    return {length: _CUT_COLOURS[i % len(_CUT_COLOURS)] for i, length in enumerate(unique)}


def ink_on(hex_colour: str) -> str:
    """Dark or light ink so a length label stays readable on its swatch."""
    channel = hex_colour.lstrip("#")
    red, green, blue = int(channel[0:2], 16), int(channel[2:4], 16), int(channel[4:6], 16)
    luminance = (0.299 * red + 0.587 * green + 0.114 * blue) / 255
    return "#1f1a14" if luminance > 0.62 else "#fffaf3"


def describe_offcut(leftover_mm: int, piece_lengths: Iterable[int]) -> str:
    """Say what an offcut can cover, using piece lengths from the job only."""
    lengths = sorted(set(piece_lengths))
    if leftover_mm <= 0 or not lengths:
        return "no offcut"
    fits = [length for length in lengths if length <= leftover_mm]
    longer = [length for length in lengths if length > leftover_mm]
    if not fits:
        return (
            f"too short for a {lengths[0]:,} mm piece, the shortest on this job"
        )
    longest_fit = fits[-1]
    if longer:
        return f"long enough for {longest_fit:,} mm, shorter than {longer[0]:,} mm"
    return f"long enough for {longest_fit:,} mm, the longest piece on this job"


def metres(mm: int) -> str:
    """Same length in metres, grouped from the integer millimetres."""
    sign = "-" if mm < 0 else ""
    whole, frac = divmod(abs(mm), 1000)
    return f"{sign}{whole}.{frac:03d} m"


def mm_text(mm: int) -> str:
    return f"{mm:,} mm"


def render_lumber_text(plan: Plan) -> str:
    """Plain-text list a builder can paste into a note or a message."""
    lines = [
        "PLANKER LUMBER LIST",
        f"Kerf: {plan.kerf_mm} mm between cuts on the same board",
        "",
        "PULL",
    ]
    pulls = plan.pull_counts()
    if pulls:
        for length, count in pulls:
            lines.append(f"{count} x {length} mm ({metres(length)})")
        total_mm = sum(board.stock_mm for board in plan.boards if board.used)
        total_n = sum(count for _, count in pulls)
        lines.append(f"Total: {total_n} boards, {total_mm} mm ({metres(total_mm)})")
    else:
        lines.append("none")
    lines += ["", "LEAVE"]
    leaves = plan.leave_counts()
    if leaves:
        for length, count in leaves:
            lines.append(f"{count} x {length} mm ({metres(length)})")
    else:
        lines.append("none")
    lines += ["", "DOES NOT FIT"]
    missing = plan.unallocated_counts()
    if missing:
        for length, count in missing:
            lines.append(f"{count} x {length} mm")
        lines.append("These are piece lengths from desired, not a board to order.")
    else:
        lines.append("none")
    lines.append("")
    return "\n".join(lines)


def render_tsv(plan: Plan) -> str:
    """Spreadsheet paste: stock, TSV leftover, then cuts. One board per row."""
    lines = ["allocated\tleftover\tcuts"]
    for board in plan.boards:
        cells = [str(board.stock_mm), str(board.tsv_leftover_mm)]
        cells.extend(str(cut) for cut in board.cuts)
        lines.append("\t".join(cells))
    return "\n".join(lines) + "\n"


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _check_line(board: BoardPlan, kerf_mm: int) -> str:
    if not board.used:
        return (
            f"not cut — {mm_text(board.stock_mm)} left whole "
            f"(spreadsheet leftover {mm_text(board.tsv_leftover_mm)})"
        )
    parts = [f"{cut:,}" for cut in board.cuts]
    kerf_total = kerf_mm * board.kerf_spans()
    if kerf_total:
        parts.append(f"kerf {kerf_total:,}")
    leftover = board.physical_leftover_mm(kerf_mm)
    parts.append(f"offcut {leftover:,}")
    return " + ".join(parts) + f" = {board.stock_mm:,}"


def _label_fits(length_mm: int) -> bool:
    return length_mm >= 155 * len(str(length_mm))


def _bar_svg(board: BoardPlan, plan: Plan, colours: dict[int, str], max_mm: int) -> str:
    kerf = plan.kerf_mm
    top, bar_h, font = 12, 420, 180
    height = top + bar_h + 28
    label_y = top + bar_h / 2 + font * 0.35
    parts: list[str] = [
        (
            f'<svg class="bar" viewBox="0 0 {max_mm} {height}" preserveAspectRatio="none" '
            f'role="img" aria-label="{_esc(_bar_label(board, plan))}">'
        ),
        (
            "<defs>"
            f'<pattern id="offcut-{board.index}" patternUnits="userSpaceOnUse" '
            'width="90" height="90" patternTransform="rotate(45)">'
            '<rect width="90" height="90" fill="#f4e7d4"/>'
            '<line x1="0" y1="0" x2="0" y2="90" stroke="#c4a484" stroke-width="28"/>'
            "</pattern>"
            f'<pattern id="unused-{board.index}" patternUnits="userSpaceOnUse" '
            'width="120" height="120" patternTransform="rotate(45)">'
            '<rect width="120" height="120" fill="#f7f1e6"/>'
            '<line x1="0" y1="0" x2="0" y2="120" stroke="#d9cbb8" stroke-width="22"/>'
            "</pattern>"
            "</defs>"
        ),
        (
            f'<line x1="0" y1="{top + bar_h + 16}" x2="{max_mm}" y2="{top + bar_h + 16}" '
            'stroke="#e4d9c8" stroke-width="8"/>'
        ),
    ]
    x = 0
    if not board.used:
        parts.append(
            f'<rect x="0" y="{top}" width="{board.stock_mm}" height="{bar_h}" '
            f'fill="url(#unused-{board.index})"><title>not cut, {board.stock_mm} mm</title></rect>'
        )
        parts.append(
            f'<text x="{board.stock_mm / 2}" y="{label_y}" text-anchor="middle" '
            f'fill="#6d6256" font-size="{font}">not cut</text>'
        )
    else:
        for index, cut in enumerate(board.cuts):
            colour = colours.get(cut, "#57534e")
            parts.append(
                f'<rect x="{x}" y="{top}" width="{cut}" height="{bar_h}" fill="{colour}">'
                f"<title>{cut} mm</title></rect>"
            )
            if _label_fits(cut):
                parts.append(
                    f'<text x="{x + cut / 2}" y="{label_y}" text-anchor="middle" '
                    f'fill="{ink_on(colour)}" font-size="{font}">{cut}</text>'
                )
            x += cut
            if index != len(board.cuts) - 1:
                parts.append(
                    f'<rect x="{x}" y="{top}" width="{kerf}" height="{bar_h}" fill="#1f1a14">'
                    f"<title>{kerf} mm kerf</title></rect>"
                )
                mid = x + kerf / 2
                parts.append(
                    f'<line x1="{mid}" y1="{top}" x2="{mid}" y2="{top + bar_h}" '
                    'stroke="#1a120c" stroke-width="2" vector-effect="non-scaling-stroke"/>'
                )
                x += kerf
        leftover = board.stock_mm - x
        if leftover < 0:
            raise RuntimeError(f"board {board.index} cuts exceed the stock")
        if leftover:
            parts.append(
                f'<rect x="{x}" y="{top}" width="{leftover}" height="{bar_h}" '
                f'fill="url(#offcut-{board.index})"><title>{leftover} mm offcut</title></rect>'
            )
            if _label_fits(leftover):
                parts.append(
                    f'<text x="{x + leftover / 2}" y="{label_y}" '
                    f'text-anchor="middle" fill="#6d6256" font-size="{font}">'
                    f"{leftover}</text>"
                )
    parts.append(
        f'<rect x="0" y="{top}" width="{board.stock_mm}" height="{bar_h}" fill="none" '
        'stroke="#1f1a14" stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _bar_label(board: BoardPlan, plan: Plan) -> str:
    if not board.used:
        return f"Board {board.index}, {board.stock_mm} mm, not cut"
    cuts = ", ".join(str(cut) for cut in board.cuts)
    left = board.physical_leftover_mm(plan.kerf_mm)
    return f"Board {board.index}, {board.stock_mm} mm, cuts {cuts}, offcut {left} mm"


def _ruler_html(max_mm: int) -> str:
    """Millimetre scale in HTML so the labels stay readable on a phone."""
    labels = [0]
    for tick in range(1000, max_mm, 1000):
        if max_mm - tick >= 800:
            labels.append(tick)
    if max_mm not in labels:
        labels.append(max_mm)
    ticks = []
    seen = set()
    for tick in list(range(0, max_mm + 1, 500)) + [max_mm]:
        if tick in seen or tick > max_mm:
            continue
        seen.add(tick)
        major = tick % 1000 == 0 or tick == max_mm
        pct = 100 * tick / max_mm
        kind = "major" if major else "minor"
        ticks.append(f'<i class="{kind}" style="left:{pct:.4f}%"></i>')
    marks = []
    for tick in labels:
        pct = 100 * tick / max_mm
        cls = "start" if tick == 0 else "end" if tick == max_mm else "mid"
        marks.append(f'<span class="{cls}" style="left:{pct:.4f}%">{tick}</span>')
    return f'<div class="ruler" aria-hidden="true">{"".join(ticks)}{"".join(marks)}</div>'


def _count_list(
    rows: tuple[tuple[int, int], ...],
    colours: dict[int, str],
    placed: dict[int, int] | None = None,
) -> str:
    """Big rows a thumb can scan. Same lengths as the input, not a dense table."""
    items = []
    for length, count in rows:
        swatch = colours.get(length)
        swatch_html = (
            f"<i class='swatch' style='background:{swatch}'></i>" if swatch else ""
        )
        detail = ""
        if placed is not None:
            got = placed.get(length, 0)
            missing = count - got
            miss = f" · <b class='miss'>{missing} not placed</b>" if missing else ""
            detail = f"<span class='sub'>{got} placed{miss}</span>"
        items.append(
            "<li>"
            f"<span class='count'>{count}</span>"
            f"<span class='mm'>{swatch_html}{_esc(mm_text(length))}</span>"
            f"{detail}"
            "</li>"
        )
    if not items:
        items.append("<li><span class='mm'>None</span></li>")
    return f"<ul class='rows'>{''.join(items)}</ul>"


def _input_list(rows: tuple[tuple[int, int], ...]) -> str:
    items = []
    for index, (count, length) in enumerate(rows, start=1):
        items.append(
            "<li>"
            f"<span class='idx'>Row {index}</span>"
            f"<span class='count'>{count} ×</span>"
            f"<span class='mm'>{length} mm</span>"
            f"<span class='m'>{metres(length)}</span>"
            "</li>"
        )
    if not items:
        items.append("<li><span class='mm'>None</span></li>")
    return f"<ul class='rows entered'>{''.join(items)}</ul>"


def _chips(board: BoardPlan, plan: Plan, colours: dict[int, str]) -> str:
    if not board.used:
        return "<p class='chips'><span class='chip quiet'>no cuts</span></p>"
    chips = []
    for cut in board.cuts:
        chips.append(
            f"<span class='chip'><i style='background:{colours.get(cut, '#57534e')}'></i>{cut}</span>"
        )
    left = board.physical_leftover_mm(plan.kerf_mm)
    if left:
        chips.append(f"<span class='chip off'>{left} left</span>")
    return f"<p class='chips'>{''.join(chips)}</p>"


_PAGE_CSS = """
:root {
  --paper: #f3ecdf;
  --sheet: #fffaf3;
  --ink: #1f1a14;
  --muted: #6d6256;
  --line: #eadfce;
  --rule: #d9cbb6;
  --stamp: #8c2f1b;
  --ok: #1f7a4d;
  --shadow: 0 16px 40px rgba(60, 40, 20, 0.08);
  --dock: 76px;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 18px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  touch-action: manipulation;
}
.sheet {
  max-width: 880px;
  margin: 0 auto;
  background: var(--sheet);
  padding: 16px 16px calc(var(--dock) + env(safe-area-inset-bottom));
}
header.top {
  border-top: 8px solid var(--stamp);
  padding-top: 14px;
}
.kicker {
  margin: 0;
  color: var(--stamp);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}
h1 {
  margin: 4px 0 0;
  font-family: Palatino, "Palatino Linotype", "Iowan Old Style", Georgia, serif;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.05;
}
.lede { margin: 8px 0 0; color: var(--muted); font-size: 17px; }
nav.jumps { display: flex; gap: 4px 18px; flex-wrap: wrap; margin: 12px 0 0; }
nav.jumps a {
  color: var(--stamp);
  font-size: 17px;
  font-weight: 700;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  text-decoration: none;
}
h2 {
  margin: 28px 0 8px;
  font-family: Palatino, "Palatino Linotype", Georgia, serif;
  font-size: 28px;
  line-height: 1.15;
  break-after: avoid;
}
h3 { margin: 22px 0 6px; font-size: 18px; break-after: avoid; }
p.note, .footnote { color: var(--muted); font-size: 16px; }
.stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: 16px 0 8px;
}
.stats div {
  border: 1px solid var(--line);
  background: #fff;
  padding: 10px 12px 12px;
  min-height: 72px;
}
.stats dt {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.stats dd { margin: 2px 0 0; font-size: 28px; font-variant-numeric: tabular-nums; font-weight: 700; }
.stats dd small { font-size: 15px; font-weight: 600; color: var(--muted); margin-left: 4px; }
.stats .bad dd { color: var(--stamp); }
.stats .ok dd { color: var(--ok); }
.pull, .leave, .rows { list-style: none; margin: 0; padding: 0; }
.pull { border-left: 4px solid var(--stamp); padding-left: 12px; }
.leave { border-left: 4px solid #c4b39a; padding-left: 12px; }
.total { margin: 8px 0 0; font-weight: 700; font-size: 18px; font-variant-numeric: tabular-nums; }
.pull li, .leave li, .rows li { border-top: 1px solid var(--line); }
.pull label, .leave li {
  display: grid;
  grid-template-columns: 52px 1fr;
  align-items: center;
  column-gap: 8px;
  row-gap: 0;
  min-height: 84px;
  padding: 12px 0;
}
.leave li { grid-template-columns: 1fr; min-height: 76px; }
.pull input {
  grid-row: 1 / span 3;
  width: 28px;
  height: 28px;
  justify-self: center;
  accent-color: var(--stamp);
}
.pull .count, .leave .count, .rows .count {
  font-size: 40px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.mm { font-size: 26px; font-variant-numeric: tabular-nums; font-weight: 700; }
.m, .sub, .rows .idx { color: var(--muted); font-size: 16px; font-variant-numeric: tabular-nums; }
.rows li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 12px;
  min-height: 56px;
  padding: 12px 0;
}
.rows .count { font-size: 28px; }
.rows .mm { font-size: 20px; }
.rows .idx { min-width: 4.2em; font-weight: 700; }
b.miss { color: var(--stamp); }
.swatch, .chip i {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 8px;
  vertical-align: -1px;
  border: 1px solid rgba(31, 26, 20, 0.25);
}
.legend { display: flex; flex-wrap: wrap; gap: 8px 16px; list-style: none; padding: 0; margin: 8px 0 12px; }
.legend li { display: flex; align-items: center; gap: 8px; font-size: 16px; min-height: 32px; }
.key { width: 28px; height: 16px; border: 1px solid rgba(31, 26, 20, 0.35); }
.key.kerf { background: #1f1a14; }
.key.off {
  background: repeating-linear-gradient(45deg, #f4e7d4, #f4e7d4 3px, #c4a484 3px, #c4a484 5px);
}
.key.idle {
  background: repeating-linear-gradient(45deg, #f7f1e6, #f7f1e6 4px, #d9cbb8 4px, #d9cbb8 6px);
}
.viz { min-width: 0; width: 100%; }
.board {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 0;
  border-top: 1px solid var(--line);
  break-inside: avoid;
}
.board.idle { background: #f6f0e6; }
.ruler-row { border-top: 0; padding-top: 0; padding-bottom: 0; }
.ruler-row .meta, .ruler-row > div:last-child { display: none; }
.meta { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: baseline; }
.idx { color: var(--muted); font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; }
.cuts-n { color: var(--muted); font-size: 16px; }
.stock { font-size: 28px; font-weight: 700; font-variant-numeric: tabular-nums; }
.offcut { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.offcut strong { font-size: 32px; font-variant-numeric: tabular-nums; line-height: 1; }
.offcut span { color: var(--muted); font-size: 16px; }
.tag.short { color: var(--stamp); font-weight: 700; }
.tag.keep { color: var(--ok); font-weight: 700; }
.phrase { margin: 0; color: var(--muted); font-size: 16px; }
.bar { width: 100%; height: 72px; display: block; }
.bar text { display: none; }
.ruler { position: relative; height: 36px; margin: 0; }
.ruler i {
  position: absolute;
  bottom: 0;
  width: 1px;
  background: #8a7b68;
}
.ruler i.major { height: 12px; }
.ruler i.minor { height: 7px; }
.ruler span {
  position: absolute;
  top: 0;
  font-size: 14px;
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.ruler span.mid { transform: translateX(-50%); }
.ruler span.end { transform: translateX(-100%); }
.chips { margin: 4px 0 0; }
.chip {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  margin: 0 8px 8px 0;
  padding: 6px 10px 6px 8px;
  background: #fff;
  border: 1px solid var(--line);
  font-variant-numeric: tabular-nums;
  font-size: 17px;
}
.chip.off, .chip.quiet { color: var(--muted); }
.check { margin: 0; color: var(--muted); font-size: 15px; font-variant-numeric: tabular-nums; }
.plain-wrap summary {
  min-height: 44px;
  display: flex;
  align-items: center;
  font-weight: 700;
  cursor: pointer;
}
pre.plain {
  background: #fff;
  border: 1px solid var(--line);
  padding: 12px 14px;
  overflow: auto;
  font: 15px/1.45 ui-monospace, "SFMono-Regular", Menlo, Consolas, monospace;
}
.length-group { margin-top: 8px; }
.length-group h3 { margin-bottom: 0; }
.keep { break-inside: avoid; }
button {
  background: var(--ink);
  color: var(--sheet);
  border: 0;
  border-radius: 8px;
  min-height: 48px;
  padding: 10px 12px;
  font: inherit;
  font-weight: 700;
  cursor: pointer;
  touch-action: manipulation;
}
button.ghost { background: #fff; color: var(--ink); border: 1px solid var(--rule); }
.dock {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 3;
  display: flex;
  gap: 8px;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  background: rgba(255, 250, 243, 0.97);
  border-top: 1px solid var(--rule);
}
.dock button { flex: 1; font-size: 17px; }
@media (min-width: 680px) {
  .sheet {
    margin: 20px auto 32px;
    padding: 28px 28px calc(var(--dock) + 24px);
    border: 1px solid var(--rule);
    box-shadow: var(--shadow);
  }
  h1 { font-size: 40px; }
  .stats { grid-template-columns: repeat(4, 1fr); }
  .board {
    display: grid;
    grid-template-columns: 112px minmax(0, 1fr) 132px;
    gap: 12px;
    align-items: start;
  }
  .ruler-row .meta, .ruler-row > div:last-child { display: block; }
  .meta { display: block; padding-top: 8px; }
  .offcut { display: block; text-align: right; padding-top: 8px; }
  .offcut span { display: block; }
  .dock {
    left: 50%;
    right: auto;
    width: min(880px, calc(100% - 32px));
    transform: translateX(-50%);
    border: 1px solid var(--rule);
    border-bottom: 0;
    border-radius: 12px 12px 0 0;
  }
}
@page { size: A4; margin: 12mm; }
@media print {
  body { background: #fff; }
  .sheet { margin: 0; max-width: none; border: 0; box-shadow: none; padding: 0; }
  .no-print, .dock { display: none !important; }
  .cut-plan { break-before: page; }
  .bar { height: 28px; }
  a { color: inherit; text-decoration: none; }
  * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""


def render_html(plan: Plan) -> str:
    """Printable page: lumber list, the input, and a to-scale cut plan."""
    colours = colour_for(_expand(plan.desired_rows))
    piece_lengths = [length for length, _ in plan.project_counts()]
    placed = dict(plan.placed_counts())
    pulls = plan.pull_counts()
    leaves = plan.leave_counts()
    missing = plan.unallocated_counts()
    pull_n = sum(count for _, count in pulls)
    leave_n = sum(count for _, count in leaves)
    placed_n = sum(len(board.cuts) for board in plan.boards)
    missing_n = len(plan.unallocated)
    offcut_mm = sum(board.physical_leftover_mm(plan.kerf_mm) for board in plan.boards if board.used)
    kerf_mm_total = sum(plan.kerf_mm * board.kerf_spans() for board in plan.boards)
    on_hand_mm = sum(board.stock_mm for board in plan.boards)
    desired_mm = sum(length * count for length, count in plan.project_counts())
    missing_class = "ok" if missing_n == 0 else "bad"

    pull_items = []
    for length, count in pulls:
        pull_items.append(
            "<li><label>"
            "<input type='checkbox'>"
            f"<span class='count'>{count}</span>"
            f"<span class='mm'>{_esc(mm_text(length))}</span>"
            f"<span class='m'>{_esc(metres(length))} each</span>"
            "</label></li>"
        )
    if not pull_items:
        pull_items.append("<li><p class='note'>No board is long enough for a cut.</p></li>")

    leave_items = []
    for length, count in leaves:
        leave_items.append(
            "<li>"
            f"<span class='count'>{count}</span>"
            f"<span class='mm'>{_esc(mm_text(length))}</span>"
            f"<span class='m'>{_esc(metres(length))} each</span>"
            "</li>"
        )

    if missing:
        missing_bits = ", ".join(
            f"{count} × {mm_text(length)}" for length, count in missing
        )
        missing_html = (
            "<h3>Pieces that still need a board</h3>"
            f"<p>{_esc(missing_bits)}</p>"
            "<p class='note'>These lengths are the pieces from <code>desired</code> "
            "that did not fit. This page does not choose a board to buy.</p>"
        )
    else:
        missing_html = (
            "<p class='note'>Every desired piece is on a board in the cut plan. "
            "Nothing further to buy for these cuts.</p>"
        )

    balance_items = []
    pull_map = dict(pulls)
    leave_map = dict(leaves)
    for length, count in plan.on_hand_counts():
        balance_items.append(
            "<li>"
            f"<span class='mm'>{_esc(mm_text(length))}</span>"
            "<span class='sub'>"
            f"On hand {count} · Pull {pull_map.get(length, 0)} · Leave {leave_map.get(length, 0)}"
            "</span>"
            "</li>"
        )
    if not balance_items:
        balance_items.append("<li><span class='mm'>No available boards.</span></li>")

    max_mm = max((board.stock_mm for board in plan.boards), default=0)
    groups: list[str] = []
    previous_length = None
    for board in plan.boards:
        if board.stock_mm != previous_length:
            if previous_length is not None:
                groups.append("</div>")
            groups.append(
                f"<div class='length-group'><h3>{_esc(mm_text(board.stock_mm))} boards</h3>"
            )
            previous_length = board.stock_mm
        left = board.physical_leftover_mm(plan.kerf_mm)
        phrase_html = ""
        if not board.used:
            off_html = "<strong>—</strong><span>leave</span>"
            meta_extra = "leave"
            idle = " idle"
        else:
            phrase = describe_offcut(left, piece_lengths)
            short = phrase.startswith("too short") or phrase == "no offcut"
            tag = "short" if short else "keep"
            label = "too short" if short else "keep"
            off_html = (
                f"<strong>{left:,}</strong><span>mm offcut</span>"
                f"<span class='tag {tag}'>{label}</span>"
            )
            # The repeated "too short" sentence is in the section intro.
            # A board that can still cover a real piece gets that length here.
            phrase_html = "" if short else f"<p class='phrase'>{_esc(phrase)}</p>"
            meta_extra = f"{len(board.cuts)} cuts"
            idle = ""
        groups.append(
            f"<article class='board{idle}'>\n"
            "<div class='meta'>"
            f"<span class='idx'>Board {board.index}</span>"
            f"<span class='stock'>{board.stock_mm}</span>"
            f"<span class='cuts-n'>{meta_extra}</span>"
            "</div>\n"
            "<div class='viz'>"
            f"{_bar_svg(board, plan, colours, max_mm)}"
            f"{_chips(board, plan, colours)}"
            f"{phrase_html}"
            f"<p class='check'>{_esc(_check_line(board, plan.kerf_mm))}</p>"
            "</div>\n"
            f"<div class='offcut'>{off_html}</div>\n"
            "</article>\n"
        )
    if previous_length is not None:
        groups.append("</div>")
    elif not plan.boards:
        groups.append("<p class='note'>No available boards.</p>")

    ruler = _ruler_html(max_mm) if max_mm else ""
    ruler_row = (
        f'<div class="board ruler-row"><div class="meta"></div><div class="viz">{ruler}</div><div></div></div>'
        if ruler
        else ""
    )
    pull_mm = sum(board.stock_mm for board in plan.boards if board.used)
    leave_mm = sum(board.stock_mm for board in plan.boards if not board.used)
    pull_total = (
        f"<p class='total'>{pull_n} boards · {_esc(mm_text(pull_mm))} · {_esc(metres(pull_mm))}</p>"
        if pull_n
        else ""
    )
    leave_total = (
        f"<p class='total'>{leave_n} boards · {_esc(mm_text(leave_mm))} · {_esc(metres(leave_mm))}</p>"
        if leave_n
        else ""
    )
    lumber_text = render_lumber_text(plan)
    avail_n = sum(count for count, _ in plan.available_rows)
    desired_n = sum(count for count, _ in plan.desired_rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#f3ecdf">
<title>Planker cut plan</title>
<style>{_PAGE_CSS}</style>
</head>
<body>
<main class="sheet">
<header class="top">
  <p class="kicker">Planker</p>
  <h1>Cut plan and lumber list</h1>
  <p class="lede">Open this page on your phone at the yard. Tick a row as you pull that board. Kerf is {plan.kerf_mm} mm between cuts. Lengths are the millimetres in the input.</p>
  <nav class="jumps no-print">
    <a href="#yard">Lumber list</a>
    <a href="#inputs">Inputs</a>
    <a href="#cuts">Cut plan</a>
  </nav>
</header>

<dl class="stats">
  <div><dt>Pull</dt><dd>{pull_n} <small>boards</small></dd></div>
  <div><dt>Leave</dt><dd>{leave_n} <small>boards</small></dd></div>
  <div><dt>Placed</dt><dd>{placed_n} <small>pieces</small></dd></div>
  <div class="{missing_class}"><dt>Not placed</dt><dd>{missing_n} <small>pieces</small></dd></div>
</dl>
<p class="note">On hand: {len(plan.boards)} boards, {_esc(mm_text(on_hand_mm))} ({_esc(metres(on_hand_mm))}). Project: {desired_n} pieces, {_esc(mm_text(desired_mm))} ({_esc(metres(desired_mm))}). Offcut on pulled boards: {_esc(mm_text(offcut_mm))}. Saw kerf: {_esc(mm_text(kerf_mm_total))}.</p>

<section id="yard">
  <h2>Lumber-yard list</h2>
  <p class="note">Tick these off as you pull them. Use the length on the row — a shorter board is not a substitute. Counts are boards this plan cuts, taken from <code>available</code>.</p>
  <h3>Pull</h3>
  <ul class="pull">{''.join(pull_items)}</ul>
  {pull_total}
  <h3>Leave on the rack</h3>
  {('<ul class="leave">' + ''.join(leave_items) + '</ul>' + leave_total) if leave_items else '<p class="note">Every available board is cut in this plan.</p>'}
  {missing_html}
  <div class="keep">
  <h3>Stock balance</h3>
  <ul class="rows">{''.join(balance_items)}</ul>
  </div>
  <details class="plain-wrap no-print">
    <summary>Plain text</summary>
    <pre id="lumber-text" class="plain">{_esc(lumber_text)}</pre>
  </details>
</section>

<section id="inputs">
  <h2>Check the input</h2>
  <h3>Available stock</h3>
  <p class="note">{len(plan.available_rows)} rows, {avail_n} boards, as entered. Rolled up:</p>
  {_count_list(plan.on_hand_counts(), colours)}
  {_input_list(plan.available_rows)}
  <h3>Project pieces</h3>
  <p class="note">{len(plan.desired_rows)} rows, {desired_n} pieces, as entered. Colours match the cut plan. Rolled up:</p>
  {_count_list(plan.project_counts(), colours, placed)}
  {_input_list(plan.desired_rows)}
</section>

<section id="cuts" class="cut-plan">
  <h2>Cut plan</h2>
  <p class="note">Each bar is one board, to scale with the ruler (millimetres). Board numbers follow the TSV rows. Left to right is the cut order. A short offcut is a thin sliver; the number at the right is its length. The dark line is the {plan.kerf_mm} mm kerf, drawn at least a hairline so it stays visible. “Too short” means the offcut is shorter than every piece on this job.</p>
  <ul class="legend">
    <li><i class="key kerf"></i> Kerf {plan.kerf_mm} mm</li>
    <li><i class="key off"></i> Offcut</li>
    <li><i class="key idle"></i> Board not cut</li>
  </ul>
  {ruler_row}
  {''.join(groups)}
</section>

<p class="footnote">An unused board is left whole. The spreadsheet leftover for that row is stock + kerf (the cutter's starting figure), not an offcut. On a cut board the spreadsheet leftover matches the offcut shown here.</p>
</main>
<nav class="dock no-print" aria-label="Share this list">
  <button type="button" id="share-btn">Share</button>
  <button type="button" id="copy-btn" class="ghost">Copy</button>
  <button type="button" id="print-btn" class="ghost">Print</button>
</nav>
<script>
function lumberText() {{
  return document.getElementById("lumber-text").textContent;
}}
function selectLumber(pre) {{
  if (pre.parentElement && pre.parentElement.open === false) pre.parentElement.open = true;
  var range = document.createRange();
  range.selectNodeContents(pre);
  var sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(range);
  pre.scrollIntoView({{behavior: "smooth", block: "center"}});
}}
document.getElementById("print-btn").addEventListener("click", function () {{ window.print(); }});
document.getElementById("copy-btn").addEventListener("click", async function () {{
  var button = this;
  var pre = document.getElementById("lumber-text");
  try {{
    await navigator.clipboard.writeText(lumberText());
    button.textContent = "Copied";
  }} catch (err) {{
    selectLumber(pre);
    button.textContent = "Selected";
  }}
}});
document.getElementById("share-btn").addEventListener("click", async function () {{
  var button = this;
  var text = lumberText();
  if (navigator.share) {{
    try {{
      await navigator.share({{title: "Planker lumber list", text: text}});
      button.textContent = "Shared";
      return;
    }} catch (err) {{
      if (err && err.name === "AbortError") return;
    }}
  }}
  try {{
    await navigator.clipboard.writeText(text);
    button.textContent = "Copied";
  }} catch (err) {{
    selectLumber(document.getElementById("lumber-text"));
    button.textContent = "Selected";
  }}
}});
</script>
</body>
</html>
"""


def _load(path: str | None) -> dict:
    if path:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    return json.load(sys.stdin)


def main(argv: list[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="planker.py",
        description=(
            "Cut available planks into desired lengths. "
            "Reads JSON from a file or stdin."
        ),
        epilog=(
            "examples:\n"
            "  python3 planker.py < input.json\n"
            "  python3 planker.py --html docs/cut-plan.html input.json\n"
            "  python3 planker.py --html - input.json > cut-plan.html\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="JSON file with available and desired pairs (default: stdin)",
    )
    parser.add_argument(
        "--html",
        metavar="FILE",
        help="write a printable cut plan and lumber-yard list (use - for stdout)",
    )
    parser.add_argument(
        "--kerf",
        type=int,
        default=KERF_MM,
        help=f"saw kerf in millimetres between cuts (default: {KERF_MM})",
    )
    args = parser.parse_args(argv)
    if args.kerf < 0:
        parser.error("kerf must be >= 0")

    out = stdout or sys.stdout
    err = stderr or sys.stderr
    data = _load(args.input)
    plan = build_plan(data, args.kerf)
    print("unallocated:", list(plan.unallocated), file=err)

    if args.html:
        page = render_html(plan)
        if args.html == "-":
            out.write(page)
        else:
            with open(args.html, "w", encoding="utf-8") as handle:
                handle.write(page)
            print(f"wrote {args.html}", file=out)
        return 0

    out.write(render_tsv(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
