# Planker

Small CLI that cuts available plank lengths into the pieces a job needs.
The cutter is greedy best-fit: each desired piece, longest first, goes on
the stock board with the smallest leftover that still fits. Saw kerf is
3 mm between cuts on the same board (not after the last cut).

Lengths are integer millimetres. `input.json` is the sample job — those
counts and lengths are the real bill of materials.

## Printable cut plan and lumber-yard list

```bash
python3 planker.py --html docs/cut-plan.html input.json
```

Open `docs/cut-plan.html` in a browser. The page has:

- a lumber-yard list — boards to pull, boards on hand that this plan does not cut, and any desired piece that did not fit (those are piece lengths, not a board to order)
- available stock and project pieces, as entered, so you can check them before cutting
- each board drawn to scale, with kerf, offcut, and the arithmetic that adds back to the stock length

Print from the browser (there is a Print button, or Ctrl/Cmd+P). Copy the
plain-text lumber list from the top of the page if you want it in a note.
A page already rendered from `input.json` is checked in at
[`docs/cut-plan.html`](docs/cut-plan.html).

`--html -` writes the page to stdout. `--kerf MM` changes the saw kerf
(default 3). The same flag is used for the spreadsheet output below.

```bash
python3 planker.py --html - input.json > cut-plan.html
python3 planker.py --kerf 3 --html docs/cut-plan.html < input.json
```

## Spreadsheet paste

```bash
python3 planker.py < input.json
```

Stdout is TSV: stock length, leftover millimetres, then each cut. Paste
that into the Plank cuts sheet. Unallocated piece lengths are printed on
stderr (the piece length, without kerf added).

An unused board's leftover cell is `stock + kerf` (5403 for a 5400 mm
board that is not cut). That is the cutter's starting figure, not an
offcut. The HTML page shows that board as left whole.

```bash
python3 planker.py input.json | pbcopy
open 'https://docs.google.com/spreadsheets/d/1xOtPt0CwiL2-eQyeWxo1ROeBID4Hba62ZC9iWFdcyt4/edit?gid=714141135#gid=714141135'
```

## Tests

From the repository root:

```bash
python3 -m unittest discover -s tests -v
```

## Input

Each field is a list of `[count, length_mm]` pairs. The sample job starts:

```json
{
  "available": [[11, 5400], [1, 3835]],
  "desired": [[5, 1800], [4, 1310]]
}
```

That is an excerpt of `input.json`, not the whole job. Run the full file.
