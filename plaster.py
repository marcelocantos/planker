#!/usr/bin/env python3
"""2D plasterboard sheet planner.

This is a separate path from the 1D timber cutter in planker.py. It does not
read input.json and it does not change that tool.

Packing is guillotine best-area fit with a shorter-leftover split. It is not
an exact optimum.

- Panels are considered largest longer-side first, then larger area, then
  larger shorter-side, then input order.
- A panel may be turned 90 degrees unless face direction is locked (grain).
  Stock sheets are not turned. Width is across the sheet; height runs down
  the drawing.
- The panel is placed in the free rectangle that leaves the smallest offcut
  area. Ties prefer a sheet that already has a panel, then an unturned
  panel, then the earlier sheet, then the upper free rectangle, then the
  left one.
- The leftover of that rectangle is split with one through-cut. If the
  leftover width is strictly less than the leftover height, the cut runs the
  full height of the rectangle (the right offcut keeps that full height, and
  the bottom offcut is only as wide as the panel). Otherwise the cut runs
  the full width.
- Saw kerf (setting kerf_mm, default 3) is a strip taken out of each
  through-cut that has a leftover. A leftover thinner than the kerf is
  refused: the panel is not placed in that rectangle. Kerf 0 is
  score-and-snap, which removes no strip. A panel that lands flush with an
  edge has no kerf on that edge.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

DEFAULT_KERF_MM = 3
LIMIT_SHEETS = 80
LIMIT_PANELS = 200
LIMIT_MM = 20000

ERR_SHEETS = "Too many sheets to lay out here (limit 80)."
ERR_PANELS = "Too many panels to lay out here (limit 200)."
ERR_MM = "Width and height must be from 1 to 20000 mm."
ERR_COUNT = "Counts must be positive integers."
ERR_KERF = "Saw kerf must be a whole number of millimetres, 0 or more."


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return value


def _as_bool(value: object, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{name} must be true or false")


def _sheet_row(row: object) -> tuple[int, int, int]:
    if isinstance(row, dict):
        count = _as_int(row["count"], "count")
        width = _as_int(row["w"], "w")
        height = _as_int(row["h"], "h")
    elif isinstance(row, (list, tuple)) and len(row) == 3:
        count = _as_int(row[0], "count")
        width = _as_int(row[1], "w")
        height = _as_int(row[2], "h")
    else:
        raise ValueError("each stock sheet is count, width, height")
    if count < 1:
        raise ValueError(ERR_COUNT)
    if width < 1 or height < 1 or width > LIMIT_MM or height > LIMIT_MM:
        raise ValueError(ERR_MM)
    return count, width, height


def _panel_place(row: dict) -> dict | None:
    if "face" not in row:
        return None
    face = row["face"]
    name = row.get("name") or face
    if not isinstance(face, str) or not face or not isinstance(name, str):
        raise ValueError("face and name must be text")
    u = _as_int(row["u"], "u")
    v = _as_int(row["v"], "v")
    if u < 0 or v < 0:
        raise ValueError("u and v must be >= 0")
    return {"face": face, "name": name, "u": u, "v": v}


def _panel_row(row: object) -> tuple[int, int, int, bool, dict | None]:
    place = None
    if isinstance(row, dict):
        count = _as_int(row["count"], "count")
        width = _as_int(row["w"], "w")
        height = _as_int(row["h"], "h")
        grain = _as_bool(row.get("grain", False), "grain")
        place = _panel_place(row)
    elif isinstance(row, (list, tuple)) and len(row) in (3, 4):
        count = _as_int(row[0], "count")
        width = _as_int(row[1], "w")
        height = _as_int(row[2], "h")
        grain = _as_bool(row[3], "grain") if len(row) == 4 else False
    else:
        raise ValueError("each panel is count, width, height, and optional face lock")
    if count < 1:
        raise ValueError(ERR_COUNT)
    if place and count != 1:
        raise ValueError("a panel fixed on a room face has count 1")
    if width < 1 or height < 1 or width > LIMIT_MM or height > LIMIT_MM:
        raise ValueError(ERR_MM)
    return count, width, height, grain, place


def normalise_job(data: object, kerf_override: int | None = None) -> dict:
    """Return a job dict with kerf_mm, available, and desired filled in."""
    if not isinstance(data, dict):
        raise ValueError("job must be a JSON object")
    if "available" not in data or "desired" not in data:
        raise ValueError("job needs available and desired")
    if kerf_override is not None:
        kerf = kerf_override
    elif "kerf_mm" in data:
        kerf = _as_int(data["kerf_mm"], "kerf_mm")
    elif "kerf" in data:
        kerf = _as_int(data["kerf"], "kerf")
    else:
        kerf = DEFAULT_KERF_MM
    if isinstance(kerf, bool) or not isinstance(kerf, int) or kerf < 0 or kerf > LIMIT_MM:
        raise ValueError(ERR_KERF)
    available = [_sheet_row(row) for row in data["available"]]
    desired = [_panel_row(row) for row in data["desired"]]
    sheet_n = sum(count for count, _, _ in available)
    panel_n = sum(count for count, _, _, _, _ in desired)
    if sheet_n > LIMIT_SHEETS:
        raise ValueError(ERR_SHEETS)
    if panel_n > LIMIT_PANELS:
        raise ValueError(ERR_PANELS)
    title = data.get("title") or "Plasterboard cut plan"
    note = data.get("note") or ""
    story = data.get("story") or ""
    if not isinstance(title, str) or not isinstance(note, str) or not isinstance(story, str):
        raise ValueError("title, note, and story must be text")
    job = {
        "example": bool(data.get("example")),
        "fictional": bool(data.get("fictional")),
        "title": title,
        "note": note,
        "story": story,
        "kerf_mm": kerf,
        "available": [{"count": count, "w": width, "h": height} for count, width, height in available],
        "desired": [],
    }
    if isinstance(data.get("room"), dict):
        job["room"] = data["room"]
    for count, width, height, grain, place in desired:
        item = {"count": count, "w": width, "h": height, "grain": grain}
        if place:
            item.update(place)
        job["desired"].append(item)
    return job


def _rect(x: int, y: int, w: int, h: int) -> dict:
    return {"x": x, "y": y, "w": w, "h": h}


def _sorted_rects(rects: list[dict]) -> list[dict]:
    return sorted(rects, key=lambda item: (item["y"], item["x"], item["w"], item["h"]))


def _fits(free: dict, pw: int, ph: int, kerf: int) -> bool:
    if pw > free["w"] or ph > free["h"]:
        return False
    leftover_w = free["w"] - pw
    leftover_h = free["h"] - ph
    if leftover_w > 0 and leftover_w < kerf:
        return False
    if leftover_h > 0 and leftover_h < kerf:
        return False
    return True


def _split(free: dict, pw: int, ph: int, kerf: int) -> tuple[list[dict], list[dict]]:
    """Guillotine split of free after placing a pw by ph panel at its origin."""
    leftover_w = free["w"] - pw
    leftover_h = free["h"] - ph
    kerfs: list[dict] = []
    frees: list[dict] = []

    def band(length: int) -> tuple[int, int]:
        if length <= 0:
            return 0, 0
        return kerf, length - kerf

    if leftover_w < leftover_h:
        kerf_w, rest_w = band(leftover_w)
        kerf_h, rest_h = band(leftover_h)
        if kerf_w:
            kerfs.append(_rect(free["x"] + pw, free["y"], kerf_w, free["h"]))
        if rest_w:
            frees.append(_rect(free["x"] + pw + kerf_w, free["y"], rest_w, free["h"]))
        if kerf_h:
            kerfs.append(_rect(free["x"], free["y"] + ph, pw, kerf_h))
        if rest_h:
            frees.append(_rect(free["x"], free["y"] + ph + kerf_h, pw, rest_h))
    else:
        kerf_w, rest_w = band(leftover_w)
        kerf_h, rest_h = band(leftover_h)
        if kerf_h:
            kerfs.append(_rect(free["x"], free["y"] + ph, free["w"], kerf_h))
        if rest_h:
            frees.append(_rect(free["x"], free["y"] + ph + kerf_h, free["w"], rest_h))
        if kerf_w:
            kerfs.append(_rect(free["x"] + pw, free["y"], kerf_w, ph))
        if rest_w:
            frees.append(_rect(free["x"] + pw + kerf_w, free["y"], rest_w, ph))
    return kerfs, frees


def _orientations(panel: dict) -> list[tuple[bool, int, int]]:
    options = [(False, panel["w"], panel["h"])]
    if not panel["grain"] and panel["w"] != panel["h"]:
        options.append((True, panel["h"], panel["w"]))
    return options


def pack_job(job: dict) -> dict:
    """Pack a normalised job. Sheets keep stock order, indexes starting at 1."""
    kerf = job["kerf_mm"]
    sheets: list[dict] = []
    index = 1
    for row in job["available"]:
        for _ in range(row["count"]):
            sheets.append(
                {
                    "index": index,
                    "w": row["w"],
                    "h": row["h"],
                    "placements": [],
                    "kerf": [],
                    "free": [_rect(0, 0, row["w"], row["h"])],
                }
            )
            index += 1

    panels: list[dict] = []
    piece_i = 0
    for row in job["desired"]:
        for _ in range(row["count"]):
            panel = {"w": row["w"], "h": row["h"], "grain": row["grain"], "i": piece_i}
            if row.get("face"):
                panel["face"] = row["face"]
                panel["name"] = row.get("name") or row["face"]
                panel["u"] = row["u"]
                panel["v"] = row["v"]
            panels.append(panel)
            piece_i += 1
    panels.sort(
        key=lambda panel: (
            -max(panel["w"], panel["h"]),
            -(panel["w"] * panel["h"]),
            -min(panel["w"], panel["h"]),
            panel["i"],
        )
    )

    unplaced: list[dict] = []
    for panel in panels:
        best: tuple | None = None
        for sheet_i, sheet in enumerate(sheets):
            for free_i, free in enumerate(sheet["free"]):
                for rotated, pw, ph in _orientations(panel):
                    if not _fits(free, pw, ph, kerf):
                        continue
                    score = (
                        free["w"] * free["h"] - pw * ph,
                        0 if sheet["placements"] else 1,
                        1 if rotated else 0,
                        sheet_i,
                        free["y"],
                        free["x"],
                    )
                    if best is None or score < best[0]:
                        best = (score, sheet_i, free_i, pw, ph, rotated)
        if best is None:
            unplaced.append(_piece_record(panel, None))
            continue
        _, sheet_i, free_i, pw, ph, rotated = best
        sheet = sheets[sheet_i]
        free = sheet["free"].pop(free_i)
        kerfs, frees = _split(free, pw, ph, kerf)
        sheet["kerf"].extend(kerfs)
        sheet["free"].extend(frees)
        placed = {
            "x": free["x"],
            "y": free["y"],
            "w": pw,
            "h": ph,
            "rotated": rotated,
            "grain": panel["grain"],
            "source_w": panel["w"],
            "source_h": panel["h"],
        }
        placed.update(_piece_record(panel, placed=True))
        sheet["placements"].append(placed)

    public_sheets = []
    for sheet in sheets:
        public_sheets.append(
            {
                "index": sheet["index"],
                "w": sheet["w"],
                "h": sheet["h"],
                "used": bool(sheet["placements"]),
                "placements": sheet["placements"],
                "kerf": _sorted_rects(sheet["kerf"]),
                "waste": _sorted_rects(sheet["free"]),
            }
        )
    return {"kerf_mm": kerf, "sheets": public_sheets, "unplaced": unplaced}


def _piece_record(panel: dict, placed: bool | None) -> dict:
    """Room identity carried onto a placement. Omitted when the piece has no face."""
    if not panel.get("face"):
        if placed:
            return {}
        return {"w": panel["w"], "h": panel["h"], "grain": panel["grain"]}
    record = {
        "id": panel["i"],
        "face": panel["face"],
        "name": panel["name"],
        "u": panel["u"],
        "v": panel["v"],
    }
    if placed:
        return record
    record["w"] = panel["w"]
    record["h"] = panel["h"]
    record["grain"] = panel["grain"]
    return record


def _commas(value: int) -> str:
    return f"{value:,}"


def area_m2(mm2: int) -> str:
    whole, frac = divmod(mm2, 1_000_000)
    milli = frac // 1_000
    return f"{whole}.{milli:03d} m2"


def _groups_of_sheets(sheets: list[dict], used: bool) -> list[tuple[int, int, int]]:
    order: list[tuple[int, int]] = []
    counts: dict[tuple[int, int], int] = {}
    for sheet in sheets:
        if sheet["used"] != used:
            continue
        key = (sheet["w"], sheet["h"])
        if key not in counts:
            order.append(key)
            counts[key] = 0
        counts[key] += 1
    return [(width, height, counts[(width, height)]) for width, height in order]


def _groups_of_panels(panels: list[dict]) -> list[tuple[int, int, bool, int]]:
    order: list[tuple[int, int, bool]] = []
    counts: dict[tuple[int, int, bool], int] = {}
    for panel in panels:
        key = (panel["w"], panel["h"], panel["grain"])
        if key not in counts:
            order.append(key)
            counts[key] = 0
        counts[key] += 1
    return [(width, height, grain, counts[(width, height, grain)]) for width, height, grain in order]


def _equation(sheet: dict) -> str:
    panel = sum(item["w"] * item["h"] for item in sheet["placements"])
    kerf = sum(item["w"] * item["h"] for item in sheet["kerf"])
    waste = sum(item["w"] * item["h"] for item in sheet["waste"])
    total = sheet["w"] * sheet["h"]
    return (
        f"{_commas(panel)} + kerf {_commas(kerf)} + offcut {_commas(waste)} = {_commas(total)} mm2"
    )


def render_shop_text(plan: dict, job: dict, custom: bool = False) -> str:
    """Plain-text yard list. custom=True marks phone edits of the example."""
    if custom:
        banner = "CUSTOM SIZES — edited on this phone, not a real job"
    elif job.get("fictional"):
        banner = "EXAMPLE / FICTIONAL — not a real job"
    elif job.get("example"):
        banner = "EXAMPLE — synthetic job, not a real bill of materials"
    else:
        banner = "Plasterboard job"
    lines = [
        "PLANKER PLASTERBOARD",
        banner,
    ]
    if job.get("story") and not custom:
        lines.append(job["story"])
    lines.extend(
        [
            f"Saw kerf: {job['kerf_mm']} mm (setting kerf_mm). 0 mm is score-and-snap.",
            "Packing: guillotine best-area fit, shorter-leftover split. Not an exact optimum.",
            "",
            "PULL",
        ]
    )
    pulls = _groups_of_sheets(plan["sheets"], used=True)
    if pulls:
        total_n = 0
        total_area = 0
        for width, height, count in pulls:
            lines.append(f"{count} x {width} x {height} mm ({area_m2(width * height)} each)")
            total_n += count
            total_area += count * width * height
        lines.append(f"Total: {total_n} sheets, {area_m2(total_area)}")
    else:
        lines.append("none")

    lines.extend(["", "LEAVE"])
    leaves = _groups_of_sheets(plan["sheets"], used=False)
    if leaves:
        for width, height, count in leaves:
            lines.append(f"{count} x {width} x {height} mm ({area_m2(width * height)} each)")
    else:
        lines.append("none")

    lines.extend(["", "DOES NOT FIT"])
    if plan["unplaced"]:
        for width, height, grain, count in _groups_of_panels(plan["unplaced"]):
            lock = "face locked" if grain else "turns allowed"
            lines.append(f"{count} x {width} x {height} mm ({lock})")
        lines.append("These are panel sizes that did not fit. This list does not add a sheet to buy.")
    else:
        lines.append("none")

    lines.extend(["", "CUTS"])
    used = [sheet for sheet in plan["sheets"] if sheet["used"]]
    if not used:
        lines.append("none")
    for sheet in used:
        lines.append(f"Sheet {sheet['index']} — {sheet['w']} x {sheet['h']} mm")
        for piece_i, placement in enumerate(sheet["placements"], start=1):
            extra = ""
            if placement["rotated"]:
                extra = f" turned (entered {placement['source_w']} x {placement['source_h']})"
            elif placement["grain"]:
                extra = " face locked"
            lines.append(
                f"  {piece_i}. {placement['w']} x {placement['h']} at {placement['x']},{placement['y']}{extra}"
            )
        for offcut in sheet["waste"]:
            lines.append(
                f"  offcut {offcut['w']} x {offcut['h']} at {offcut['x']},{offcut['y']}"
            )
        if job["kerf_mm"] and sheet["kerf"]:
            kerf_area = sum(item["w"] * item["h"] for item in sheet["kerf"])
            lines.append(f"  kerf {job['kerf_mm']} mm, {area_m2(kerf_area)}")
        lines.append(f"  {_equation(sheet)}")
    lines.append("")
    return "\n".join(lines)


def render_html(job: dict) -> str:
    """One offline HTML file: the job is embedded and the cutter runs in the page."""
    sample = json.dumps(job, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    script = (ROOT / "plaster_editor.js").read_text(encoding="utf-8").replace("__SAMPLE_JOB__", sample)
    story = (
        job.get("story")
        or "EXAMPLE / FICTIONAL. This room is made up. It is not a real job."
    )
    story_html = (
        story.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    page = (
        (ROOT / "plaster_page.html")
        .read_text(encoding="utf-8")
        .replace("__EDITOR_JS__", script)
        .replace("__STORY__", story_html)
    )
    if "__SAMPLE_JOB__" in page or "__EDITOR_JS__" in page or "__STORY__" in page:
        raise RuntimeError("template placeholders left in the page")
    if not page.endswith("\n"):
        page += "\n"
    return page


def load_job(path: str | None, kerf_override: int | None) -> dict:
    if path:
        text = Path(path).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    return normalise_job(json.loads(text), kerf_override=kerf_override)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Plan rectangular plasterboard cuts on stock sheets."
    )
    parser.add_argument("job", nargs="?", help="JSON job file. Reads stdin when omitted.")
    parser.add_argument(
        "--html",
        metavar="PATH",
        help="Write a self-contained HTML shop sheet. Use - for stdout.",
    )
    parser.add_argument(
        "--kerf",
        type=int,
        default=None,
        help=f"Override kerf_mm. Default {DEFAULT_KERF_MM} when the job omits it. 0 is score-and-snap.",
    )
    args = parser.parse_args(argv)
    try:
        job = load_job(args.job, args.kerf)
        plan = pack_job(job)
        html = render_html(job) if args.html else ""
    except (ValueError, json.JSONDecodeError, OSError, KeyError) as exc:
        print(f"plaster: {exc}", file=sys.stderr)
        return 2
    if args.html == "-":
        sys.stdout.write(html)
        return 0
    if args.html:
        Path(args.html).write_text(html, encoding="utf-8")
    sys.stdout.write(render_shop_text(plan, job))
    return 0


if __name__ == "__main__":
    sys.exit(main())
