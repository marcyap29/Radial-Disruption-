"""
Generates the three output files from a list of per-pair result dicts.
"""

import json
import math
import csv
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import date

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).parent.parent / "output"


def _safe_pearsonr(xs: List[float], ys: List[float]) -> Optional[float]:
    """Pearson r without scipy dependency."""
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def _format_range(r: Optional[list]) -> str:
    if r is None:
        return "N/A"
    return f"[{r[0]:.3f}, {r[1]:.3f}]"


def write_json(results: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    logger.info(f"Wrote {path}")


def write_csv(results: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in results:
        rows.append({
            "Disruption":   r["disruption"],
            "Industry":     r["industry"],
            "Expert f_ij":  r["expert_fij"],
            "Occ Point":    r["occ_point"] if r["occ_point"] is not None else "N/A",
            "Occ Range":    _format_range(r["occ_range"]),
            "In Occ Range": _bool_str(r["in_occ_range"]),
            "IO Point":     r["io_point"] if r["io_point"] is not None else "N/A",
            "IO Range":     _format_range(r["io_range"]),
            "In IO Range":  _bool_str(r["in_io_range"]),
            "Convergent":   "Yes" if r["convergent"] else "No",
        })

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"Wrote {path}")


def _bool_str(v: Optional[bool]) -> str:
    if v is None:
        return "N/A"
    return "Yes" if v else "No"


def write_report(results: List[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    total = len(results)
    has_occ = [r for r in results if r["in_occ_range"] is not None]
    has_io  = [r for r in results if r["in_io_range"]  is not None]
    has_both = [r for r in results if r["in_occ_range"] is not None and r["in_io_range"] is not None]

    pct_occ  = sum(1 for r in has_occ  if r["in_occ_range"]) / len(has_occ)  * 100 if has_occ  else 0
    pct_io   = sum(1 for r in has_io   if r["in_io_range"])  / len(has_io)   * 100 if has_io   else 0
    pct_both = sum(1 for r in has_both if r["convergent"])    / len(has_both) * 100 if has_both else 0

    # Inter-method correlation: occ_point vs io_point where both exist
    paired = [(r["occ_point"], r["io_point"]) for r in results
              if r["occ_point"] is not None and r["io_point"] is not None
              and not math.isnan(r["occ_point"]) and not math.isnan(r["io_point"])]
    pearson_r = _safe_pearsonr([p[0] for p in paired], [p[1] for p in paired]) if paired else None

    # Per-case summary
    cases_seen = {}
    for r in results:
        cases_seen.setdefault(r["disruption"], []).append(r)

    lines = [
        f"# RDF Empirical Validation Report",
        f"",
        f"**Generated:** {date.today().isoformat()}  ",
        f"**Total industry pairs evaluated:** {total}  ",
        f"**Pairs with occupational overlap data:** {len(has_occ)}  ",
        f"**Pairs with IO overlap data:** {len(has_io)}  ",
        f"",
        f"---",
        f"",
        f"## Summary Statistics",
        f"",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Expert scores within occupational range | {pct_occ:.1f}% ({sum(1 for r in has_occ if r['in_occ_range'])}/{len(has_occ)}) |",
        f"| Expert scores within IO range | {pct_io:.1f}% ({sum(1 for r in has_io if r['in_io_range'])}/{len(has_io)}) |",
        f"| Expert scores within **both** ranges (convergent) | {pct_both:.1f}% ({sum(1 for r in has_both if r['convergent'])}/{len(has_both)}) |",
        f"| Inter-method Pearson r (occ vs IO point estimates) | {pearson_r if pearson_r is not None else 'N/A'} |",
        f"",
    ]

    # Claim verdict
    threshold = 80.0
    if pct_both >= threshold:
        lines += [
            f"**VERDICT: PASS** — {pct_both:.1f}% of expert scores fall within both derived ranges (threshold: {threshold}%).  ",
            f"The paper can claim: *expert judgment f_ij scores are consistent with empirically-derived "
            f"occupational and supply-chain overlap measures.*",
        ]
    else:
        lines += [
            f"**VERDICT: FAIL** — Only {pct_both:.1f}% of expert scores fall within both derived ranges "
            f"(threshold: {threshold}%).  ",
            f"Review flagged pairs below before making the consistency claim.",
        ]

    lines += ["", "---", "", "## Per-Case Results", ""]

    for case_label, case_results in cases_seen.items():
        lines.append(f"### {case_label}")
        lines.append("")
        lines.append("| Industry | Expert | Occ Range | In Occ? | IO Range | In IO? | Convergent |")
        lines.append("|----------|--------|-----------|---------|----------|--------|------------|")
        for r in case_results:
            lines.append(
                f"| {r['industry']} | {r['expert_fij']} "
                f"| {_format_range(r['occ_range'])} | {_bool_str(r['in_occ_range'])} "
                f"| {_format_range(r['io_range'])} | {_bool_str(r['in_io_range'])} "
                f"| {'Yes' if r['convergent'] else 'No'} |"
            )
        lines.append("")

    # Flag disagreements
    disagreements = [r for r in results if r["in_occ_range"] is False or r["in_io_range"] is False]
    if disagreements:
        lines += ["---", "", "## Flagged Disagreements", ""]
        for r in disagreements:
            issues = []
            if r["in_occ_range"] is False:
                issues.append(f"expert {r['expert_fij']} outside occ range {_format_range(r['occ_range'])}")
            if r["in_io_range"] is False:
                issues.append(f"expert {r['expert_fij']} outside IO range {_format_range(r['io_range'])}")
            lines.append(f"- **{r['disruption']} / {r['industry']}**: {'; '.join(issues)}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Methodology Notes",
        "",
        "**Occupational overlap (BLS OEWS):** Bray-Curtis similarity between industry occupation-share "
        "vectors. For each disrupting industry D and adjacent industry i, overlap = Σ min(share_D(occ), "
        "share_i(occ)) across all occupations significant in D (≥0.5% of workforce). Range bands are "
        "point estimate ± 0.10.",
        "",
        "**Supply-chain overlap (BEA IO Use tables):** Same metric applied to commodity-input vectors. "
        "For each supplier commodity s, share_X(s) = inputs from s / total inputs for industry X. "
        "Overlap = Σ min(share_D(s), share_i(s)) across suppliers significant in D (≥1% of inputs). "
        "Range bands are point estimate ± 0.10.",
        "",
        "**Convergence criterion:** An expert score is convergent if it falls within *both* the "
        "occupational range and the IO range simultaneously.",
        "",
        "**AI coding case note:** Because the disrupting industry (NAICS 511210) and adjacent industry "
        "(NAICS 541511) share the same broad sector, occupational overlap uses a SOC-specific metric "
        "measuring the geometric mean of each occupation's share in both industries. IO overlap uses "
        "sector-level codes (5112 vs 5415).",
    ]

    path.write_text("\n".join(lines))
    logger.info(f"Wrote {path}")
