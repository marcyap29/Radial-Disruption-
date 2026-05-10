#!/usr/bin/env python3
"""
RDF Empirical Validation Tool
------------------------------
Derives f_ij range bands from BLS OEWS and BEA IO tables and compares them
against expert judgment baseline scores from the Radial Disruption Field framework.

Usage:
    python main.py [--cases smartphone internet ai] [--no-cache] [--output-dir ./output]
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--cases",
        nargs="+",
        choices=["smartphone", "internet", "ai", "all"],
        default=["all"],
        help="Which disruption cases to run (default: all)",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="Delete cached data files and re-download",
    )
    p.add_argument(
        "--output-dir",
        default="./output",
        help="Directory for output files (default: ./output)",
    )
    return p.parse_args()


def _resolve_cases(requested):
    from rdf_validation.config import CASES
    key_map = {
        "smartphone": "smartphone_2007",
        "internet":   "internet_1993",
        "ai":         "ai_coding_2022",
    }
    if "all" in requested:
        return list(CASES.keys())
    return [key_map[c] for c in requested if c in key_map]


def main():
    args = parse_args()
    output_dir = Path(args.output_dir)

    if args.no_cache:
        import shutil
        cache_dir = Path(__file__).parent / "data_cache"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
            logger.info(f"Cleared cache: {cache_dir}")

    from rdf_validation.config import CASES
    from rdf_validation.fij_calculator import run_case
    from rdf_validation.reporter import write_json, write_csv, write_report

    case_keys = _resolve_cases(args.cases)
    if not case_keys:
        logger.error("No valid cases selected.")
        sys.exit(1)

    logger.info(f"Running cases: {case_keys}")
    all_results = []
    for key in case_keys:
        logger.info(f"\n{'='*60}\nCase: {key}\n{'='*60}")
        try:
            results = run_case(key)
            all_results.extend(results)
            logger.info(f"  {len(results)} pairs computed")
        except Exception as e:
            logger.error(f"Case {key} failed: {e}", exc_info=True)

    if not all_results:
        logger.error("No results produced — check logs for errors.")
        sys.exit(1)

    # Write outputs
    json_path   = output_dir / "rdf_fij_derived_scores.json"
    csv_path    = output_dir / "rdf_fij_summary_table.csv"
    report_path = output_dir / "rdf_fij_validation_report.md"

    write_json(all_results, json_path)
    write_csv(all_results, csv_path)
    write_report(all_results, report_path)

    convergent = sum(1 for r in all_results if r["convergent"])
    evaluable  = sum(1 for r in all_results if r["in_occ_range"] is not None and r["in_io_range"] is not None)

    print(f"\n{'='*60}")
    print(f"RESULTS: {convergent}/{evaluable} pairs convergent "
          f"({100*convergent/evaluable:.1f}% — threshold 80%)" if evaluable else "No evaluable pairs")
    print(f"Outputs written to: {output_dir.resolve()}")
    print(f"  {json_path.name}")
    print(f"  {csv_path.name}")
    print(f"  {report_path.name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
