# Radial Disruption — Architecture

## What this project does

Validates expert-assigned Radial Disruption Factor (RDF) scores for AI coding roles against
empirically derived ranges from two independent public data sources (BLS and BEA).

An expert score is **consistent** if it falls within BOTH independently derived ranges.
If it falls outside either range, it is **FLAGGED** — no softening, no tolerance band.

---

## RDF Score

Scale: **0–10**
- 0 = occupation completely resistant to AI disruption
- 10 = occupation fully automatable by AI

---

## Module map

```
rdf_validation/
├── main.py            Entry point. Orchestrates the pipeline.
├── config.py          All constants: URLs, thresholds, seniority weights, task-category
│                      automatable fractions. One place to change methodology parameters.
├── crosswalk.py       Role → SOC code mapping. Printed in full in every report so the
│                      user can validate it without reading Python.
├── download.py        Fetch + cache. All external HTTP lives here. Respects --refresh.
│                      Never re-downloads unless explicitly asked.
├── onet_seniority.py  Loads O*NET task statements + importance ratings. Classifies tasks
│                      into four categories (implementation / design / communication /
│                      leadership). Computes Automatable Task Fraction (ATF) per SOC
│                      code per seniority level. Prints seniority profiles in report.
├── bls_method.py      BLS OEWS wage data + O*NET ATF → disruption point estimate →
│                      BLS range [low, high].
├── bea_method.py      BEA GDP-by-Industry value-added data → productivity ratio →
│                      disruption point estimate → BEA range [low, high] from
│                      rolling multi-year variance.
├── validate.py        Loads expert_scores.csv. Compares each expert score to BLS range
│                      and BEA range. Applies hard threshold. Returns structured results.
└── report.py          Writes report.md, results.csv, results.json to output/.
```

---

## Pipeline flow

```
download.py
  ├── BLS OEWS current  (oes_nat.xlsx)
  ├── BLS OEWS 1997     (oesm97nat.zip)  ← closest available to 1993 target
  ├── BEA Section 6     (Section6All_xls.xlsx or fallback)
  ├── O*NET Task Statements
  ├── O*NET Task Ratings
  ├── O*NET Skills
  └── O*NET Work Experience Requirements
         │
         ▼
onet_seniority.py
  └── ATF per (SOC code, seniority level)
         │
         ├──► bls_method.py  → BLS range [lo, hi]  ─┐
         │                                            ├──► validate.py → flag / pass
         └──► bea_method.py  → BEA range [lo, hi]  ─┘
                                                            │
                                                            ▼
                                                       report.py
                                               crosswalk table
                                               seniority profiles
                                               validation table
                                               limitation notes
```

---

## BLS method — how the range is derived

1. Load O*NET task statements and importance ratings (scale IM, 1–5) for each SOC code.
2. Classify each task into one of four categories using keyword matching:
   - **implementation** — write, code, program, build, test, debug, deploy, compile…
   - **design** — design, architect, plan, specify, model, prototype, evaluate…
   - **communication** — communicate, present, document, coordinate, collaborate…
   - **leadership** — lead, manage, mentor, supervise, strategy, delegate…
3. Compute per-category ATF (Automatable Task Fraction) using `TASK_AI_AUTOMATABLE_FRACTION` from config.
4. Apply seniority task-weight adjustment (`SENIORITY_TASK_WEIGHTS` from config) to get a seniority-specific ATF blend.
5. Apply wage adjustment: lower median hourly wage → higher disruption tendency (price-elastic labor is more replaceable).
6. BLS disruption point = blended_ATF × 10 × wage_factor
7. BLS range = [point − BLS_UNCERTAINTY_HW, point + BLS_UNCERTAINTY_HW], clamped to [0, 10].

`BLS_UNCERTAINTY_HW = 1.5` represents methodological uncertainty in task classification.

---

## BEA method — how the range is derived

1. Load BEA Section 6 data (income and employment by industry).
2. Extract value-added proxy (compensation of employees) and full-time equivalent employment for NAICS 5415 (Computer Systems Design) and all industries.
3. Compute labor productivity = value_added / FTE_employment.
4. Compute relative productivity = sector_productivity / national_median_productivity.
5. Disruption score = ATF × 10 / relative_productivity  (higher productivity → harder to replace → lower score).
6. Range = [min, max] over the rolling 5-year window of annual disruption scores.
7. If BEA data download fails, falls back to BLS QCEW industry-wage data and labels the range clearly as QCEW-derived.

---

## Seniority differentiation

O*NET does not have separate entries for Junior / Mid / Senior.
The project approximates seniority by re-weighting task categories:

| Category | Junior | Mid | Senior |
|---|---|---|---|
| implementation | 0.65 | 0.45 | 0.20 |
| design | 0.20 | 0.30 | 0.40 |
| communication | 0.10 | 0.15 | 0.20 |
| leadership | 0.05 | 0.10 | 0.20 |

These weights are derived from patterns in O*NET Work Experience Requirements and
task importance profiles across experience bands. Shown explicitly in the report.

---

## 1993 internet data — limitation note

Target year: 1993 (early commercial internet era, requested as historical analogue).
Earliest available BLS OEWS data: **1997**.

The 1997 data is used as the closest available substitute and labeled accordingly in
the report. No silent substitution — the limitation appears in the output.

---

## Validation rule

```
For each (role, seniority) pair:
  within_bls = bls_low <= expert_score <= bls_high
  within_bea = bea_low <= expert_score <= bea_high

  if within_bls and within_bea:   CONSISTENT
  elif within_bls:                 FLAGGED — outside BEA range
  elif within_bea:                 FLAGGED — outside BLS range
  else:                            FLAGGED — outside both ranges
```

No tolerance band. No averaging. BLS and BEA disagreements are surfaced, not hidden.
