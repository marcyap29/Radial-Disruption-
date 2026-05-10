"""
Derives f_ij range bands for each industry pair and checks consistency
with expert judgment baseline scores.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

from .config import CASES, BAND_HALF_WIDTH
from .bls_processor import (
    compute_occ_overlap,
    compute_occ_overlap_soc,
    occ_overlap_to_range,
)
from .bea_processor import compute_io_overlap, io_overlap_to_range

logger = logging.getLogger(__name__)


def _in_range(value: float, band: Optional[Tuple[float, float]]) -> Optional[bool]:
    if band is None:
        return None
    return band[0] <= value <= band[1]


def run_case(case_key: str) -> List[Dict]:
    """
    Run both BLS and BEA overlap calculations for a named case.
    Returns a list of result dicts, one per industry pair.
    """
    case = CASES[case_key]
    label = case["label"]
    d_naics = case["disrupting_naics"]
    bls_year = case["bls_year"]
    bea_year = case["bea_year"]
    is_soc_case = "adjacent_naics" in case  # AI coding case

    results = []

    for pair in case["pairs"]:
        pair_label = pair["label"]
        expert = pair["expert_fij"]

        logger.info(f"  [{label}] {pair_label}")

        # --- Occupational overlap ---
        if is_soc_case:
            adj_naics = case["adjacent_naics"]
            occ_point = compute_occ_overlap_soc(
                bls_year, d_naics, adj_naics, pair["soc"]
            )
        else:
            adj_naics = pair["naics"]
            occ_point = compute_occ_overlap(bls_year, d_naics, adj_naics)

        occ_range = occ_overlap_to_range(occ_point)

        # --- IO supply-chain overlap ---
        if is_soc_case:
            # Both disrupting and adjacent share the same or near-same NAICS;
            # IO overlap uses the sector-level code to avoid trivial self-overlap
            io_point = compute_io_overlap(
                bea_year, d_naics, case["adjacent_naics"],
                fallback_year=_fallback_year(bea_year),
            )
        else:
            io_point = compute_io_overlap(
                bea_year, d_naics, pair.get("bea_code", adj_naics),
                fallback_year=pair.get("bea_fallback_year"),
            )

        io_range = io_overlap_to_range(io_point)

        # --- Consistency checks ---
        in_occ = _in_range(expert, occ_range)
        in_io = _in_range(expert, io_range)
        convergent = (in_occ is True) and (in_io is True)

        results.append({
            "disruption": label,
            "case_key": case_key,
            "industry": pair_label,
            "expert_fij": expert,
            "occ_point": round(occ_point, 4) if not _isnan(occ_point) else None,
            "occ_range": list(occ_range) if occ_range else None,
            "in_occ_range": in_occ,
            "io_point": round(io_point, 4) if not _isnan(io_point) else None,
            "io_range": list(io_range) if io_range else None,
            "in_io_range": in_io,
            "convergent": convergent,
            "naics_adjacent": adj_naics if not is_soc_case else case["adjacent_naics"],
            "soc": pair.get("soc"),
            "bls_year": bls_year,
            "bea_year": bea_year,
        })

    return results


def run_all_cases() -> List[Dict]:
    all_results = []
    for key in CASES:
        logger.info(f"Running case: {key}")
        try:
            all_results.extend(run_case(key))
        except Exception as e:
            logger.error(f"Case {key} failed: {e}", exc_info=True)
    return all_results


def _isnan(v) -> bool:
    try:
        return math.isnan(v)
    except (TypeError, ValueError):
        return False


def _fallback_year(year: int) -> Optional[int]:
    fallbacks = {1997: 2002, 2002: 2007, 2007: 2012, 2021: 2017}
    return fallbacks.get(year)
