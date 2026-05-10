# Radial Disruption — Claude Code Instructions

Python data-validation project. No UI. No API keys. All external data fetched via free
bulk-download endpoints and cached locally on first run.

---

## Standard Procedure — Follow This Every Time a Prompt Is Given

```
PROMPT RECEIVED
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1 — ORIENT (always, before anything else)                  │
│                                                                 │
│  Read: DOCS/agents md files/agents.md       ← architecture     │
│  Read: DOCS/tracking md files/context.md    ← last session     │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2 — UNDERSTAND THE TASK                                    │
│                                                                 │
│  Read: DOCS/tracking md files/planner.md    ← current tasks    │
│  Read: DOCS/tracking md files/backlog.md    ← priority pool    │
│                                                                 │
│  Task type?                                                     │
│    • New feature / multi-file  → STEP 3A                       │
│    • Bug fix                   → STEP 3B                       │
│    • Documentation update      → STEP 3C                       │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3A — PLAN (new feature / multi-file change)                │
│  Read: DOCS/agents md files/agents_sop.md → SOP-PLAN           │
│  Read: DOCS/bugtracker/BUG_PREVENTION.md  (always before code) │
│  Do:   Definition of done · file list · sub-tasks · out of scope│
├─────────────────────────────────────────────────────────────────┤
│ STEP 3B — DIAGNOSE (bug fix)                                    │
│  Read: DOCS/bugtracker/BUG_PREVENTION.md                       │
│  Read: DOCS/agents md files/agents_sop.md → SOP-ERROR          │
├─────────────────────────────────────────────────────────────────┤
│ STEP 3C — DOCUMENT                                              │
│  Update: context.md + planner.md + backlog.md                  │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4 — IMPLEMENT                                              │
│  Read every file before modifying it. Never edit blind.         │
│  Run: python -m rdf_validation --dry-run   before full run      │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5 — REVIEW                                                 │
│  Run: python -m rdf_validation                                  │
│  Verify: rdf_validation/output/report.md looks sane             │
│  Check: no new warnings in console                              │
└─────────────────────────────────────────────────────────────────┘
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6 — CLOSE SESSION (always, before stopping)                │
│  Write: context.md  → prepend session block (newest first)      │
│  Update: planner.md → cross off completed tasks                 │
│  Update: backlog.md → mark shipped items ✅                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Invariants — Never Violate

- **No API keys** — all data via free bulk-download endpoints only.
- **Cache before processing** — `download.py` must save raw files to `rdf_validation/cache/` before any computation. Subsequent runs must use cached files; never re-download unless `--refresh` flag is passed.
- **Hard threshold only** — expert score outside a derived range is FLAGGED. No tolerance band, no softening, no "close enough" logic.
- **Crosswalk is explicit** — `crosswalk.py` defines every role→SOC mapping in code and the report prints the full table. User must be able to validate it without reading Python.
- **BLS and BEA stay separate** — never average or merge the two ranges. Report both per pair so disagreement is visible.
- **Data-source limitations are documented inline** — any year substitution, fallback dataset, or structural assumption appears in the output report, not just comments.
- **Do not commit cache or output** — both directories are gitignored.

---

## File Directory

| Folder | Key files |
|---|---|
| `DOCS/agents md files/` | `agents.md` (architecture), `agents_sop.md` (SOPs) |
| `DOCS/tracking md files/` | `context.md`, `planner.md`, `backlog.md` |
| `DOCS/bugtracker/` | `BUG_PREVENTION.md` |
| `rdf_validation/` | `main.py`, `config.py`, `crosswalk.py`, `download.py`, `onet_seniority.py`, `bls_method.py`, `bea_method.py`, `validate.py`, `report.py` |
| `rdf_validation/cache/` | downloaded raw data (gitignored) |
| `rdf_validation/output/` | `report.md`, `results.csv`, `results.json` (gitignored) |

---

## Data Sources

| Source | What it provides | URL pattern |
|---|---|---|
| BLS OEWS national | Occupational wages by SOC code | `https://www.bls.gov/oes/current/oes_nat.xlsx` |
| BLS OEWS historical (1997) | Earliest available OEWS; closest to 1993 target | `https://www.bls.gov/oes/special.requests/oesm97nat.zip` |
| BEA GDP by Industry | Value added by NAICS code → productivity | `https://apps.bea.gov/national/Release/XLS/Section6All_xls.xlsx` |
| O*NET Task Statements | Task text per SOC code | `https://www.onetcenter.org/dl_files/database/db_29_0_text/Task%20Statements.txt` |
| O*NET Task Ratings | Task importance ratings (scale IM, 1–5) | `https://www.onetcenter.org/dl_files/database/db_29_0_text/Task%20Ratings.txt` |
| O*NET Skills | Skill importance + level per SOC code | `https://www.onetcenter.org/dl_files/database/db_29_0_text/Skills.txt` |
| O*NET Work Experience | Experience requirements per SOC code | `https://www.onetcenter.org/dl_files/database/db_29_0_text/Work%20Experience%20Requirements.txt` |

---

## Running the Tool

```bash
# First time: create venv and install dependencies
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# First run — downloads and caches all data, then validates
.venv/bin/python -m rdf_validation

# Subsequent runs — uses cache (fast)
.venv/bin/python -m rdf_validation

# Force re-download (e.g., after BLS annual release)
.venv/bin/python -m rdf_validation --refresh

# Dry run — verify imports and crosswalk; no download or validation
.venv/bin/python -m rdf_validation --dry-run
```

Output lands in `rdf_validation/output/`:
- `report.md` — human-readable markdown with crosswalk, seniority profiles, and validation table
- `results.csv` — one row per (role, seniority) pair with all scores and range bounds
- `results.json` — machine-readable version of results.csv

To validate against your own expert scores, edit `rdf_validation/expert_scores.csv`
(fill in the `expert_rdf_score` column, 0–10 scale) and re-run.
