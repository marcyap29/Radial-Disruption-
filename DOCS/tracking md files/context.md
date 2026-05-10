# Session Log — Radial Disruption

Newest session first. Keep last 5 sessions; archive older entries.

---

## 2026-05-10 — Claude Sonnet 4.6 [Session 2 — First live run; data source fixes]

**Done:**
- User filled in expert_scores.csv with real RDF scores (21 pairs, 3.0–9.0 range).
- Ran full pipeline; diagnosed and fixed three data issues:
  1. **BLS OEWS 403**: `www.bls.gov` blocks programmatic downloads. Wage adjustment
     fell back to QCEW industry wages (NAICS level) — works correctly, labeled in output.
  2. **BEA Section 6 HTML redirect**: Both BEA URL patterns return an HTML login page,
     not the Excel file. Added HTML-detection guard to `download.py` so the garbage file
     is never cached. BEA method falls back to QCEW wage-as-productivity-proxy — labeled.
  3. **QCEW parser not finding files**: Subdirectory structure was `qcew_2023/2023.annual.by_industry/`;
     rewrote `_load_qcew_productivity` and `_find_qcew_file` to locate per-NAICS CSV
     files by name. Now correctly loads NAICS 5415 ($149,102/yr), 5182 ($171,216/yr),
     51 ($154,901/yr), 10 / national ($72,608/yr).
- Fixed `%,.0f` logging format error (Python `%`-style logging doesn't accept `,`).
- Wired QCEW wages into BLS wage adjustment as fallback (`bls_method.py`).
- Added QCEW national baseline code "10" to productivity ratio for BEA method.
- Passed `qcew_dir` through `main.py` → `compute_bls_ranges`.
- Pipeline runs cleanly end-to-end, no exceptions.

**Validation results — first real run:**
- 2/21 CONSISTENT: Data Scientist / ML Engineer Senior (3.0), DevOps / SRE Senior (3.0).
- 19/21 FLAGGED — systematic pattern: all Junior/Mid expert scores (7.0–9.0) fall above
  BLS upper bounds (~6.5–7.3) and well above BEA upper bounds (~3.5–4.6).

**Interpretation of results:**
- BLS flags: expert predicts heavier disruption than O*NET task-composition data implies.
  BLS ranges are driven by ATF ×10 ±1.5; the model tops out ~7 for the most automatable
  roles (QA Junior). Expert scores of 8.5–9.0 sit above this ceiling.
- BEA flags: QCEW data shows NAICS 5415 avg pay is 2.05× national average. Productivity-
  adjusted model produces low disruption scores (1–4 range). High sector wages suppress
  disruption estimates; expert judgment that AI will commoditize Junior/Mid coding conflicts
  with this structural signal. Flags are real disagreements, not bugs.
- Only Senior scores align because lower expert scores (3.0–5.5) enter the BLS range, though
  most Senior scores still sit above the BEA ceiling.

**Data sources confirmed working (cached):**
- O*NET 29.0: Task Statements, Task Ratings, Skills — all cached.
- BLS QCEW 2023: full 153 MB ZIP extracted, NAICS files loading correctly.

**Persistent data gaps (labeled in report):**
- BLS OEWS: 403 on all URLs. Wage adjustment uses QCEW industry wages as proxy.
- BEA Section 6: HTML redirect on all URL patterns. Productivity uses QCEW wage ratio.
- O*NET Work Experience Requirements: 404 (filename changed in db_29_0; not used in ATF).
- OEWS historical 1997: 403. Internet-era comparison unavailable; limitation noted in report.

**Next:**
- User reviews report.md — particularly the crosswalk table and seniority ATF profiles.
- Decide: are the BEA flags a methodology problem (productivity model too strong) or a
  genuine calibration signal (Junior/Mid scores too high)?
- If calibration adjustment needed: tune SENIORITY_TASK_WEIGHTS or BEA_SINGLE_YEAR_HW
  in config.py and re-run (cache means re-run is instant, no re-download).

---

## 2026-05-10 — Claude Sonnet 4.6 [Session 1 — Initial build]

**Done:**
- Built full project structure from scratch using Startup Onboard template pattern.
- Created DOCS/ hierarchy: CLAUDE.md, agents.md, agents_sop.md, BUG_PREVENTION.md,
  context.md, planner.md, backlog.md.
- Created complete rdf_validation/ Python package:
  - config.py — all constants, URLs, seniority weights, task-category automatable fractions
  - crosswalk.py — explicit role → SOC code mapping (7 roles, printed in every report)
  - download.py — fetch + cache with multi-URL fallback; respects --refresh flag
  - onet_seniority.py — O*NET task classification → ATF per (SOC, seniority)
  - bls_method.py — OEWS wages + ATF → BLS range [lo, hi]
  - bea_method.py — BEA Section 6 value-added → productivity → BEA range; QCEW fallback
  - validate.py — hard threshold comparison; no tolerance band
  - report.py — markdown + CSV + JSON output to rdf_validation/output/
  - main.py — CLI entry point with --dry-run and --refresh flags
- Created expert_scores.csv template (21 rows: 7 roles × 3 seniority levels, scores = 5.0)
- Created requirements.txt, .gitignore

**Key design decisions locked:**
- No API keys anywhere. Free bulk downloads only.
- 1993 target → 1997 earliest OEWS substitution, labeled in output.
- BLS and BEA ranges reported separately; never averaged.
- Hard threshold: expert score outside range → FLAGGED immediately.
- Cache: download once per session unless --refresh passed.
- Output: rdf_validation/output/ (gitignored).

**Warnings / limitations:**
- BEA Section 6 URL (`Section6All_xls.xlsx`) is the best known free bulk endpoint but
  may redirect or 404 on future BEA releases. QCEW fallback is labeled clearly.
- O*NET version pinned to 29_0 in config.py. Update ONET_VERSION when BEA releases a new
  database version.
- expert_scores.csv ships with placeholder scores of 5.0. User must fill in real scores
  before the validation output is meaningful.

**Next:**
- User fills in expert_scores.csv with real RDF scores.
- User runs: `pip install -r requirements.txt && python -m rdf_validation`
- Review report.md for any FLAGGed rows and inspect the crosswalk + seniority profile tables.
