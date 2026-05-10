"""
BLS OEWS bulk-download processor.

Downloads industry-level OEWS files, extracts occupation employment by NAICS,
and computes occupational overlap (f_ij proxy) between the disrupting industry
and each adjacent industry.

Overlap definition:
    For disrupting industry D and adjacent industry i,
    occ_overlap(D, i) = sum of min(share_D(occ), share_i(occ)) for all occ
    where share_X(occ) = employment in occ / total employment in industry X

This is the Bray-Curtis-style overlap; bounded [0, 1].
"""

import io
import os
import re
import zipfile
import logging
import requests
import pandas as pd
from pathlib import Path
from functools import lru_cache
from typing import Dict, Optional

from .config import (
    BLS_BULK_URL_TEMPLATE,
    BLS_NATIONAL_URL_TEMPLATE,
    OCC_SIGNIFICANCE_THRESHOLD,
    BAND_HALF_WIDTH,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data_cache" / "bls"


def _year_short(year: int) -> str:
    return str(year)[-2:]


def _cache_path(year: int, kind: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"oews_{year}_{kind}.parquet"


def _download_zip(url: str) -> bytes:
    logger.info(f"Downloading {url}")
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    return resp.content


def _find_xlsx_in_zip(zf: zipfile.ZipFile) -> str:
    """Return the first .xlsx or .xls filename in the zip."""
    for name in zf.namelist():
        if name.lower().endswith((".xlsx", ".xls")):
            return name
    raise FileNotFoundError(f"No Excel file found in zip. Contents: {zf.namelist()}")


def _load_oews_industry_frame(year: int) -> pd.DataFrame:
    """
    Load OEWS industry-level data for a given year.
    Returns DataFrame with columns: naics, occ_code, tot_emp (float).
    Uses parquet cache if available.
    """
    cache = _cache_path(year, "industry")
    if cache.exists():
        logger.info(f"Loading BLS OEWS {year} from cache")
        return pd.read_parquet(cache)

    ys = _year_short(year)
    url = BLS_BULK_URL_TEMPLATE.format(year_short=ys)
    try:
        raw = _download_zip(url)
    except Exception as e:
        logger.warning(f"Industry zip failed ({e}), trying national file")
        url = BLS_NATIONAL_URL_TEMPLATE.format(year_short=ys)
        raw = _download_zip(url)

    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        excel_name = _find_xlsx_in_zip(zf)
        logger.info(f"  Reading {excel_name}")
        with zf.open(excel_name) as f:
            df = pd.read_excel(f, dtype=str, engine="openpyxl")

    df.columns = [c.strip().lower() for c in df.columns]

    # Normalise column names across OEWS vintage variations
    col_map = {}
    for col in df.columns:
        if re.search(r"naics", col):
            col_map[col] = "naics"
        elif re.search(r"occ.?code", col):
            col_map[col] = "occ_code"
        elif re.search(r"tot.?emp", col):
            col_map[col] = "tot_emp"
        elif col == "i_group":
            col_map[col] = "i_group"
    df = df.rename(columns=col_map)

    required = {"naics", "occ_code", "tot_emp"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OEWS {year}: missing columns {missing}. Found: {list(df.columns)}")

    # Keep only industry-level rows (not cross-industry aggregates)
    if "i_group" in df.columns:
        df = df[df["i_group"].isin(["3", "4", "5", "sector", "3-digit", "4-digit", "NAICS"])]

    # Convert employment to numeric; suppress ** / # suppression markers
    df["tot_emp"] = pd.to_numeric(df["tot_emp"].str.replace(",", ""), errors="coerce")
    df = df.dropna(subset=["tot_emp"])
    df = df[df["tot_emp"] > 0]

    df = df[["naics", "occ_code", "tot_emp"]].copy()
    df["naics"] = df["naics"].str.strip()
    df["occ_code"] = df["occ_code"].str.strip()

    df.to_parquet(cache, index=False)
    logger.info(f"  Cached {len(df):,} rows → {cache}")
    return df


def _naics_prefix_match(df: pd.DataFrame, naics_prefix: str) -> pd.DataFrame:
    """Return rows whose naics starts with naics_prefix."""
    return df[df["naics"].str.startswith(naics_prefix)]


def _industry_occ_shares(df: pd.DataFrame, naics_prefix: str) -> pd.Series:
    """
    For a given NAICS (prefix), aggregate employment across all matching
    sub-industries, then return occupation share series indexed by occ_code.
    """
    sub = _naics_prefix_match(df, naics_prefix)
    if sub.empty:
        return pd.Series(dtype=float)
    agg = sub.groupby("occ_code")["tot_emp"].sum()
    return agg / agg.sum()


def compute_occ_overlap(year: int, disrupting_naics: str, adjacent_naics: str) -> float:
    """
    Bray-Curtis occupational overlap between disrupting and adjacent NAICS.
    Returns a value in [0, 1].
    """
    df = _load_oews_industry_frame(year)
    shares_d = _industry_occ_shares(df, disrupting_naics)
    shares_i = _industry_occ_shares(df, adjacent_naics)

    if shares_d.empty or shares_i.empty:
        logger.warning(f"No OEWS data for NAICS {disrupting_naics} or {adjacent_naics} in {year}")
        return float("nan")

    # Only count occupations that are meaningful in the disrupting industry
    significant_d = shares_d[shares_d >= OCC_SIGNIFICANCE_THRESHOLD].index
    shares_d = shares_d.loc[significant_d]

    common = shares_d.index.intersection(shares_i.index)
    if common.empty:
        return 0.0

    overlap = sum(min(shares_d[occ], shares_i[occ]) for occ in common)
    return float(overlap)


def compute_occ_overlap_soc(
    year: int,
    disrupting_naics: str,
    adjacent_naics: str,
    target_soc: str,
) -> float:
    """
    For the AI coding case: overlap between the disrupting industry and a
    specific occupation (soc_code) within the adjacent NAICS.

    Metric: share of total disrupting-industry employment in target_soc,
    weighted by the share of adjacent industry's employment that is target_soc.
    This gives high overlap when the disrupting industry heavily employs the
    same occupational type that defines the adjacent "tier".
    """
    df = _load_oews_industry_frame(year)
    shares_d = _industry_occ_shares(df, disrupting_naics)
    shares_i = _industry_occ_shares(df, adjacent_naics)

    if shares_d.empty or shares_i.empty:
        logger.warning(f"No OEWS data: {disrupting_naics} or {adjacent_naics} in {year}")
        return float("nan")

    # Match 6-digit SOC or its major group (first 2 digits)
    soc_prefix = target_soc[:2]

    def _soc_share(shares: pd.Series, soc: str) -> float:
        # Exact match first
        if soc in shares.index:
            return float(shares[soc])
        # Prefix match
        sub = shares[shares.index.str.startswith(soc_prefix)]
        return float(sub.sum()) if not sub.empty else 0.0

    share_d = _soc_share(shares_d, target_soc)
    share_i = _soc_share(shares_i, target_soc)

    # Geometric mean of both sides: high only when both industries engage the occupation
    if share_d == 0 or share_i == 0:
        return 0.0
    return float((share_d * share_i) ** 0.5)


def occ_overlap_to_range(point: float) -> Optional[tuple]:
    """Convert a point estimate to a [low, high] range band."""
    if pd.isna(point):
        return None
    low = max(0.0, point - BAND_HALF_WIDTH)
    high = min(1.0, point + BAND_HALF_WIDTH)
    return (round(low, 3), round(high, 3))
