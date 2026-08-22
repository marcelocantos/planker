# Entropy audit: planker

Date: 2026-08-22
Mode: full (entropy + explicit hygiene validation)
Auditor: entropy-audit owner (this campaign)

## Executive summary

- **Snapshot:** `/Users/marcelo/work/github.com/marcelocantos/planker`
- **Branch:** `master` (tracks `origin/master`)
- **HEAD:** `ec4d694e47e0d4dc121894bc6c51306c8dcd8737` — `Add Apache 2.0 license (#1)`
- **Prior commit:** `7ca9d77fa5b5865e66c8f9d25baa702ea7e4033c` — `planker: cut desired planks from available lengths`
- **Initial dirty state:** clean (`git status --porcelain=v1 -b` showed only `## master...origin/master`)
- **Scope:** the four tracked files (`planker.py`, `README.md`, `input.json`, `LICENSE`). No packages, tests, CI, or generated trees exist.
- **Exclusions:** none named. There is no vendored, generated, fixture-snapshot, or `node_modules`/`.venv` tree. `input.json` is live job data committed as the only sample input, and is in scope.

**Headline mechanism:** A 51-line stdin CLI whose only algorithm (kerf-adjusted leftover best-fit, largest-first) is also the whole product, yet kerf is an undocumented magic `3` that leaks into the spreadsheet TSV, and nothing on the shipped path asserts allocation, leftover, or unallocated invariants.

**Highest-consequence findings:**

- **ENT-001 (P1):** No executable oracle for the allocator. `pytest --collect-only` finds zero tests; GitHub Actions reports `total_count: 0`.
- **ENT-002 (P2):** User-facing leftover/unallocated columns include kerf. Unused 5400 mm stock is printed as leftover `5403`.
- **ENT-003 (P2):** Module docstring describes a JSON schema that `main()` rejects.

**Unverified residue:** whether leftover should charge `n` or `n-1` kerfs; whether the Google Sheet is the intended long-term UI and whether that sheet is world-readable; whether greedy leftover-min is accepted versus exact packing.

## Scope and exclusions

In scope: `planker.py` (runtime), `README.md` (declared contract), `input.json` (committed job), `LICENSE`, GitHub repo settings visible via `gh`.

Out of scope because absent: `.github/`, `tests/`, `hygiene.yaml`, `AGENTS.md`, `CLAUDE.md`, `pyproject.toml`, packaging, containers, services.

No generated or vendored trees were skipped.

## Commands run

All commands from repo root. Auxiliary probes did not modify files.

| Command | Version / identity | Exit | Shipped vs auxiliary | Result / limitation |
|---|---|---|---|---|
| `git rev-parse --abbrev-ref HEAD` | git | 0 | provenance | `master` |
| `git rev-parse HEAD` | git | 0 | provenance | `ec4d694e47e0d4dc121894bc6c51306c8dcd8737` |
| `git status --porcelain=v1 -b` | git | 0 | provenance | `## master...origin/master` (clean) |
| `git log --stat --format=fuller` | git | 0 | history | 2 commits; first lands `planker.py`+README+`input.json`; second LICENSE via PR #1 |
| `python3 --version` | CPython 3.13.0 (`/Users/marcelo/.py/bin/python3`) | 0 | environment | Runtime used for shipped-path run |
| `python3 planker.py < input.json` | same | 0 | **shipped path** | stderr `unallocated: []`; 15 TSV rows; two unused 5400 mm planks report leftover `5403` |
| `python3 -m py_compile planker.py` | same | 0 | shipped syntax | compiles |
| `python3 -m compileall -q .` | same | 0 | shipped syntax | compiles |
| `ruff check planker.py` | ruff 0.15.20 (already installed; **not** a repo dependency) | 1 | auxiliary | F401 unused `typing.Dict`, `typing.Any` at `planker.py:13` |
| `ruff format --check planker.py` | ruff 0.15.20 | 1 | auxiliary | would insert a blank line before `if __name__` |
| `pytest --collect-only -q` | pytest 9.0.3 (global venv; **not** declared here) | 5 | auxiliary collect | `no tests collected in 0.00s`; no `tests/` directory |
| `/Users/marcelo/.claude/skills/hygiene/hygiene_check.py` | uv-run script | 1 | hygiene validator | `FileNotFoundError: .../planker/hygiene.yaml` |
| `gh api repos/marcelocantos/planker/actions/workflows` | gh | 0 | GitHub | `{"total_count":0,"workflows":[]}` |
| `gh api repos/marcelocantos/planker/branches/master/protection` | gh | 404 | GitHub | `Branch not protected` |
| `gh api repos/marcelocantos/planker --jq '{visibility,security_and_analysis}'` | gh | 0 | GitHub | public; Dependabot + secret scanning **disabled** |
| README-example stdin to `planker.py` | CPython 3.13.0 | 0 | shipped path (example) | unused 10000 mm stock leftover `10003` |
| docstring-shaped JSON to `planker.py` | same | 1 | shipped path (negative) | `TypeError: cannot unpack non-iterable int object` at `planker.py:39` |
| In-process leftover reconstruction | same | 0 | auxiliary | leftover matches `piece - sum(cuts) - (n-1)*kerf` (n≥1) and `piece+kerf` (n=0) |

