# Backlog — Radial Disruption

Priority pool. Items move to planner.md when they enter an active sprint.

---

## P1 — High priority

- **Decide on BEA calibration**: 19/21 pairs flagged because expert Junior/Mid scores (7.0–9.0)
  exceed BLS upper bounds (~6.5–7.3) and BEA upper bounds (~3.5–4.6). Three options:
  (A) increase `BEA_SINGLE_YEAR_HW` to widen the range;
  (B) accept flags as real — expert judgment conflicts with structural labor market signals;
  (C) adjust `SENIORITY_TASK_WEIGHTS` in config.py and re-run (cache makes re-runs instant).
  Document the decision rationale in context.md.

- **Add QCEW multi-year download**: QCEW is now the primary data source for both BLS wage
  adjustment and BEA productivity proxy. Currently using 2023 only (single year → ±1.2
  static half-width). Extend to download 5 consecutive years (2019–2023) for a proper rolling
  window range. Update `BLS_QCEW_URL` in config.py to include prior years.

- **Validate crosswalk with BLS SOC 2018 revision**: SOC codes are periodically revised.
  Confirm 15-1252, 15-2051, etc. are current and map correctly to O*NET 29.0 codes.

---

## P2 — Medium priority

- **BEA Section 6 confirmed HTML redirect** *(was P1 — status updated 2026-05-10)*:
  Both `apps.bea.gov` URL patterns return 200 OK but body is HTML login page, not Excel.
  HTML-detection guard in download.py prevents caching bad data. BEA method correctly falls
  back to QCEW wage ratio. To fix: identify a publicly accessible BEA bulk download URL
  (check BEA's open data portal or FRED API for Section 6 data) and update `BEA_SECTION6_URLS`
  in config.py.

- **BLS OEWS 403 confirmed blocked** *(was implicit in P1 — status updated 2026-05-10)*:
  `www.bls.gov` and `download.bls.gov` both return 403 for OEWS Excel/ZIP files.
  BLS method uses QCEW NAICS wages as fallback (wage_factor ~1.045 for NAICS 5415).
  To fix: check if BLS OEWS is accessible via a mirror (data.bls.gov API, FRED, or
  direct FTP at ftp.bls.gov/pub/special.requests/oes/).

- **Interactive crosswalk review**: Add a `--crosswalk` flag that prints the crosswalk
  table and prompts the user to confirm or edit each row before validation runs.

- **O*NET Skills integration**: Skills.txt is downloaded but not yet used in ATF
  computation. Integrate skill importance ratings as a secondary ATF signal alongside
  task ratings. Document the blending weight in config.py.

- **Historical BLS CES trend chart**: Use BLS CES series for Information sector
  (CEU5500000001) to show employment trend from 1993 to present as a contextual
  analogue for AI disruption. Output as a data table in the report.

---

## P3 — Low priority / future

- **O*NET version auto-detect**: Query onetcenter.org for the latest database version
  and update ONET_VERSION in config.py automatically on --refresh.

- **Multi-expert score support**: Allow multiple expert columns in expert_scores.csv
  (e.g., `expert_1_score`, `expert_2_score`). Report inter-rater agreement alongside
  empirical validation.

- **Confidence intervals from O*NET**: O*NET provides standard errors for task ratings.
  Use them to propagate uncertainty into the ATF estimate and widen the BLS range
  proportionally rather than using a fixed BLS_UNCERTAINTY_HW.

- **Web output**: Generate a self-contained HTML report alongside report.md for easier
  sharing without a Markdown viewer.
