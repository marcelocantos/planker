# Planker

Small CLI that cuts available plank lengths into the pieces a job needs.
The cutter is greedy best-fit: each desired piece, longest first, goes on
the stock board with the smallest leftover that still fits. Saw kerf is
3 mm between cuts on the same board (not after the last cut).

Lengths are integer millimetres. `input.json` is the sample job — those
counts and lengths are the real bill of materials.

## On a phone or iPad

The cut plan is one self-contained HTML file. It works offline in Safari
or Chrome. Nothing to install, and nothing to type at the yard: the
lengths come from the JSON you already have.

```bash
python3 planker.py --html docs/cut-plan.html input.json
```

Get `docs/cut-plan.html` onto the device, then open it:

- **iPhone or iPad:** AirDrop the file, or save it to Files. Tap it and
  choose Safari (or Chrome). From Files you can also tap Share → Open in
  Safari.
- **Android:** copy the file onto the phone and open it in Chrome.

The lumber list is the first screen. Tick a row as you pull that board.
The bar at the bottom is sized for a thumb:

- **Share** sends the plain-text list (Messages, Mail, WhatsApp, AirDrop).
- **Copy** puts that same list on the clipboard.
- **Print** opens the system print sheet (AirPrint, or save a PDF).

Turn the phone sideways if you want a wider cut diagram. On an iPad in
landscape the bars sit beside the board number. A page already rendered
from `input.json` is checked in at
[`docs/cut-plan.html`](docs/cut-plan.html).

The page shows:

- boards to pull, boards on hand that this plan does not cut, and any
  desired piece that did not fit (those are piece lengths, not a board to order)
- available stock and project pieces, as entered, in large rows
- each board drawn to scale, with kerf, offcut, and the arithmetic that
  adds back to the stock length

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