Limitations: ruff/pytest are host tools, not repo-declared gates. No clone detector, coverage, or SBOM tool is configured. `gh` 404 on `.github/workflows` contents is consistent with zero Actions workflows.

## Dimension vector

First audit of this snapshot; **Change from baseline** is n/a for every row.

| Dimension | State | Evidence summary | Change from baseline |
|---|---|---|---|
| Architecture topology | healthy | One script, stdlib `json`/`sys`, stdin JSON → stdout TSV / stderr diagnostics. No packages, cycles, or hidden deployables. | n/a |
| Redundancy / sources of truth | concern | Three descriptions of input and algorithm (module docstring, README, `main()`/`allocate_greedy`) do not agree. | n/a |
| Change amplification | healthy | Kerf, packing rule, and TSV schema all live in `planker.py`. A behaviour change is one file plus README. | n/a |
| Local code quality | concern | Linear and readable, but magic `kerf = 3`, leftover encoding, unused typing imports, commented debug prints. | n/a |
| Correctness / verification | concern | Shipped run on `input.json` fully allocates (62/62), but leftover/unallocated are kerf-tainted and no test asserts that. | n/a |
| Security / dependencies | healthy | No third-party deps; stdin JSON only; no secrets in tree. Public repo with scanning off is low consequence at this size. | n/a |
| Build / release / operations | concern | Shebang script, no package metadata, no CI, unprotected `master`, no tags. Appropriate as a local tool; undeclared as a public repo. | n/a |
| Documentation / governance | concern | Apache-2.0 LICENSE and a usable README exist; docstring is wrong; no `AGENTS.md`, CODEOWNERS, hygiene, or SECURITY.md. | n/a |

Do not collapse this vector to a scalar.

## Observed architecture

```
stdin JSON {available, desired}  →  main()  →  allocate_greedy()  →  stdout TSV + stderr unallocated
                                              kerf=3 inside allocator
README usage  →  pbcopy  →  Google Sheet "Plank cuts"
```

**Entry point:** `planker.py:50-51` (`if __name__ == "__main__": main()`), shebang `#!/usr/bin/env python3`.

**Deployable unit:** the script itself. GitHub description: "Calculate cubby house plank dimensions" (`https://github.com/marcelocantos/planker`). No installable package.

**Domain:** expand `[count, length]` rows to bags of millimetre lengths; sort desired descending; greedy-assign each want to the current smallest leftover that fits after adding 3 mm kerf; print stock, leftover, and cut list as TSV.

**Public surfaces:** stdin JSON, stdout TSV header `allocated\tleftover\tcuts` (`planker.py:46`), stderr `unallocated:` (`planker.py:45`), README example, hardcoded Sheet URL.

**Dependencies:** CPython stdlib only. Direction: `main` → `allocate_greedy`; no cycles.

**Cross-cutting:** kerf is inlined in the allocator, not configuration. No logging, auth, or flags.

### Declared vs observed

| Rule | Status |
|---|---|
| Lengths are integer mm | declared in README:16-17; observed (no type check; negatives allocate) |
| Input is `[[count, length], ...]` | declared in README:21-22; **observed** in `main()` at `planker.py:39-40` |
| Input is a list of numbers | declared in module docstring `planker.py:4-6`; **contradicted** by `main()` |
| Smallest available plank that fits | declared in README:3-4; **not** what `min(candidates)` on leftover does in general |
| Best-fit greedy cutter by default | declared in docstring `planker.py:8`; observed leftover-min; "by default" implies other cutters that do not exist |
| Kerf 3 mm, charged as (n−1) saw gaps on used stock | **inferred** from `planker.py:17-29`; not declared |
| Output is pasteable TSV for a named Google Sheet | declared in README:9-12; observed |

