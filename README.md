# Planker

Small CLI tool to allocate available plank lengths to desired lengths. It uses a
greedy algorithm that cuts the smallest available plank that fits each desired
length.

Plasterboard is a separate 2D page. It does not change the timber cutter.
See [Plasterboard sheets](#plasterboard-sheets).

Usage:

```
planker.py < input.json | pbcopy
open 'https://docs.google.com/spreadsheets/d/1xOtPt0CwiL2-eQyeWxo1ROeBID4Hba62ZC9iWFdcyt4/edit?gid=714141135#gid=714141135'
# paste into the 'Plank cuts' sheet
```

Units and input format:

- All lengths are integer mm.

Example input JSON:

Each field contains an array of arrays. Each sub array contains two elements,
count and length, e.g., [2, 1000] means two segments of 1000 mm each.

```
{
  "available": [[4, 10000], [5, 8000]],
  "desired": [[2, 6000], [1, 4000], [2, 2000], [1, 9000], [1, 5000]]
}
```

## Plasterboard sheets

A phone page that lays rectangular panels onto rectangular stock sheets.
The timber command above is unchanged. This planner does not read
`input.json`.

`example-plaster.json` is an **EXAMPLE / FICTIONAL** spare room, not a
client job and not a real bill of materials. The room is made up: 3.6 m by
3.0 m and 2.7 m high, with a wardrobe bulk on the west wall, a bulkhead
along the window wall, one door, and one window. In that fiction the
garage holds 11 sheets of 1200×2700 mm and 8 sheets of 1200×2400 mm.
Those are typical Australian plasterboard sizes, used only so the drawing
has familiar proportions.

```bash
python3 plaster.py example-plaster.json
python3 plaster.py --html docs/plaster-cut-plan.html example-plaster.json
```

Open [`docs/plaster-cut-plan.html`](docs/plaster-cut-plan.html) on a phone:

- **iPhone or iPad:** AirDrop the file, or copy it into Files, then open it
  in Safari. From Files you can also use Share → Open in Safari.
- **Android:** copy the file onto the phone and open it in Chrome.

Nothing to install. The page works offline. There is no camera.

The first screen is the sheets to pull. Tick a row at the rack.
**Share**, **Copy**, and **Print** sit in the bar at the bottom. Share
sends the plain-text list. **Edit stock and panels** changes counts and
millimetre width × height on the phone, and the list and the drawings
update. **Restore example job** puts the fictional spare room back. Edits
stay on that device until you restore.

The page also draws a **room preview**. Each cut panel has one colour on
its sheet and the same colour on the wall or ceiling it belongs to. Drag
to turn the room, pinch to zoom, and tap a panel to mark it in both
views. The door and the window are openings. This view is part of the
fiction: it is the made-up spare room, not a measured site.

Saw kerf is the named setting `kerf_mm`. The default is **3 mm**, about a
circular-saw or panel-saw blade. Set it to **0** for score-and-snap, which
does not remove a strip. A panel that lands flush with an edge has no kerf
on that edge. A gap thinner than the kerf is refused.

Packing is a **guillotine best-area fit with a shorter-leftover split**.
It is not an exact optimum.

- Panels are placed largest longer-side first.
- Each panel goes into the free rectangle that leaves the smallest offcut
  area. Ties prefer a sheet already in use, then an unturned panel, then
  the earlier sheet.
- The panel may be turned 90° unless **face direction locked** is set.
  Stock sheets are not turned. Width runs across the sheet. Height runs
  down the drawing.
- The leftover of that rectangle is one through-cut. If the leftover width
  is less than the leftover height, the cut runs the full height of the
  rectangle. Otherwise it runs the full width.
- The kerf is taken out of that cut.

The page draws each cut sheet to scale, with offcuts hatched and panels
that did not fit drawn at the same scale. It does not invent a sheet to
buy for those panels.

```bash
python3 -m unittest discover -s tests -v
```
