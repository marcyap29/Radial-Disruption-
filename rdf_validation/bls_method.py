"""
BLS method: derive disruption range from OEWS wages + O*NET ATF.

Algorithm per (role, seniority):
1. Get the weighted-average ATF across the role's SOC code(s).
2. Get the median hourly wage for each SOC code from OEWS.
3. Compute a wage adjustment factor: lower wages → slightly higher disruption.
4. BLS disruption point = ATF × 10 × wage_factor
5. BLS range = [point − BLS_UNCERTAINTY_HW, point + BLS_UNCERTAINTY_HW], clamped [0, 10].

The 1997 historical OEWS is loaded and compared to current OEWS.
Both years are included in the report as context (not used to widen the range — the
range comes from methodological uncertainty, not year-over-year variance).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from .config import (
    RDF_MIN, RDF_MAX,
    BLS_UNCERTAINTY_HW,
    WAGE_ADJUSTMENT_STRENGTH,
    BLS_COL_ALIASES,
    INTERNET_EARLIEST_OEWS,
    INTERNET_NOTE,
)
from .crosswalk import CrosswalkEntry
from .onet_seniority import SeniorityProfile

log = logging.getLogger(__name__)


@dataclass
class BLSRange:
    role: str
    seniority: str
    soc_code: str
    atf: float
    median_hourly_wage: Optional[float]
    wage_factor: float
    disruption_point: float
    low: float
    high: float
    historical_median_wage_1997: Optional[float]
    notes: list[str]


# ---------------------------------------------------------------------------
# OEWS loading
# ---------------------------------------------------------------------------

def _clean_wage(val) -> Optional[float]:
    """Convert BLS wage cell to float. Handle '*' (suppressed) and '#' (top-coded)."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    if s == "*":
        return None   # suppressed — too few observations
    if s == "#":
        return 239200.0 / 2080  # top-coded annual; convert to hourly
    try:
        return float(s)
    except ValueError:
        return None


def _load_oews(path: Path, year_label: str) -> pd.DataFrame:
    """Load BLS OEWS national Excel file → DataFrame with SOC code and wages."""
    try:
        # BLS OEWS files may have a header row that is not row 0
        # Try reading with default header, fall back to header=1
        for header_row in (0, 1, 2):
            try:
                df = pd.read_excel(path, header=header_row, dtype=str)
                # Normalize column names
                df.columns = [c.strip().upper() for c in df.columns]
                for old, new in BLS_COL_ALIASES.items():
                    if old.upper() in df.columns:
                        df = df.rename(columns={old.upper(): new})
                if "OCC_CODE" in df.columns and ("H_MEDIAN" in df.columns or "A_MEDIAN" in df.columns):
                    log.info("[BLS OEWS %s] Loaded %d rows (header row=%d)", year_label, len(df), header_row)
                    return df
            except Exception:
                continue
        log.error("[BLS OEWS %s] Could not parse %s", year_label, path.name)
        return pd.DataFrame()
    except Exception as exc:
        log.error("[BLS OEWS %s] Failed to read %s: %s", year_label, path.name, exc)
        return pd.DataFrame()


def _get_median_wage(oews: pd.DataFrame, soc_code: str) -> Optional[float]:
    """Extract median hourly wage for a SOC code. Returns None if suppressed."""
    if oews.empty:
        return None
    row = oews[oews["OCC_CODE"] == soc_code]
    if row.empty:
        return None
    for col in ("H_MEDIAN", "A_MEDIAN"):
        if col in row.columns:
            val = _clean_wage(row.iloc[0][col])
            if val is not None:
                # If annual, convert to hourly
                if col == "A_MEDIAN":
                    val = val / 2080
                return val
    return None


# ---------------------------------------------------------------------------
# QCEW wage fallback (used when OEWS is unavailable)
# ---------------------------------------------------------------------------

def _load_qcew_wages(qcew_dir: Optional[Path]) -> dict[str, float]:
    """Load avg_annual_pay by NAICS from QCEW per-industry CSV files.

    Returns {naics: hourly_wage_equivalent}.
    Private sector (own_code=5), national (area_fips=US000).
    """
    if not qcew_dir or not qcew_dir.is_dir():
        return {}

    subdir = qcew_dir / "2023.annual.by_industry"
    search_dir = subdir if subdir.is_dir() else qcew_dir

    wages: dict[str, float] = {}
    targets = ["5415", "5182", "5112", "51", "10"]

    for naics in targets:
        path = next(
            (p for p in search_dir.iterdir() if p.suffix == ".csv" and f" {naics} " in p.name),
            None,
        )
        if path is None:
            continue
        try:
            df = pd.read_csv(path, dtype=str)
            mask = (df["area_fips"] == "US000") & (df["own_code"] == "5") & (df["qtr"] == "A")
            row = df[mask]
            if not row.empty:
                pay = float(row.iloc[0]["avg_annual_pay"].replace(",", ""))
                wages[naics] = pay / 2080   # annual → hourly
                log.info("[QCEW wages] NAICS %s: $%.2f/hr ($%.0f/yr)", naics, wages[naics], pay)
        except Exception as exc:
            log.warning("[QCEW wages] NAICS %s: %s", naics, exc)

    return wages


# ---------------------------------------------------------------------------
# Wage normalization
# ---------------------------------------------------------------------------