Unknown intent requiring owner judgment: leftover formula (n vs n−1 kerfs); whether unused leftover should be stock millimetres; whether greedy is good enough versus exact bin packing.

## Findings

### ENT-001: The only algorithm has no shipped-path oracle

- **Priority:** P1
- **Dimensions:** Correctness / verification; Build / release / operations
- **Status:** observed fact
- **Evidence:**
  - `pytest --collect-only -q` → exit 5, `no tests collected`; no `tests/` or `test/` directory
  - `gh api repos/marcelocantos/planker/actions/workflows` → `{"total_count":0,"workflows":[]}`
  - `git ls-files` is only `LICENSE`, `README.md`, `input.json`, `planker.py`
  - Load-bearing behaviour lives in `allocate_greedy` (`planker.py:16-33`) and expansion/sort in `main` (`planker.py:39-40`)
  - Shipped run `python3 planker.py < input.json` exits 0 and reports `unallocated: []`, but that is a smoke, not an invariant check
- **Mechanism:** Kerf, leftover encoding, candidate selection, and descending sort can change without any check failing. The next plausible defect (off-by-kerf leftover, wrong unallocated millimetres, sort removed) would be noticed only by staring at a spreadsheet.
- **Blast radius:** The whole product. Future packing or kerf edits have no regression net.
- **Counterevidence checked:** `python3 -m py_compile planker.py` is green (syntax only). Committed `input.json` currently fully allocates (62 desired pieces, 15 stock planks, 2 unused 5400 mm). That is a single golden smoke, not an assertion. History: both logic and sample were introduced together in `7ca9d77`; no later test commit.
- **Smallest coherent remediation:** Add a tiny pytest module (or even `python3 -m unittest`) that feeds known `[count, length]` bags and asserts (1) allocated multiset equals desired, (2) leftover formula, (3) unallocated values are original millimetres, (4) docstring-illegal JSON is rejected or documented. Wire it as a GitHub Actions job on `master`.
- **Verification:** `pytest` fails if leftover for unused stock is `stock+kerf` or if unallocated includes kerf.
- **Ratchet candidate:** hygiene `correctness.unit-tests` with `command: pytest` (or a `ci_job` once a workflow exists). Do not add `hygiene.yaml` until the tests exist.

### ENT-002: Kerf is mixed into leftover and unallocated outputs

- **Priority:** P2
- **Dimensions:** Correctness / verification; Local code quality; Documentation / governance
- **Status:** observed fact
- **Evidence:**
  - `kerf = 3` at `planker.py:17` with no name at module scope, no CLI flag, no README mention
  - Unused stock: `leftover = [x + kerf for x in pieces]` (`planker.py:22`) is never decremented, then printed as the leftover column (`planker.py:47-48`)
  - Shipped `input.json` run: unused rows `5400\t5403` (twice)
  - README example run: unused rows `10000\t10003`
  - Auxiliary reconstruction: used leftover equals `piece - sum(cuts) - (n-1)*kerf`; unused equals `piece+kerf`
  - Failed assignments append `want` **after** `want += kerf` (`planker.py:24,31`). Probe with zero stock and desired 1800 reports `unallocated: [1803]`
  - Allocated cuts correctly store `want - kerf` (`planker.py:28`)
