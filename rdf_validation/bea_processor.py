"""
BEA Input-Output Use table processor.

Downloads the annual IO Use table for a given year, extracts the vector of
supplier inputs for each industry, and computes supply-chain overlap between
the disrupting industry D and each adjacent industry i.

Overlap definition:
    For each commodity/supplier row s:
        share_D(s) = input from s as fraction of D's total inputs
        share_i(s) = input from s as fraction of i's total inputs
    io_overlap(D, i) = sum_s min(share_D(s), share_i(s))

This mirrors the occupational overlap metric: bounded [0, 1], interpretable
as "fraction of substrate that is shared via common supplier relationships."
"""

import io
import logging
import re
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Optional, Tuple

from .config import (
    BEA_IO_URLS,
    BEA_IO_SUMMARY_URLS,
    IO_SIGNIFICANCE_THRESHOLD,
    BAND_HALF_WIDTH,
)

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent / "data_cache" / "bea"


def _cache_path(year: int) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"io_use_{year}.parquet"


def _download_bytes(url: str) -> bytes:
    logger.info(f"Downloading {url}")
    resp = requests.get(url, timeout=180)
    resp.raise_for_status()
    return resp.content


def _load_io_use_table(year: int) -> pd.DataFrame:
    """
    Load BEA IO Use table for `year`.
    Returns a DataFrame where:
        index  = commodity/supplier codes (strings)
        columns = industry codes (strings)
        values  = dollar flows (millions)

    Uses parquet cache if present.
    """
    cache = _cache_path(year)
    if cache.exists():
        logger.info(f"Loading BEA IO {year} from cache")
        df = pd.read_parquet(cache)
        return df

    # Try detail table first, fall back to summary
    urls_to_try = []
    if year in BEA_IO_URLS:
        urls_to_try.append(("detail", BEA_IO_URLS[year]))
    if year in BEA_IO_SUMMARY_URLS:
        urls_to_try.append(("summary", BEA_IO_SUMMARY_URLS[year]))

    raw = None
    for kind, url in urls_to_try:
        try:
            raw = _download_bytes(url)
            logger.info(f"  Using {kind} table for {year}")
            break
        except Exception as e:
            logger.warning(f"  {kind} table failed: {e}")

    if raw is None:
        raise RuntimeError(f"Could not download BEA IO table for {year}")

    df = _parse_bea_excel(raw, year)
    df.to_parquet(cache)
    logger.info(f"  Cached IO table {year}: {df.shape} → {cache}")
    return df


