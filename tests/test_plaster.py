"""2D plasterboard planner tests.

example-plaster.json is a labelled fictional spare room, not a client job.
The timber CLI is only smoked here so this page cannot silently replace it.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import plaster  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def _job(kerf: int, available: list, desired: list, example: bool = False) -> dict:
    data = {"available": available, "desired": desired, "kerf_mm": kerf}
    if example:
        data["example"] = True
    return plaster.normalise_job(data)


def _js(job: dict, custom: bool = False) -> dict:
    proc = subprocess.run(
        ["node", str(ROOT / "tests/js_plaster.js")],
        input=json.dumps({"job": job, "custom": custom}),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout)


def _overlap(a: dict, b: dict) -> bool:
    return a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"] and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"]


def _assert_partition(test: unittest.TestCase, sheet: dict, kerf: int) -> None:
    rects: list[tuple[str, dict]] = []
    for placement in sheet["placements"]:
        rects.append(("panel", placement))
        test.assertGreater(placement["w"], 0)
        test.assertGreater(placement["h"], 0)
        test.assertLessEqual(placement["x"] + placement["w"], sheet["w"])
        test.assertLessEqual(placement["y"] + placement["h"], sheet["h"])
        test.assertGreaterEqual(placement["x"], 0)
        test.assertGreaterEqual(placement["y"], 0)
        if placement["rotated"]:
            test.assertEqual(placement["w"], placement["source_h"])
            test.assertEqual(placement["h"], placement["source_w"])
        else:
            test.assertEqual(placement["w"], placement["source_w"])
            test.assertEqual(placement["h"], placement["source_h"])
        if placement["grain"]:
            test.assertFalse(placement["rotated"])
    for band in sheet["kerf"]:
        rects.append(("kerf", band))
        test.assertTrue(band["w"] == kerf or band["h"] == kerf)
    for offcut in sheet["waste"]:
        rects.append(("waste", offcut))
        test.assertGreater(offcut["w"], 0)
        test.assertGreater(offcut["h"], 0)
    area = 0
    for kind, rect in rects:
        test.assertGreaterEqual(rect["x"], 0)
        test.assertGreaterEqual(rect["y"], 0)
        test.assertLessEqual(rect["x"] + rect["w"], sheet["w"])
        test.assertLessEqual(rect["y"] + rect["h"], sheet["h"])
        area += rect["w"] * rect["h"]
        del kind
    for index, (_, left) in enumerate(rects):
        for _, right in rects[index + 1 :]:
            test.assertFalse(_overlap(left, right), f"{left} overlaps {right} on sheet {sheet['index']}")
    test.assertEqual(area, sheet["w"] * sheet["h"])


class GeometryTests(unittest.TestCase):
    def test_vertical_split_when_leftover_is_narrower_than_it_is_short(self):
        job = _job(3, [[1, 100, 100]], [[1, 40, 30]])
        plan = plaster.pack_job(job)
        sheet = plan["sheets"][0]
        self.assertEqual(
            sheet["placements"],
            [
                {
                    "x": 0,
                    "y": 0,
                    "w": 40,
                    "h": 30,
                    "rotated": False,
                    "grain": False,
                    "source_w": 40,
                    "source_h": 30,
                }
            ],
        )
        self.assertEqual(
            sheet["kerf"],
            [{"x": 40, "y": 0, "w": 3, "h": 100}, {"x": 0, "y": 30, "w": 40, "h": 3}],
        )
        self.assertEqual(
            sheet["waste"],
            [{"x": 43, "y": 0, "w": 57, "h": 100}, {"x": 0, "y": 33, "w": 40, "h": 67}],
        )
        _assert_partition(self, sheet, 3)

    def test_horizontal_split_otherwise(self):
        job = _job(3, [[1, 100, 100]], [[1, 30, 40]])
        sheet = plaster.pack_job(job)["sheets"][0]
        self.assertEqual(
            sheet["kerf"],
            [{"x": 30, "y": 0, "w": 3, "h": 40}, {"x": 0, "y": 40, "w": 100, "h": 3}],
        )
        self.assertEqual(
            sheet["waste"],
            [{"x": 33, "y": 0, "w": 67, "h": 40}, {"x": 0, "y": 43, "w": 100, "h": 57}],
        )
        _assert_partition(self, sheet, 3)

    def test_kerf_three_refuses_a_pair_that_kerf_zero_cuts(self):
        available = [[1, 100, 100]]
        desired = [[2, 50, 100]]
        tight = plaster.pack_job(_job(3, available, desired))
        self.assertEqual(len(tight["sheets"][0]["placements"]), 1)
        self.assertEqual(tight["unplaced"], [{"w": 50, "h": 100, "grain": False}])
        _assert_partition(self, tight["sheets"][0], 3)
        loose = plaster.pack_job(_job(0, available, desired))
        self.assertEqual(len(loose["sheets"][0]["placements"]), 2)
        self.assertEqual(loose["unplaced"], [])
        self.assertEqual(loose["sheets"][0]["kerf"], [])
        _assert_partition(self, loose["sheets"][0], 0)

    def test_exact_kerf_strip_leaves_no_offcut(self):
        sheet = plaster.pack_job(_job(3, [[1, 100, 40]], [[1, 97, 40]]))["sheets"][0]
        self.assertEqual(sheet["placements"][0]["w"], 97)
        self.assertEqual(sheet["waste"], [])
        self.assertEqual(sheet["kerf"], [{"x": 97, "y": 0, "w": 3, "h": 40}])
        _assert_partition(self, sheet, 3)

    def test_sliver_thinner_than_kerf_is_not_a_placement(self):
        plan = plaster.pack_job(_job(3, [[1, 100, 40]], [[1, 98, 40]]))
        self.assertEqual(plan["sheets"][0]["placements"], [])
        self.assertEqual(plan["unplaced"], [{"w": 98, "h": 40, "grain": False}])

    def test_rotation_is_used_only_when_the_panel_allows_it(self):
        turned = plaster.pack_job(_job(0, [[1, 80, 30]], [[1, 30, 80, 0]]))
        self.assertEqual(turned["sheets"][0]["placements"][0]["rotated"], True)
        self.assertEqual(turned["sheets"][0]["placements"][0]["w"], 80)
        self.assertEqual(turned["sheets"][0]["placements"][0]["h"], 30)
        self.assertEqual(turned["unplaced"], [])
        locked = plaster.pack_job(_job(0, [[1, 80, 30]], [[1, 30, 80, 1]]))
        self.assertEqual(locked["sheets"][0]["placements"], [])
        self.assertEqual(locked["unplaced"], [{"w": 30, "h": 80, "grain": True}])
        self.assertFalse(locked["sheets"][0]["used"])

    def test_stock_sheets_are_not_turned(self):
        plan = plaster.pack_job(_job(0, [[1, 30, 80]], [[1, 80, 30]]))
        sheet = plan["sheets"][0]
        self.assertEqual((sheet["w"], sheet["h"]), (30, 80))
        self.assertTrue(sheet["placements"][0]["rotated"])
        self.assertEqual((sheet["placements"][0]["w"], sheet["placements"][0]["h"]), (30, 80))

    def test_smaller_free_rectangle_wins_over_a_larger_sheet(self):
        plan = plaster.pack_job(_job(0, [[1, 1000, 1000], [1, 100, 100]], [[1, 100, 100]]))
        self.assertFalse(plan["sheets"][0]["used"])
        self.assertTrue(plan["sheets"][1]["used"])
        self.assertEqual(plaster._groups_of_sheets(plan["sheets"], used=True), [(100, 100, 1)])

    def test_largest_longer_side_is_placed_first(self):
        plan = plaster.pack_job(_job(0, [[1, 100, 50]], [[1, 10, 10], [1, 100, 50]]))
        self.assertEqual(len(plan["sheets"][0]["placements"]), 1)
        self.assertEqual(plan["sheets"][0]["placements"][0]["source_w"], 100)
        self.assertEqual(plan["unplaced"], [{"w": 10, "h": 10, "grain": False}])

    def test_default_kerf_is_3_and_limits_are_named(self):
        job = plaster.normalise_job({"available": [[1, 10, 10]], "desired": []})
        self.assertEqual(job["kerf_mm"], plaster.DEFAULT_KERF_MM)
        self.assertEqual(plaster.DEFAULT_KERF_MM, 3)
        self.assertFalse(job["example"])
        with self.assertRaisesRegex(ValueError, "limit 80"):
            plaster.normalise_job({"available": [[81, 10, 10]], "desired": []})
        with self.assertRaisesRegex(ValueError, "limit 200"):
            plaster.normalise_job({"available": [], "desired": [[201, 10, 10]]})
        with self.assertRaises(ValueError):
            plaster.normalise_job({"available": [[True, 10, 10]], "desired": []})
        with self.assertRaises(ValueError):
            plaster.normalise_job({"kerf_mm": -1, "available": [], "desired": []})


class ExampleJobTests(unittest.TestCase):
    def setUp(self):
        self.job = plaster.normalise_job(_load("example-plaster.json"))
        self.plan = plaster.pack_job(self.job)

    def test_example_is_labelled_and_is_not_the_timber_job(self):
        raw = (ROOT / "example-plaster.json").read_text(encoding="utf-8")
        self.assertTrue(self.job["example"])
        self.assertTrue(self.job["fictional"])
        self.assertIn("FICTIONAL", self.job["title"])
        self.assertIn("fictional", self.job["story"].lower())
        self.assertIn("not a client job", self.job["story"])
        self.assertIn("two windows", self.job["story"].lower())
        self.assertIn("Skinny panels", self.job["story"])
        self.assertIn("Not a real bill of materials", self.job["note"])
        self.assertNotIn("5400", raw)
        self.assertNotIn("input.json", raw)
        self.assertEqual(self.job["kerf_mm"], 3)
        self.assertEqual([(row["w"], row["h"], row["count"]) for row in self.job["available"]], [(1200, 2700, 11), (1200, 2400, 8)])
        self.assertEqual(len(self.job["desired"]), 46)
        openings = self.job["room"]["openings"]
        self.assertEqual([item["name"] for item in openings], ["Door", "Big window", "Small window"])
        self.assertNotEqual(openings[1]["w"] * openings[1]["h"], openings[2]["w"] * openings[2]["h"])
        names = " ".join(row["name"] for row in self.job["desired"])
        self.assertIn("Lintel", names)
        self.assertIn("Sill piece", names)
        self.assertIn("Side fill", names)
        self.assertTrue(any(row["w"] <= 200 for row in self.job["desired"]))
        for row in self.job["desired"]:
            self.assertEqual(row["count"], 1)
            self.assertTrue(row["face"])
            self.assertTrue(row["name"])
            self.assertGreaterEqual(row["u"], 0)
            self.assertGreaterEqual(row["v"], 0)

    def test_every_sheet_is_a_partition_and_pieces_are_counted_once(self):
        desired = []
        for row in self.job["desired"]:
            for _ in range(row["count"]):
                desired.append((row["w"], row["h"], row["grain"]))
        placed = []
        for sheet in self.plan["sheets"]:
            _assert_partition(self, sheet, 3)
            for placement in sheet["placements"]:
                placed.append((placement["source_w"], placement["source_h"], placement["grain"]))
        missing = [(panel["w"], panel["h"], panel["grain"]) for panel in self.plan["unplaced"]]
        self.assertEqual(sorted(placed + missing), sorted(desired))
        self.assertEqual(self.plan["unplaced"], [])

    def _face_rows(self):
        grouped = {}
        for row in self.job["desired"]:
            grouped.setdefault(row["face"], []).append(row)
        return grouped

    def test_room_faces_cover_their_area_and_leave_the_openings(self):
        grouped = self._face_rows()
        expected = {
            "east": 3000 * 2700 - 700 * 800,
            "south": 3600 * 2700 - 820 * 2040,
            "west": 1800 * 2700,
            "robeFront": 1200 * 2700,
            "robeSouth": 600 * 2700,
            "robeNorth": 600 * 2700,
            "north": 3600 * 2400 - 1200 * 1100,
            "ceiling": 3600 * 2500 - 600 * 1200,
            "soffit": 3600 * 500,
            "bulkhead": 3600 * 300,
            "doorWestJamb": 90 * 2040,
            "doorEastJamb": 90 * 2040,
            "doorHead": 820 * 90,
            "winLeft": 100 * 1100,
            "winRight": 100 * 1100,
            "winSill": 1200 * 100,
            "winHead": 1200 * 100,
            "win2Left": 100 * 800,
            "win2Right": 100 * 800,
            "win2Sill": 700 * 100,
            "win2Head": 700 * 100,
        }
        self.assertEqual(set(grouped), set(expected))

        def covers(rows, hole):
            hu, hv, hw, hh = hole
            for row in rows:
                if row["u"] < hu + hw and hu < row["u"] + row["w"] and row["v"] < hv + hh and hv < row["v"] + row["h"]:
                    return True
            return False

        for face, rows in grouped.items():
            area = 0
            for index, row in enumerate(rows):
                area += row["w"] * row["h"]
                for other in rows[index + 1 :]:
                    self.assertFalse(
                        row["u"] < other["u"] + other["w"]
                        and other["u"] < row["u"] + row["w"]
                        and row["v"] < other["v"] + other["h"]
                        and other["v"] < row["v"] + row["h"],
                        f"{face} pieces overlap",
                    )
            self.assertEqual(area, expected[face], face)
        self.assertFalse(covers(grouped["south"], (1680, 0, 820, 2040)))
        self.assertFalse(covers(grouped["north"], (180, 800, 1200, 1100)))
        self.assertFalse(covers(grouped["east"], (1500, 1100, 700, 800)))

    def test_example_pull_leave_and_a_turned_panel(self):
        self.assertEqual(
            plaster._groups_of_sheets(self.plan["sheets"], used=True),
            [(1200, 2700, 9), (1200, 2400, 8)],
        )
        self.assertEqual(
            plaster._groups_of_sheets(self.plan["sheets"], used=False),
            [(1200, 2700, 2)],
        )
        placed = [panel for sheet in self.plan["sheets"] for panel in sheet["placements"]]
        self.assertTrue(any(panel["rotated"] for panel in placed))
        self.assertTrue(any(panel["grain"] and not panel["rotated"] for panel in placed))
        ids = [panel["id"] for panel in placed]
        self.assertEqual(sorted(ids), list(range(len(ids))))
        text = plaster.render_shop_text(self.plan, self.job)
        self.assertIn("EXAMPLE / FICTIONAL — not a real job", text)
        self.assertIn("not a client job", text)
        self.assertIn("9 x 1200 x 2700 mm (3.240 m2 each)", text)
        self.assertIn("8 x 1200 x 2400 mm (2.880 m2 each)", text)
        self.assertIn("Total: 17 sheets, 52.200 m2", text)
        self.assertIn("Skinny panels", text)
        self.assertIn("DOES NOT FIT\nnone", text)
        self.assertIn("face locked", text)
        self.assertIn("turned (entered", text)

    def test_browser_cutter_matches_python_on_the_example_and_the_fixtures(self):
        cases = [
            self.job,
            _job(3, [[1, 100, 100]], [[2, 50, 100]]),
            _job(0, [[1, 100, 100]], [[2, 50, 100]]),
            _job(0, [[1, 80, 30]], [[1, 30, 80, 1]]),
            _job(0, [[1, 1000, 1000], [1, 100, 100]], [[1, 100, 100]]),
            _job(3, [[1, 100, 100]], [[1, 40, 30]]),
        ]
        for job in cases:
            plan = plaster.pack_job(job)
            got = _js(job)
            self.assertEqual(got["plan"]["sheets"], plan["sheets"])
            self.assertEqual(got["plan"]["unplaced"], plan["unplaced"])
            self.assertEqual(got["text"], plaster.render_shop_text(plan, job))
        custom = _js(self.job, custom=True)
        self.assertIn("CUSTOM SIZES — edited on this phone, not a real job", custom["text"])
        self.assertNotIn("EXAMPLE / FICTIONAL", custom["text"])
        self.assertNotIn(self.job["story"], custom["text"])


class PageTests(unittest.TestCase):
    def test_checked_in_page_matches_the_generator(self):
        job = plaster.normalise_job(_load("example-plaster.json"))
        html = plaster.render_html(job)
        checked = ROOT / "docs" / "plaster-cut-plan.html"
        self.assertEqual(checked.read_text(encoding="utf-8"), html)
        self.assertIn("EXAMPLE / FICTIONAL", html)
        self.assertIn("wardrobe", html)
        self.assertIn("bulkhead", html)
        self.assertIn("different sizes", html)
        self.assertIn("Skinny panels", html)
        self.assertIn("room-opening", html)
        self.assertIn("Room preview", html)
        self.assertIn('id="room-view"', html)
        self.assertIn("guillotine best-area fit", html)
        self.assertIn("kerf_mm", html)
        self.assertIn("Face direction locked", html)
        self.assertNotIn("__SAMPLE_JOB__", html)
        self.assertNotIn("__EDITOR_JS__", html)
        self.assertNotIn("__STORY__", html)
        self.assertIn("function packJob", html)

    def test_cli_writes_the_list_and_rejects_a_bad_job(self):
        proc = subprocess.run(
            [sys.executable, "plaster.py", "example-plaster.json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertTrue(proc.stdout.startswith("PLANKER PLASTERBOARD\n"))
        self.assertIn("EXAMPLE / FICTIONAL — not a real job", proc.stdout)
        self.assertIn("DOES NOT FIT\nnone", proc.stdout)
        self.assertEqual(proc.stderr, "")
        bad = subprocess.run(
            [sys.executable, "plaster.py", "--kerf", "-1", "example-plaster.json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertEqual(bad.returncode, 2)
        self.assertIn("kerf", bad.stderr)

    def test_timber_cli_still_runs(self):
        proc = subprocess.run(
            [sys.executable, "planker.py"],
            cwd=ROOT,
            input=(ROOT / "input.json").read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertTrue(proc.stdout.startswith("allocated\tleftover\tcuts\n"))
        self.assertIn("unallocated:", proc.stderr)


if __name__ == "__main__":
    unittest.main()