- **Mechanism:** The allocator uses a virtual `stock+kerf` leftover so a full-plank cut does not need an extra kerf, then prints that internal encoding. Spreadsheet consumers (README:10-12) therefore see leftover millimetres that are not remaining stock. Unallocated stderr is similarly inflated, so a "what still needs buying" glance is wrong by 3 mm per piece.
- **Blast radius:** Every paste into the `Plank cuts` sheet; any leftover-based scrap decision; any unallocated restock list. 3 mm is inside typical saw kerf, so a tight fit can be accepted on paper and fail on the saw, or unused stock can look 3 mm longer than it is.
- **Counterevidence checked:** On committed `input.json`, `unallocated` is empty, so the unallocated leak is latent there. Allocated cut values match original desired lengths (62/62). The (n−1) kerf model is internally consistent; it may be physically intended (kerf only between successive cuts). README never mentions leftover semantics, so this is not a documented encoding.
- **Smallest coherent remediation:** Keep internal `stock+kerf` if that model is intended, but print leftover as remaining millimetres of stock (`leftover[i] - kerf` if that matches the model, or compute `available[i] - sum(alloc) - kerf_used` explicitly) and append original `want` to `unallocated`. Lift `KERF = 3` to a named constant and document it in README.
- **Verification:** Test: unused plank of 5400 prints leftover 5400 (or whatever millimetre semantics the owner chooses, but not 5403 unless documented). Test: one unallocatable 1800 prints `1800`, not `1803`.
- **Ratchet candidate:** a unit test on leftover/unallocated millimetres; later a README sentence that `hygiene` `file:`-matches `kerf`.

### ENT-003: Module docstring schema contradicts `main()`

- **Priority:** P2
- **Dimensions:** Redundancy / sources of truth; Documentation / governance
- **Status:** observed fact
- **Evidence:**
  - Docstring `planker.py:4-6` says `available` / `desired` are "list of available/desired plank lengths (numbers)"
  - `main()` does `sum(([x] * n for n, x in data["available"]), [])` (`planker.py:39-40`)
  - Piped `{"available":[5400,5400],"desired":[1800,900]}` exits 1: `TypeError: cannot unpack non-iterable int object` at `planker.py:39`
  - README:21-28 documents `[[count, length], ...]` and matches `main()`
- **Mechanism:** Two authorities for the wire format. A reader of the module docstring will emit JSON the program cannot parse. A later edit to expansion logic has no schema test.
- **Blast radius:** Anyone invoking the CLI from the docstring rather than README; future schema changes.
- **Counterevidence checked:** README example JSON runs to completion (exit 0). GitHub repo has no other API docs. History: docstring and `main()` were introduced in the same commit `7ca9d77`, so this is original drift, not a later refactor leftover.
- **Smallest coherent remediation:** Rewrite the docstring to the `[count, length]` bags, mention descending sort and kerf, and drop "by default".
- **Verification:** A test that the README example object allocates, and that a list-of-numbers object is either accepted (if you change `main()`) or fails with a clear error.
- **Ratchet candidate:** a JSON-schema fixture test, or a README/docstring contract test. Not worth a separate schema library at this size.

### ENT-004: README packing rule is not the leftover best-fit in `allocate_greedy`

- **Priority:** P3
- **Dimensions:** Redundancy / sources of truth; Documentation / governance
- **Status:** observed fact (docs); inference (practical divergence)
- **Evidence:**
  - README:3-4: "greedy algorithm that cuts the smallest available plank that fits each desired length"
  - Code: `candidates = {(p, i) for i, p in enumerate(leftover) if p >= want}` then `min(candidates)` (`planker.py:25-27`) — smallest **current leftover**, then smallest index
  - `main()` sorts desired descending (`planker.py:40`); README does not mention that
  - Docstring `planker.py:8`: "best-fit greedy cutter by default" (no other cutter exists)
  - On committed `input.json`, leftover-min and smallest-original-stock coincide
  - Constructed case `pieces=[1000,400], cuts=[650,300]`: leftover-min packs both onto 1000; smallest-original puts 300 onto 400
- **Mechanism:** Future readers (or a "fix the greedy" edit) may implement README literally and change cut lists on real jobs. The committed sample does not detect that fork.
- **Blast radius:** Any new `input.json` where a large plank has been partly used and still has smaller leftover than an unused shorter plank.
- **Counterevidence checked:** README "smallest available" is a reasonable colloquial label for leftover-min on a first cut. No second algorithm is in the tree. Divergence is demonstrated only on a synthetic bag, not on `input.json`.
- **Smallest coherent remediation:** Describe leftover best-fit decreasing in README in one sentence; delete "by default".
- **Verification:** A comment/README test is enough; a unit test that the constructed case keeps leftover-min if that is the chosen rule.
- **Ratchet candidate:** none until the sentence exists; then a `file:` hygiene match is optional.

### ENT-005: Product UI is an unpublished Google Sheet linked from README