def _parse_bea_excel(raw: bytes, year: int) -> pd.DataFrame:
    """
    Parse BEA Use table from raw Excel bytes.
    BEA format: first few rows are header noise; the table proper begins with
    a row where column 0 is 'Code' or blank and subsequent columns are industry codes.
    """
    xl = pd.ExcelFile(io.BytesIO(raw), engine="openpyxl")
    sheet = xl.sheet_names[0]
    raw_df = xl.parse(sheet, header=None, dtype=str)

    # Find the header row: look for a row with 'Code' or lots of numeric-ish entries
    header_row = _find_header_row(raw_df)
    logger.debug(f"  Header row index: {header_row}")

    # Re-read with correct header
    df = xl.parse(sheet, header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    # First column should be commodity codes; rename it
    first_col = df.columns[0]
    df = df.rename(columns={first_col: "commodity_code"})
    df["commodity_code"] = df["commodity_code"].str.strip()

    # Drop rows that aren't actual commodity/input rows (totals, blanks, labels)
    df = df.dropna(subset=["commodity_code"])
    df = df[df["commodity_code"].str.len() > 0]
    # Remove known footer rows
    exclude_patterns = r"^(T|Total|Value added|GDP|Components|Footnote|Note|Source)"
    df = df[~df["commodity_code"].str.match(exclude_patterns, na=False)]

    df = df.set_index("commodity_code")

    # Convert all value columns to numeric
    for col in df.columns:
        df[col] = pd.to_numeric(df[col].str.replace(",", ""), errors="coerce")

    df = df.fillna(0.0)
    # Drop columns that are all zero or metadata strings
    numeric_cols = [c for c in df.columns if df[c].sum() != 0]
    df = df[numeric_cols]

    return df


def _find_header_row(raw_df: pd.DataFrame) -> int:
    """Heuristic: find the row index that serves as the column header."""
    for i, row in raw_df.iterrows():
        vals = row.dropna().astype(str).tolist()
        # Header row typically has 'Code' in first cell or many short uppercase codes
        if any(v.strip().lower() in ("code", "commodity", "industry") for v in vals[:3]):
            return i
        # Or: row with 10+ short alphanumeric tokens (industry codes)
        short_tokens = [v for v in vals if re.match(r"^[A-Z0-9]{2,8}$", v.strip())]
        if len(short_tokens) >= 10:
            return i
    return 5  # fallback


def _get_industry_input_shares(
    io_df: pd.DataFrame, industry_code: str
) -> Optional[pd.Series]:
    """
    Return the input share vector for a given industry column.
    Tries exact match, then prefix match on column names.
    """
    # Exact match
    if industry_code in io_df.columns:
        col = io_df[industry_code]
    else:
        # Prefix match: find columns starting with the code
        matches = [c for c in io_df.columns if c.startswith(industry_code)]
        if not matches:
            logger.warning(f"Industry code {industry_code!r} not found in IO table columns")
            return None
        col = io_df[matches].sum(axis=1)

    total = col.sum()
    if total == 0:
        return None
    return col / total


def compute_io_overlap(
    year: int,
    disrupting_naics: str,
    adjacent_naics: str,
    fallback_year: Optional[int] = None,
) -> float:
    """
    Bray-Curtis supply-chain overlap between disrupting and adjacent NAICS.
    Returns value in [0, 1], or nan if data unavailable.
    """
    try:
        io_df = _load_io_use_table(year)
    except Exception as e:
        if fallback_year:
            logger.warning(f"IO {year} failed ({e}), trying {fallback_year}")
            try:
                io_df = _load_io_use_table(fallback_year)
            except Exception as e2:
                logger.error(f"IO fallback {fallback_year} also failed: {e2}")
                return float("nan")
        else:
            logger.error(f"IO {year} failed: {e}")
            return float("nan")

    shares_d = _get_industry_input_shares(io_df, _naics_to_bea(disrupting_naics))
    shares_i = _get_industry_input_shares(io_df, _naics_to_bea(adjacent_naics))

    if shares_d is None or shares_i is None:
        return float("nan")

    # Filter to significant suppliers in disrupting industry
    significant = shares_d[shares_d >= IO_SIGNIFICANCE_THRESHOLD].index
    shares_d_sig = shares_d.loc[significant]

    common = shares_d_sig.index.intersection(shares_i.index)
    if common.empty:
        return 0.0

    overlap = sum(min(float(shares_d_sig[s]), float(shares_i[s])) for s in common)
    return float(overlap)


def _naics_to_bea(naics: str) -> str:
    """
    Map NAICS codes to BEA IO table industry codes.
    BEA uses its own sector scheme; this provides approximate mappings
    for the codes used in our cases.
    """
    # BEA IO summary-level codes (approximate; detail-level varies by year)
    mapping = {
        # Computer/electronics manufacturing
        "334":    "334",
        "3344":   "3344",
        # Machinery
        "333":    "333",
        # Telecom
        "517":    "517",
        # Software
        "5112":   "5112",
        "511210": "5112",
        "511":    "511",
        # Amusements/gaming
        "7132":   "713",
        # Custom software / IT services
        "541511": "5415",
        "5415":   "5415",
        # Travel
        "5615":   "5615",
        # Publishing
        "5111":   "511",
        # Video rental / rental services
        "5322":   "532",
        # Music retail / electronics retail
        "4512":   "441",
    }
    return mapping.get(naics, naics)


def io_overlap_to_range(point: float) -> Optional[Tuple[float, float]]:
    """Convert a point estimate to a [low, high] range band."""
    if np.isnan(point):
        return None
    low = max(0.0, point - BAND_HALF_WIDTH)
    high = min(1.0, point + BAND_HALF_WIDTH)
    return (round(low, 3), round(high, 3))
