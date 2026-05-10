# Active Plan — Session 2 Close

**Status:** Session 2 complete. Pipeline ran successfully end-to-end. Awaiting next iteration decision.

---

## Definition of Done

- All Python modules present and importable
- `python -m rdf_validation --dry-run` exits cleanly
- `python -m rdf_validation` produces report.md, results.csv, results.json in output/
- Crosswalk table visible in report
- Seniority profiles visible in report
- Validation table shows BLS range and BEA range separately per (role, seniority) pair
- FLAGGED rows call out which source (BLS / BEA / both) triggered the flag

---

## Tasks

### Infrastructure
- [x] Create DOCS/ hierarchy
- [x] Write CLAUDE.md (root)
- [x] Write agents.md (architecture)
- [x] Write agents_sop.md
- [x] Write BUG_PREVENTION.md
- [x] Write context.md, planner.md, backlog.md
- [x] Write .gitignore
- [x] Write requirements.txt

### Python package
- [x] config.py — constants, URLs, weights
- [x] crosswalk.py — role → SOC mapping
- [x] download.py — fetch + cache
- [x] onet_seniority.py — O*NET ATF computation
- [x] bls_method.py — BLS range derivation
- [x] bea_method.py — BEA range derivation
- [x] validate.py — hard-threshold comparison
- [x] report.py — output generation
- [x] main.py — CLI entry point
- [x] expert_scores.csv — template

### Session 1 user actions (complete)
- [x] Fill in expert_scores.csv with real RDF scores (21 pairs, 3.0–9.0)
- [x] Run `pip install -r requirements.txt`
- [x] Run `python -m rdf_validation` and review report.md
- [x] Validate crosswalk table against industry knowledge
- [x] Review seniority profiles and adjust config.py weights if needed

### Session 2 data source fixes (complete)
- [x] Diagnose BLS OEWS 403 — added QCEW industry wage fallback in bls_method.py
- [x] Diagnose BEA Section 6 HTML redirect — added HTML-detection guard in download.py
- [x] Diagnose QCEW parser missing files — rewrote _find_qcew_file() and _load_qcew_productivity()
- [x] Fix `%,.0f` logging format error — changed to `$%.0f` in bls_method.py and bea_method.py
- [x] Add QCEW national code "10" as baseline for BEA productivity ratio
- [x] Pass qcew_dir through main.py → compute_bls_ranges
- [x] Confirm pipeline runs cleanly end-to-end

### Open decisions (next session)
- [ ] Decide: are BEA flags a methodology problem or a genuine calibration signal?
  - Option A: Reduce BEA productivity weight — lower STATIC_RELATIVE_PRODUCTIVITY or increase BEA_SINGLE_YEAR_HW
  - Option B: Accept flags as real — expert Junior/Mid scores genuinely exceed empirical ceiling
  - Option C: Re-examine SENIORITY_TASK_WEIGHTS — Junior implementation fraction of 0.65 may be too low
