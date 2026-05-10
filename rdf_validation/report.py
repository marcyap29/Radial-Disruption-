"""
Generate report.md, results.csv, results.json in rdf_validation/output/.

report.md sections:
  1. Run metadata (date, data sources, limitations)
  2. Crosswalk table (explicit — user validates this)
  3. Seniority profiles (O*NET-derived ATF per level — user validates these)
  4. Validation table (expert vs BLS vs BEA; CONSISTENT / FLAGGED)
  5. Flags summary
  6. Methodology notes
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import (
    OUTPUT_DIR,
    INTERNET_TARGET_YEAR, INTERNET_EARLIEST_OEWS, INTERNET_NOTE,
    BLS_UNCERTAINTY_HW,
    SENIORITY_TASK_WEIGHTS,
    TASK_AI_AUTOMATABLE_FRACTION,
)
from .crosswalk import as_table_rows, CROSSWALK
from .onet_seniority import SeniorityProfile
from .bls_method import BLSRange
from .bea_method import BEARange
from .validate import ValidationResult

log = logging.getLogger(__name__)

PASS_MARK  = "PASS"
FLAG_MARK  = "FLAG"
BLANK_MARK = "—"


# ---------------------------------------------------------------------------
# Markdown helpers
# ---------------------------------------------------------------------------

def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    col_widths = [max(len(h), max((len(str(r[i])) for r in rows), default=0))
                  for i, h in enumerate(headers)]
    sep = "| " + " | ".join("-" * w for w in col_widths) + " |"
    header = "| " + " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers)) + " |"
    data_rows = [
        "| " + " | ".join(str(r[i]).ljust(col_widths[i]) for i in range(len(headers))) + " |"
        for r in rows
    ]
    return "\n".join([header, sep] + data_rows)


# ---------------------------------------------------------------------------
# Report sections
# ---------------------------------------------------------------------------

def _section_metadata(download_results: dict) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    available = [k for k, v in download_results.items() if v is not None]
    failed    = [k for k, v in download_results.items() if v is None]

    lines = [
        "# RDF Validation Report",
        "",
        f"Generated: {now}  ",
        f"RDF scale: 0 (no disruption) – 10 (full disruption)  ",
        "",
        "## Data Sources",
        "",
        "| Source | Status |",
        "|---|---|",
    ]
    for k in available:
        lines.append(f"| {k} | cached ✓ |")
    for k in failed:
        lines.append(f"| {k} | **FAILED — see console log** |")

    lines += [
        "",
        "## Historical Data Limitation",
        "",
        f"> {INTERNET_NOTE}",
        "",
    ]
    return "\n".join(lines)


def _section_crosswalk() -> str:
    rows_raw = as_table_rows()
    headers = ["Role", "Primary SOC", "Primary Title", "Wt", "Secondary SOC",
               "Secondary Title", "Wt", "BEA NAICS", "Notes"]
    rows = [
        [
            r["Role"],
            r["Primary SOC"],
            r["Primary Title"],
            r["Primary Weight"],
            r["Secondary SOC"],
            r["Secondary Title"],
            r["Secondary Weight"],
            r["BEA NAICS"],
            r["Notes"][:80] + ("…" if len(r["Notes"]) > 80 else ""),
        ]
        for r in rows_raw
    ]
    table = _md_table(headers, rows)

    return "\n".join([
        "## Industry-to-SOC Crosswalk",
        "",
        "**Review this table.** Every role-to-SOC mapping is explicit here.",
        "Adjust `crosswalk.py` if any mapping does not match your intent, then re-run.",
        "",
        table,
        "",
        "Full mapping rationale is in the `notes` field of each `CrosswalkEntry` in `crosswalk.py`.",
        "",
    ])


def _section_seniority_profiles(profiles: dict[str, SeniorityProfile]) -> str:
    lines = [
        "## O*NET Seniority Profiles",
        "",
        "Seniority differentiation: O*NET does not have Junior / Mid / Senior entries.",
        "The ATF (Automatable Task Fraction) is computed from O*NET importance-weighted tasks,",
        "then blended with a task-category weight model (60% O*NET / 40% seniority model).",
        "",
        "### Task-category weights by seniority level",
        "",
    ]

    # Seniority weight table
    headers = ["Category", "AI Automatable", "Junior Weight", "Mid Weight", "Senior Weight"]
    rows = []
    for cat, auto_frac in TASK_AI_AUTOMATABLE_FRACTION.items():
        rows.append([
            cat.capitalize(),
            f"{auto_frac:.0%}",
            f"{SENIORITY_TASK_WEIGHTS['Junior'][cat]:.0%}",
            f"{SENIORITY_TASK_WEIGHTS['Mid'][cat]:.0%}",
            f"{SENIORITY_TASK_WEIGHTS['Senior'][cat]:.0%}",
        ])
    lines.append(_md_table(headers, rows))
    lines.append("")
    lines.append("**Adjust these in `config.py → SENIORITY_TASK_WEIGHTS` and `TASK_AI_AUTOMATABLE_FRACTION`.**")
    lines.append("")

    # Per-SOC ATF table
    lines += ["### ATF by SOC code and seniority level", ""]
    soc_headers = ["SOC Code", "Task Count", "Base ATF (Mid)", "Junior ATF", "Senior ATF"]
    soc_rows = []
    for soc, profile in sorted(profiles.items()):
        soc_rows.append([
            soc,
            str(profile.onet_task_count),
            f"{profile.base_atf:.3f}",
            f"{profile.atf_by_seniority.get('Junior', 0):.3f}",
            f"{profile.atf_by_seniority.get('Senior', 0):.3f}",
        ])
    if soc_rows:
        lines.append(_md_table(soc_headers, soc_rows))
    else:
        lines.append("*No O*NET profiles loaded — ATF defaulted to 0.50 for all occupations.*")
    lines.append("")

    return "\n".join(lines)


def _section_validation(results: list[ValidationResult]) -> str:
    lines = [
        "## Validation Results",
        "",
        "Hard threshold — expert score must fall **within** both ranges. Outside = FLAGGED.",
        "BLS and BEA ranges are kept separate. Disagreement between them is visible here.",
        "",
    ]

    headers = [
        "Role", "Level", "Expert", "BLS Range", "BLS", "BEA Range", "BEA", "Status"
    ]
    rows = []
    for r in results:
        expert_str = f"{r.expert_score:.2f}" if r.expert_score is not None else "—"
        bls_str    = f"[{r.bls_low:.2f}, {r.bls_high:.2f}]"
        bea_str    = f"[{r.bea_low:.2f}, {r.bea_high:.2f}]"

        bls_mark = (
            BLANK_MARK if r.within_bls is None
            else PASS_MARK if r.within_bls else FLAG_MARK
        )
        bea_mark = (
            BLANK_MARK if r.within_bea is None
            else PASS_MARK if r.within_bea else FLAG_MARK
        )

        status_cell = r.status
        if r.status == "FLAGGED":
            status_cell = f"**FLAGGED**"
        elif r.status == "CONSISTENT":
            status_cell = "CONSISTENT"
        else:
            status_cell = "_no score_"

        rows.append([
            r.role, r.seniority, expert_str,
            bls_str, bls_mark,
            bea_str, bea_mark,
            status_cell,
        ])

    lines.append(_md_table(headers, rows))
    lines.append("")
    return "\n".join(lines)


def _section_flags(results: list[ValidationResult]) -> str:
    flagged = [r for r in results if r.status == "FLAGGED"]
    lines = ["## Flags", ""]

    if not flagged:
        lines.append("No flags. All scored pairs are within both derived ranges.")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"{len(flagged)} pair(s) flagged:")
    lines.append("")
    for r in flagged:
        lines.append(f"### {r.role} | {r.seniority}")
        lines.append(f"- Expert score: **{r.expert_score:.2f}**")
        lines.append(f"- BLS range: [{r.bls_low:.2f}, {r.bls_high:.2f}] → {'PASS' if r.within_bls else 'FAIL'}")
        lines.append(f"- BEA range: [{r.bea_low:.2f}, {r.bea_high:.2f}] → {'PASS' if r.within_bea else 'FAIL'}")
        lines.append(f"- **Reason: {r.flag_reason}**")
        if r.bls_notes:
            lines.append(f"- BLS notes: {'; '.join(r.bls_notes)}")
        if r.bea_notes:
            lines.append(f"- BEA notes: {'; '.join(r.bea_notes)}")
        lines.append("")

    return "\n".join(lines)


def _section_methodology() -> str:
    return "\n".join([
        "## Methodology Notes",
        "",
        "### BLS method",
        f"O*NET task importance ratings (scale IM, 1–5) per SOC code are keyword-classified into",
        "four categories: implementation, design, communication, leadership.",
        "Each category has an AI-automatable fraction (see table above).",
        "The Automatable Task Fraction (ATF) is the importance-weighted average automatable fraction.",
        "Seniority adjustment blends O*NET ATF (60%) with a task-weight model (40%).",
        "Wage adjustment boosts disruption for lower-wage occupations (more price-elastic labor).",
        f"The BLS range is ATF × 10 × wage_factor ± {BLS_UNCERTAINTY_HW} RDF points,",
        "representing methodological uncertainty in keyword-based task classification.",
        "",
        "### BEA method",
        "Labor productivity (value added per worker) for the target NAICS code is divided",
        "by the national median. Higher relative productivity → higher strategic value → lower disruption.",
        "BEA disruption point = ATF × 10 / relative_productivity.",
        "The BEA range is derived from the min/max of this score over a rolling multi-year window.",
        "If BEA Section 6 is unavailable, BLS QCEW average annual pay is used as a proxy (labeled).",
        "If neither is available, a static relative productivity estimate from published BEA releases",
        "is used (labeled explicitly in the BEA notes column).",
        "",
        "### Validation rule",
        "```",
        "within_bls = bls_low <= expert_score <= bls_high",
        "within_bea = bea_low <= expert_score <= bea_high",
        "CONSISTENT if within_bls AND within_bea",
        "FLAGGED    otherwise",
        "```",
        "No tolerance band. No averaging of BLS and BEA. If they disagree, both facts appear.",
        "",
    ])


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_reports(
    results: list[ValidationResult],
    profiles: dict[str, SeniorityProfile],
    download_results: dict,
    bls_ranges: dict,
    bea_ranges: dict,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Markdown ---
    md = "\n".join([
        _section_metadata(download_results),
        _section_crosswalk(),
        _section_seniority_profiles(profiles),
        _section_validation(results),
        _section_flags(results),
        _section_methodology(),
    ])

    md_path = OUTPUT_DIR / "report.md"
    md_path.write_text(md, encoding="utf-8")
    log.info("[REPORT] Written: %s", md_path)

    # --- CSV ---
    rows = []
    for r in results:
        bls = bls_ranges.get((r.role, r.seniority))
        bea = bea_ranges.get((r.role, r.seniority))
        rows.append({
            "role":             r.role,
            "seniority":        r.seniority,
            "expert_rdf_score": r.expert_score,
            "bls_low":          r.bls_low,
            "bls_high":         r.bls_high,
            "bea_low":          r.bea_low,
            "bea_high":         r.bea_high,
            "within_bls":       r.within_bls,
            "within_bea":       r.within_bea,
            "status":           r.status,
            "flag_reason":      r.flag_reason,
            "bls_atf":          bls.atf if bls else None,
            "bls_wage_factor":  bls.wage_factor if bls else None,
            "bea_naics":        bea.naics_code if bea else None,
            "bea_data_source":  bea.data_source if bea else None,
            "bea_rel_prod":     bea.relative_productivity if bea else None,
        })
    csv_path = OUTPUT_DIR / "results.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    log.info("[REPORT] Written: %s", csv_path)

    # --- JSON ---
    json_path = OUTPUT_DIR / "results.json"
    json_path.write_text(json.dumps(rows, indent=2, default=str), encoding="utf-8")
    log.info("[REPORT] Written: %s", json_path)

    # Console summary
    n_consistent = sum(1 for r in results if r.status == "CONSISTENT")
    n_flagged    = sum(1 for r in results if r.status == "FLAGGED")
    n_no_score   = sum(1 for r in results if r.status == "NO_EXPERT_SCORE")
    print(f"\n{'='*60}")
    print(f"  RDF VALIDATION COMPLETE")
    print(f"  Consistent:     {n_consistent}")
    print(f"  Flagged:        {n_flagged}")
    print(f"  No score:       {n_no_score}")
    print(f"  Output:         {OUTPUT_DIR}")
    print(f"{'='*60}\n")
