# Bug Prevention — Radial Disruption

Known failure patterns and how to avoid them.

---

## Download failures

**Pattern:** `requests.exceptions.ConnectionError` or `HTTPError 404` during download.

**Cause:** BLS and BEA publish new data releases and move files. URLs that worked last
quarter may 404 today.

**Fix:**
- `download.py` tries multiple URL patterns per source (list in `config.py → URLS`).
- If all patterns fail, it logs a clear `[DOWNLOAD FAILED]` message with the URLs tried
  and falls back to the labeled fallback dataset (QCEW for BEA; exits for BLS OEWS).
- Never silently substitute data. Always log what was used.

---

## O*NET column name variance

**Pattern:** `KeyError: 'Scale ID'` or `KeyError: 'Task ID'` when reading O*NET files.

**Cause:** O*NET's tab-delimited files occasionally rename columns between versions
(e.g., `Scale ID` vs `Scale Name`).

**Fix:**
- `onet_seniority.py` prints the actual column names on first read.
- Check the print output and update `ONET_COL_ALIASES` in `config.py` if column names differ.

---

## BLS OEWS suppressed values

**Pattern:** Wage computation returns `NaN` or raises a `ValueError` for specific SOC codes.

**Cause:** BLS OEWS suppresses wage estimates with `*` (suppressed) or `#` (top-coded at
$239,200) for small-cell occupations.

**Fix:**
- `bls_method.py` strips `*` and replaces `#` with `239200` before converting to float.
- If a SOC code has no usable wage after stripping, the wage adjustment factor defaults to 1.0
  (neutral) and the report notes the suppression.

---

## OEWS column name variance (historical files)

**Pattern:** `KeyError: 'H_MEDIAN'` when reading the 1997 historical OEWS file.

**Cause:** Early OEWS files used different column headers than the current format.

**Fix:**
- `bls_method.py` normalizes column names via `BLS_COL_ALIASES` in `config.py`.
- Current known aliases: `MEDIAN` → `H_MEDIAN`, `HRLY_WAGE` → `H_MEAN`.

---

## Expert scores CSV encoding

**Pattern:** `UnicodeDecodeError` or extra blank rows when loading `expert_scores.csv`.

**Cause:** Excel saves CSV with BOM or Windows line endings.

**Fix:**
- `validate.py` reads with `encoding='utf-8-sig'` and `skipinitialspace=True`.
- If you edit the file in Excel, re-save as "CSV UTF-8 (comma delimited)".

---

## BEA Section 6 sheet name variance

**Pattern:** `SheetNotFoundError` when opening the BEA Excel file.

**Cause:** BEA renames sheets between annual releases.

**Fix:**
- `bea_method.py` prints available sheet names if the expected sheet is not found.
- Update `BEA_SHEET_NAMES` in `config.py` with the correct sheet name.

---

## Range clamping

**Pattern:** BLS or BEA range lower bound goes negative.

**Cause:** Low ATF × wage_factor combination minus uncertainty half-width.

**Fix:** Both method files clamp ranges to [0.0, 10.0]. This is expected behavior, not a bug.
If many ranges are hitting the floor, the ATF or wage_factor parameters in `config.py` may need
recalibration.