def _build_wage_index(oews: pd.DataFrame, soc_codes: list[str]) -> dict[str, float]:
    """Compute normalized wage for each SOC code in [0, 1] relative to the set."""
    wages = {}
    for soc in soc_codes:
        w = _get_median_wage(oews, soc)
        if w is not None:
            wages[soc] = w

    if not wages:
        return {soc: 0.5 for soc in soc_codes}

    min_w, max_w = min(wages.values()), max(wages.values())
    span = max_w - min_w or 1.0
    return {soc: (wages.get(soc, (min_w + max_w) / 2) - min_w) / span for soc in soc_codes}


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_bls_ranges(
    oews_current_path: Optional[Path],
    oews_historical_path: Optional[Path],
    profiles: dict[str, SeniorityProfile],
    entries: list[CrosswalkEntry],
    qcew_dir: Optional[Path] = None,
) -> dict[tuple[str, str], BLSRange]:
    """Return BLSRange for every (role, seniority) pair."""

    oews_now  = _load_oews(oews_current_path, "current") if oews_current_path else pd.DataFrame()
    oews_1997 = _load_oews(oews_historical_path, str(INTERNET_EARLIEST_OEWS)) if oews_historical_path else pd.DataFrame()

    qcew_wages: dict[str, float] = {}
    if oews_now.empty:
        log.warning("[BLS] OEWS unavailable — falling back to QCEW industry wages for adjustment.")
        qcew_wages = _load_qcew_wages(qcew_dir)
        if not qcew_wages:
            log.warning("[BLS] QCEW wages also unavailable — wage adjustment factor = 1.0 (neutral).")

    # Build OEWS wage index (or QCEW fallback by NAICS → we'll handle per-entry below)
    all_soc = list(profiles.keys())
    wage_index = _build_wage_index(oews_now, all_soc)  # empty → all 0.5 (neutral)

    results: dict[tuple[str, str], BLSRange] = {}

    for entry in entries:
        for seniority in ("Junior", "Mid", "Senior"):
            notes = []

            # Weighted ATF across primary + secondary SOC codes
            weighted_atf = 0.0
            total_weight = 0.0
            wage_sum = 0.0
            wage_count = 0

            for soc, weight in entry.weighted_soc_codes:
                if soc not in profiles:
                    log.warning("[BLS] No O*NET profile for SOC %s — skipping in weight", soc)
                    continue
                atf_val = profiles[soc].atf_by_seniority.get(seniority, profiles[soc].base_atf)
                weighted_atf += atf_val * weight
                total_weight += weight

                w = _get_median_wage(oews_now, soc)
                if w is not None:
                    wage_sum += w * weight
                    wage_count += weight

            if total_weight > 0:
                weighted_atf /= total_weight
            else:
                weighted_atf = 0.5
                notes.append("No O*NET profiles found — ATF defaulted to 0.50")

            # Wage factor — prefer OEWS SOC wages; fall back to QCEW NAICS wages
            if wage_count > 0:
                avg_wage = wage_sum / wage_count
                norm = wage_index.get(entry.primary_code, 0.5)
                wage_factor = 1.0 + WAGE_ADJUSTMENT_STRENGTH * (1.0 - norm)
            elif qcew_wages:
                # QCEW is keyed by NAICS; use the entry's BEA NAICS as proxy
                naics = entry.bea_naics
                sector_wage = qcew_wages.get(naics, qcew_wages.get("51"))
                national_wage = qcew_wages.get("10")
                if sector_wage and national_wage and national_wage > 0:
                    avg_wage = sector_wage
                    # Normalize: sector vs national within QCEW range
                    all_qcew = list(qcew_wages.values())
                    min_w, max_w = min(all_qcew), max(all_qcew)
                    span = max_w - min_w or 1.0
                    norm = (sector_wage - min_w) / span
                    wage_factor = 1.0 + WAGE_ADJUSTMENT_STRENGTH * (1.0 - norm)
                    notes.append(
                        f"OEWS unavailable; QCEW NAICS {naics} wage ${sector_wage*2080:,.0f}/yr "
                        f"used for adjustment (factor={wage_factor:.3f})"
                    )
                else:
                    avg_wage = None
                    wage_factor = 1.0
                    notes.append("Wage data unavailable — wage adjustment factor = 1.0 (neutral)")
            else:
                avg_wage = None
                wage_factor = 1.0
                notes.append("Wage data unavailable — wage adjustment factor = 1.0 (neutral)")

            disruption_point = weighted_atf * 10.0 * wage_factor
            low  = max(RDF_MIN, round(disruption_point - BLS_UNCERTAINTY_HW, 2))
            high = min(RDF_MAX, round(disruption_point + BLS_UNCERTAINTY_HW, 2))

            # Historical wage for context
            hist_wage = _get_median_wage(oews_1997, entry.primary_code)
            if hist_wage is None and not oews_1997.empty:
                notes.append(f"SOC {entry.primary_code} not found in {INTERNET_EARLIEST_OEWS} OEWS")
            if oews_1997.empty:
                notes.append(INTERNET_NOTE)

            results[(entry.role, seniority)] = BLSRange(
                role=entry.role,
                seniority=seniority,
                soc_code=entry.primary_code,
                atf=round(weighted_atf, 4),
                median_hourly_wage=round(avg_wage, 2) if avg_wage else None,
                wage_factor=round(wage_factor, 4),
                disruption_point=round(disruption_point, 3),
                low=low,
                high=high,
                historical_median_wage_1997=round(hist_wage, 2) if hist_wage else None,
                notes=notes,
            )

            log.info(
                "[BLS] %s | %s | ATF=%.3f wage_factor=%.3f → point=%.2f range=[%.2f, %.2f]",
                entry.role, seniority, weighted_atf, wage_factor, disruption_point, low, high,
            )

    return results
