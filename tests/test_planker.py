"""Allocation and shop-sheet tests.

``input.json`` and ``tests/fixtures/input.tsv`` are the real sample job.
Anything under a SYNTHETIC name is an arbitrary fixture, not stock to buy.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import planker  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


class SampleJobTests(unittest.TestCase):
    def setUp(self):
        self.data = _load("input.json")
        self.plan = planker.build_plan(self.data, planker.KERF_MM)

    def test_tsv_matches_the_original_greedy_paste(self):
        expected = (ROOT / "tests/fixtures/input.tsv").read_text(encoding="utf-8")
        self.assertEqual(planker.render_tsv(self.plan), expected)

    def test_every_board_accounts_for_kerf(self):
        self.assertGreaterEqual(len(self.plan.boards), 1)
        for board in self.plan.boards:
            self.assertTrue(
                board.consistent(planker.KERF_MM),
                f"board {board.index} stock={board.stock_mm} cuts={board.cuts} "
                f"leftover={board.tsv_leftover_mm}",
            )

    def test_pieces_are_placed_or_listed_once(self):
        desired = []
        for count, length in self.data["desired"]:
            desired.extend([length] * count)
        placed = [cut for board in self.plan.boards for cut in board.cuts]
        self.assertEqual(sorted(placed + list(self.plan.unallocated)), sorted(desired))

    def test_sample_pull_and_leave_lists(self):
        self.assertEqual(self.plan.pull_counts(), ((5400, 9), (3835, 1), (3830, 2), (3820, 1)))
        self.assertEqual(self.plan.leave_counts(), ((5400, 2),))
        self.assertEqual(self.plan.unallocated, ())
        text = planker.render_lumber_text(self.plan)
        self.assertIn("9 x 5400 mm (5.400 m)", text)
        self.assertIn("1 x 3835 mm (3.835 m)", text)
        self.assertIn("2 x 3830 mm (3.830 m)", text)
        self.assertIn("1 x 3820 mm (3.820 m)", text)
        self.assertIn("Total: 13 boards, 63915 mm (63.915 m)", text)
        self.assertIn("2 x 5400 mm (5.400 m)", text)
        self.assertIn("DOES NOT FIT\nnone\n", text)

    def test_offcut_notes_use_piece_lengths_from_the_job(self):
        lengths = [length for length, _ in self.plan.project_counts()]
        self.assertEqual(
            planker.describe_offcut(270, lengths),
            "long enough for 200 mm, shorter than 280 mm",
        )
        self.assertEqual(
            planker.describe_offcut(11, lengths),
            "too short for a 200 mm piece, the shortest on this job",
        )
        leftovers = {
            board.physical_leftover_mm(planker.KERF_MM)
            for board in self.plan.boards
            if board.used
        }
        self.assertIn(270, leftovers)
        self.assertIn(11, leftovers)

    def test_cli_stdout_and_stderr_for_the_sample(self):
        proc = subprocess.run(
            [sys.executable, "planker.py", "input.json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        expected = (ROOT / "tests/fixtures/input.tsv").read_text(encoding="utf-8")
        self.assertEqual(proc.stdout, expected)
        self.assertEqual(proc.stderr, "unallocated: []\n")

    def test_stdin_tsv_still_works(self):
        proc = subprocess.run(
            [sys.executable, "planker.py"],
            cwd=ROOT,
            input=(ROOT / "input.json").read_text(encoding="utf-8"),
            text=True,
            capture_output=True,
            check=True,
        )
        expected = (ROOT / "tests/fixtures/input.tsv").read_text(encoding="utf-8")
        self.assertEqual(proc.stdout, expected)

    def test_checked_in_page_matches_the_renderer(self):
        page = planker.render_html(self.plan)
        saved = (ROOT / "docs/cut-plan.html").read_text(encoding="utf-8")
        self.assertEqual(saved, page)
        self.assertIn("9 x 5400 mm (5.400 m)", page)
        self.assertIn("1,430 + 1,320 + 1,320 + 1,310 + kerf 9 + offcut 11 = 5,400", page)
        self.assertIn("spreadsheet leftover 5,403", page)
        self.assertIn("Every desired piece is on a board", page)
        self.assertIn("Project: 62 pieces, 62,276 mm", page)
        self.assertIn("5 rows, 15 boards", page)
        self.assertIn("25 rows, 62 pieces", page)
        self.assertNotIn("does not choose a board to buy", page)


class SyntheticTests(unittest.TestCase):
    def test_shortfall_keeps_the_real_piece_length(self):
        data = json.loads(
            (ROOT / "tests/fixtures/synthetic_shortfall.json").read_text(encoding="utf-8")
        )
        self.assertIn("SYNTHETIC", data["note"])
        plan = planker.build_plan(data, planker.KERF_MM)
        self.assertEqual(plan.unallocated, (500,))
        self.assertEqual(plan.pull_counts(), ((1000, 2),))
        self.assertEqual(plan.leave_counts(), ())
        for board in plan.boards:
            self.assertTrue(board.consistent(planker.KERF_MM))
        page = planker.render_html(plan)
        self.assertIn("1 × 500 mm", page)
        self.assertIn("does not choose a board to buy", page)
        self.assertNotIn("503", page)

    def test_kerf_changes_whether_the_second_piece_fits(self):
        # SYNTHETIC lengths, not a bill of materials.
        data = {"available": [[1, 1000]], "desired": [[2, 500]]}
        with_kerf = planker.build_plan(data, 3)
        no_kerf = planker.build_plan(data, 0)
        self.assertEqual(with_kerf.unallocated, (500,))
        self.assertEqual([board.cuts for board in with_kerf.boards], [(500,)])
        self.assertEqual(no_kerf.unallocated, ())
        self.assertEqual([board.cuts for board in no_kerf.boards], [(500, 500)])
        self.assertEqual(no_kerf.boards[0].physical_leftover_mm(0), 0)

    def test_html_flag_writes_a_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "plan.html"
            proc = subprocess.run(
                [sys.executable, "planker.py", "--html", str(dest), "input.json"],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertEqual(proc.stdout, f"wrote {dest}\n")
            self.assertEqual(proc.stderr, "unallocated: []\n")
            self.assertIn("Lumber-yard list", dest.read_text(encoding="utf-8"))

    def test_negative_kerf_is_rejected(self):
        proc = subprocess.run(
            [sys.executable, "planker.py", "--kerf", "-1", "input.json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("kerf must be >= 0", proc.stderr)


if __name__ == "__main__":
    unittest.main()