- **Priority:** P3
- **Dimensions:** Documentation / governance; Security / dependencies
- **Status:** observed fact (URL present); needs verification (sheet ACL)
- **Evidence:** README:10-12 hardcodes `https://docs.google.com/spreadsheets/d/1xOtPt0CwiL2-eQyeWxo1ROeBID4Hba62ZC9iWFdcyt4/edit?gid=714141135#gid=714141135` and instructs paste into `Plank cuts`
- **Mechanism:** The TSV has no in-repo consumer. The sheet is a second authority for how leftover/cuts are interpreted. If the sheet is link-readable, a public repo advertises a personal cubby-house cut list.
- **Blast radius:** Documentation and anyone cloning the public repo; possible exposure of project dimensions. Not a code RCE.
- **Counterevidence checked:** No credentials in the URL. The repo is public (`visibility: public`). Sheet ACL was **not** fetched (would require Google auth / browser). This audit did not open the sheet.
- **Smallest coherent remediation:** Keep the paste workflow; either document "private sheet, replace the URL" or drop the specific ID from README in favour of "paste into your sheet".
- **Verification:** Owner confirms sheet sharing. A doc-only change has no runtime test.
- **Ratchet candidate:** none (manual attestation).

### ENT-006: Public default branch has no merge or CI gate

- **Priority:** P3
- **Dimensions:** Build / release / operations; Documentation / governance
- **Status:** observed fact
- **Evidence:**
  - `gh api .../branches/master/protection` → 404 Branch not protected
  - Actions `total_count: 0`
  - No `.gitignore`, `pyproject.toml`, Makefile, CODEOWNERS, SECURITY.md, Dependabot
  - Secret scanning and Dependabot updates disabled on a public repo
  - Two commits, one author; LICENSE via merged PR #1
- **Mechanism:** `git push origin master` can land anything, including a broken allocator, with no check. Proportionate for a personal 51-line script; still the observed SDLC of a public GitHub repo.
- **Blast radius:** `origin/master` history; clones that trust HEAD.
- **Counterevidence checked:** Stdlib-only, no supply chain to scan. PR #1 existed for LICENSE, so GitHub PR flow has been used at least once. Local shebang execution does not need a release pipeline.
- **Smallest coherent remediation:** One Actions workflow running `python3 -m py_compile planker.py` plus the tests from ENT-001. Branch protection is optional at this bus factor.
- **Verification:** A dummy failing test turns the workflow red.
- **Ratchet candidate:** hygiene `build.ci` / `correctness.unit-tests` after the workflow exists. Do not declare floors above reality.

## Redundancy and competing sources of truth

| Fact | Authorities | Drift |
|---|---|---|
| JSON wire format | docstring `planker.py:4-6` vs README:21-28 vs `main()` `planker.py:39-40` | docstring is wrong (ENT-003) |
| Packing rule | README:3-4 vs docstring `planker.py:8` vs `allocate_greedy` `planker.py:25-27` | leftover-min vs "smallest available plank"; "by default" is fiction (ENT-004) |
| Remaining millimetres | internal leftover (`stock+kerf` then subtract `want+kerf`) vs printed leftover column vs physical stock | printed unused leftover is stock+3 (ENT-002) |
| Unallocated millimetres | original desired vs `want` after kerf add | printed unallocated is desired+3 (ENT-002) |
| What the repo is | GitHub description "cubby house plank dimensions" vs README "allocate available plank lengths" | compatible, not contradictory |
| Sample job | `input.json` vs README example JSON | two independent examples; not competing |

No duplicate allocators, no parallel validators, no generated copies.

Deliberate non-duplication: TSV printing is inline in `main()` rather than a second formatter.

## Healthy structure worth retaining

- **One file owns the algorithm.** `allocate_greedy` + `main` is the right size. Do not split layers, add a package, or introduce a strategy interface for a single cutter.
- **Stdlib only.** `json` + `sys` is the whole dependency graph. Keep it that way; a solver library would be disproportionate.
- **I/O contract is simple and useful.** stdin JSON, stdout TSV, stderr diagnostics. README:9-12 describes a real paste workflow.
- **README bag schema matches `main()`.** `[count, length]` expansion at `planker.py:39-40` is the live format.
- **Largest-first then leftover-min** is a coherent greedy decreasing / best-fit heuristic, implemented linearly in ~20 lines.
- **Shipped smoke is currently feasible.** `python3 planker.py < input.json` exits 0, `unallocated: []`, 62 desired pieces placed on 15 stock planks.
- **Apache-2.0 LICENSE** is present and GitHub-classified (`license.spdx_id: Apache-2.0`).
- **No cycles, no adapters, no dead packages.** Unused `Dict`/`Any` and two commented prints (`planker.py:42-43`) are the only residue inside the script.

