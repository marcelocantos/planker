# Planker

Small CLI tool to allocate available plank lengths to desired lengths. It uses a
greedy algorithm that cuts the smallest available plank that fits each desired
length.

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
