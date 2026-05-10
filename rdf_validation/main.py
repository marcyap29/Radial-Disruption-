"""
Entry point for the RDF validation pipeline.

Usage:
  python -m rdf_validation                 # full run (uses cache if present)
  python -m rdf_validation --refresh       # force re-download
  python -m rdf_validation --dry-run       # verify imports + crosswalk; no validation
"""

from __future__ import annotations

import argparse
import logging
import sys

from .config import CACHE_DIR, OUTPUT_DIR, SOC_CODES
from .crosswalk import CROSSWALK, all_roles
from .download import download_all
from .onet_seniority import compute_profiles
from .bls_method import compute_bls_ranges
from .bea_method import compute_bea_ranges
from .validate import load_expert_scores, run_validation
from .report import write_reports

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="RDF Validation Pipeline")
    parser.add_argument("--refresh", action="store_true",
                        help="Re-download all data even if cached")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check imports and crosswalk; skip download and validation")
    args = parser.parse_args()

    if args.dry_run:
        print("\n[DRY RUN] Checking crosswalk and imports...")
        print(f"  Roles defined: {all_roles()}")
        print(f"  SOC codes covered: {SOC_CODES}")
        print(f"  Cache dir: {CACHE_DIR}")
        print(f"  Output dir: {OUTPUT_DIR}")
        print("[DRY RUN] OK — no download or computation performed.\n")
        return

    # Step 1: Download
    log.info("=== Step 1: Download ===")
    files = download_all(refresh=args.refresh)

    # Step 2: O*NET seniority profiles
    log.info("=== Step 2: O*NET seniority profiles ===")
    profiles = {}
    if files.get("onet_task_statements") and files.get("onet_task_ratings"):
        profiles = compute_profiles(
            statements_path=files["onet_task_statements"],
            ratings_path=files["onet_task_ratings"],
            soc_codes=SOC_CODES,
        )
    else:
        log.warning("[MAIN] O*NET files unavailable — ATF defaulted to 0.50 for all SOC codes")
        from .onet_seniority import SeniorityProfile
        from .config import SENIORITY_LEVELS, SENIORITY_TASK_WEIGHTS, TASK_AI_AUTOMATABLE_FRACTION
        for soc in SOC_CODES:
            atf_by_sen = {}
            for level in SENIORITY_LEVELS:
                w = SENIORITY_TASK_WEIGHTS[level]
                atf_by_sen[level] = round(sum(w[cat] * TASK_AI_AUTOMATABLE_FRACTION[cat] for cat in w), 4)
            profiles[soc] = SeniorityProfile(
                soc_code=soc,
                onet_task_count=0,
                base_atf=0.50,
                atf_by_seniority=atf_by_sen,
            )

    # Step 3: BLS ranges
    log.info("=== Step 3: BLS ranges ===")
    bls_ranges = compute_bls_ranges(
        oews_current_path=files.get("bls_oews_current"),
        oews_historical_path=files.get("bls_oews_historical"),
        profiles=profiles,
        entries=CROSSWALK,
        qcew_dir=files.get("bls_qcew"),
    )

    # Step 4: BEA ranges
    log.info("=== Step 4: BEA ranges ===")
    bea_ranges = compute_bea_ranges(
        bea_path=files.get("bea_section6"),
        qcew_dir=files.get("bls_qcew"),
        profiles=profiles,
        entries=CROSSWALK,
    )

    # Step 5: Load expert scores and validate
    log.info("=== Step 5: Validation ===")
    expert_scores = load_expert_scores()
    results = run_validation(bls_ranges, bea_ranges, expert_scores)

    # Step 6: Write reports
    log.info("=== Step 6: Reports ===")
    write_reports(
        results=results,
        profiles=profiles,
        download_results=files,
        bls_ranges=bls_ranges,
        bea_ranges=bea_ranges,
    )