## Hygiene posture

**Hygiene posture not declared.** There is no `hygiene.yaml`. It was not initialized.

Explicit validator run from repo root:

```
$ /Users/marcelo/.claude/skills/hygiene/hygiene_check.py
FileNotFoundError: [Errno 2] No such file or directory: '/Users/marcelo/work/github.com/marcelocantos/planker/hygiene.yaml'
exit 1
```

No per-dimension held tiers or floors exist to validate. Negative-space items cannot drift-fail.

Overlap with entropy: ENT-001/ENT-006 are the missing correctness and CI controls hygiene would later declare. Do not author `hygiene.yaml` from this audit; any file written now would either over-declare (floors above reality) or freeze "no tests" as the held tier without an owner decision.

Entropy findings suitable for later hygiene (only after the artefact exists):

- `correctness.unit-tests` → `command: pytest`
- `docs.license` → `file: {path: LICENSE}` (already true)
- `docs.readme` → `file: {path: README.md}` (already true)
- `build.ci` → `ci_job` once a workflow exists
- `vcs.gitignore` → only if a `.gitignore` is actually needed (today there are no build artefacts)

## Oracle coverage and residue

| Property | Decided by |
|---|---|
| Script parses as Python 3 | shipped: `python3 -m py_compile planker.py` (exit 0) |
| `input.json` currently fully allocates | shipped smoke: stderr `unallocated: []` (no assertion this remains true) |
| README example JSON is accepted | shipped: example stdin exit 0 |
| Docstring list-of-numbers JSON is accepted | **fails** on shipped path (ENT-003) |
| Leftover column is remaining stock mm | **nothing**; auxiliary reconstruction only (ENT-002) |
| Unallocated lengths are original mm | **nothing**; auxiliary probe only (ENT-002) |
| Allocated multiset equals desired | **nothing** (held on this snapshot by inspection, not gated) |
| Kerf model (n vs n−1) is the intended physics | **owner intent** |
| Greedy leftover-min vs exact packing quality | **nothing** (accepted risk / taste) |
| Google Sheet ACL | **unverified** (ENT-005) |
| ruff F401 / format blank line | auxiliary host ruff; not a repo gate |
| Dependency vulnerabilities | N/A (no third-party deps) |
| CI on `master` | **nothing** |

Failed/skipped checks: `pytest` collect exit 5; `hygiene_check.py` exit 1 (missing yaml); ruff check/format exit 1 (auxiliary); branch protection 404; no coverage, clone detector, or live Sheet fetch.

### Owner residue (intent only)

- Should leftover charge one kerf per cut (`n`) or only between remaining pieces (`n-1` plus the `stock+kerf` trick)?
- Print leftover as stock millimetres, or document the internal encoding?
- Keep leftover best-fit decreasing, or implement README "smallest original plank"?
- Is the Google Sheet the long-term UI, and is it private?
- Declare hygiene with honest floor 0, or leave undeclared until tests exist?

## Remediation sequence

1. **Oracle first (ENT-001).** Add tests for allocated multiset, leftover millimetres, unallocated millimetres, and the README example. Run them locally with `pytest`.
2. **Fix reporting to match the tests (ENT-002).** Print leftover/unallocated in stock millimetres; name `KERF`. Document the chosen n vs n−1 rule in README in one sentence.
3. **Converge docs (ENT-003, ENT-004).** Make the module docstring match `main()`; replace "smallest available plank" / "by default" with leftover best-fit decreasing.
4. **Optional Sheet hygiene (ENT-005).** Drop or qualify the spreadsheet ID.
5. **Ratchet (ENT-001, ENT-006).** One GitHub Actions job; then, if requested, `hygiene.yaml` with floors that match reality (`docs` LICENSE+README, `correctness` once pytest is in CI). Do not set floors above what the validator can see.
6. **Re-run this audit** on the same finding IDs and the same leftover/unallocated definitions.

Do not introduce a packer framework, config file, or TOML project metadata unless packaging becomes a real need. Keep the single-module shape.
