"""
O*NET-based seniority differentiation.

Steps:
1. Load task statements + importance ratings for each SOC code.
2. Classify each task into one of four categories via keyword matching.
3. Compute a base ATF (Automatable Task Fraction) from the O*NET importance-weighted
   task profile — this represents the "average" worker in that occupation.
4. Apply seniority task-weight blending to get a seniority-adjusted ATF.
5. Return a SeniorityProfile per SOC code, used by bls_method.py.

The category weights and automatable fractions come from config.py so the user
can adjust them without touching this file.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import (
    SENIORITY_LEVELS,
    SENIORITY_TASK_WEIGHTS,
    TASK_AI_AUTOMATABLE_FRACTION,
    ONET_COL_ALIASES,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task classification keywords
# Order matters: leadership checked before communication before design before
# implementation, so "manage the implementation of" → leadership, not implementation.
# ---------------------------------------------------------------------------

TASK_KEYWORDS: dict[str, list[str]] = {
    "leadership": [
        "lead ", "leads ", "leading ", "manage ", "manages ", "managing ",
        "supervise", "oversee", "direct ", "directs ", "mentor", "coach",
        "hire ", "recruit", "evaluate performance", "set goals", "set priorities",
        "strategy", "strategize", "prioritize", "allocate resources", "delegate",
        "budget", "headcount", "performance review",
    ],
    "communication": [
        "communicate", "present ", "explanation", "explain ",
        "document ", "write report", "write documentation", "prepare report",
        "meet with", "discuss ", "coordinate with", "collaborate",
        "consult ", "negotiate", "liaise", "liaison", "train ",
        "educate ", "demonstrate to", "report to", "brief ",
        "facilitate", "stakeholder",
    ],
    "design": [
        "design ", "architect", "plan ", "specify", "define requirements",
        "model ", "prototype", "blueprint", "evaluate options", "assess ",
        "research ", "analyze ", "analyse ", "select technology", "choose ",
        "recommend ", "propose ", "review architecture", "system design",
        "requirements gathering", "feasibility",
    ],
    "implementation": [
        "write ", "writes ", "written ", "code ", "codes ", "coding ",
        "program ", "programs ", "programming ", "develop ", "build ",
        "implement", "create ", "construct", "test ", "debug", "fix ",
        "deploy", "install", "configure ", "execute ", "run ", "update ",
        "modify ", "refactor", "optimize", "compile", "maintain",
        "troubleshoot", "monitor ", "integrate", "automate",
    ],
}


def classify_task(task_text: str) -> str:
    """Return the category of a task statement based on keyword matching."""
    t = task_text.lower()
    for category in ("leadership", "communication", "design", "implementation"):
        if any(kw in t for kw in TASK_KEYWORDS[category]):
            return category
    return "implementation"  # default: uncategorized tasks are implementation-flavored


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _normalize_cols(df: pd.DataFrame, aliases: dict) -> pd.DataFrame:
    renamed = {k: v for k, v in aliases.items() if k in df.columns}
    if renamed:
        log.debug("Renaming columns: %s", renamed)
    return df.rename(columns=renamed)


def load_task_statements(path: Path) -> pd.DataFrame:
    """Load O*NET Task Statements.txt → DataFrame with columns:
    [soc_code, task_id, task, task_type]
    """
    df = pd.read_csv(path, sep="\t", encoding="utf-8-sig", low_memory=False)
    log.info("[O*NET Task Statements] Columns: %s", list(df.columns))
    df = _normalize_cols(df, ONET_COL_ALIASES)

    # Normalize SOC code: strip O*NET suffix (.00 / .01 etc.) → 7-char "XX-XXXX"
    soc_col = "O*NET-SOC Code"
    if soc_col in df.columns:
        df["soc_code"] = df[soc_col].str[:7]
    else:
        raise KeyError(f"Expected column '{soc_col}' not found. Got: {list(df.columns)}")

    task_col = next((c for c in df.columns if "task" in c.lower() and "id" not in c.lower()
                     and "type" not in c.lower() and "incumbent" not in c.lower()), None)
    if task_col is None:
        raise KeyError(f"Could not find task text column. Got: {list(df.columns)}")

    df = df.rename(columns={task_col: "task"})
    df["task_id"] = df.get("Task ID", range(len(df)))
    df["task_type"] = df.get("Task Type", "Core")
    return df[["soc_code", "task_id", "task", "task_type"]].copy()


def load_task_ratings(path: Path) -> pd.DataFrame:
    """Load O*NET Task Ratings.txt → DataFrame with columns:
    [soc_code, task_id, scale_id, data_value]

    We keep only Importance ratings (Scale ID = 'IM').
    """
    df = pd.read_csv(path, sep="\t", encoding="utf-8-sig", low_memory=False)
    log.info("[O*NET Task Ratings] Columns: %s", list(df.columns))
    df = _normalize_cols(df, ONET_COL_ALIASES)

    soc_col = "O*NET-SOC Code"
    df["soc_code"] = df[soc_col].str[:7]

    # Locate scale ID column
    scale_col = next((c for c in df.columns if "scale" in c.lower()), None)
    if scale_col is None:
        raise KeyError(f"Could not find Scale ID column. Got: {list(df.columns)}")
    df = df.rename(columns={scale_col: "scale_id"})

    # Task ID column
    task_id_col = next((c for c in df.columns if "task" in c.lower() and "id" in c.lower()), None)
    if task_id_col:
        df = df.rename(columns={task_id_col: "task_id"})
    else:
        df["task_id"] = None

    # Data value column
    val_col = next((c for c in df.columns if "data" in c.lower() and "value" in c.lower()), None)
    if val_col is None:
        raise KeyError(f"Could not find Data Value column. Got: {list(df.columns)}")
    df = df.rename(columns={val_col: "data_value"})

    df = df[df["scale_id"] == "IM"].copy()
    df["data_value"] = pd.to_numeric(df["data_value"], errors="coerce")
    return df[["soc_code", "task_id", "data_value"]].dropna(subset=["data_value"])


# ---------------------------------------------------------------------------
# ATF computation
# ---------------------------------------------------------------------------

@dataclass
class SeniorityProfile:
    soc_code: str
    onet_task_count: int
    base_atf: float                       # O*NET baseline, ~mid-level
    atf_by_seniority: dict[str, float]    # seniority → adjusted ATF
    top_tasks_by_category: dict[str, list[str]] = field(default_factory=dict)


def _compute_base_atf(tasks_df: pd.DataFrame, ratings_df: pd.DataFrame, soc: str) -> tuple[float, dict, list]:
    """Compute ATF for one SOC code from O*NET data.

    Returns (base_atf, category_importance_totals, task_sample_list).
    """
    t = tasks_df[tasks_df["soc_code"] == soc].copy()
    r = ratings_df[ratings_df["soc_code"] == soc].copy()

    if t.empty:
        log.warning("[O*NET] No task statements for SOC %s — using default ATF 0.50", soc)
        return 0.50, {}, []

    # Classify tasks
    t["category"] = t["task"].apply(classify_task)

    # Join with importance ratings
    if not r.empty and "task_id" in r.columns and t["task_id"].notna().any():
        merged = t.merge(r[["task_id", "data_value"]], on="task_id", how="left")
        merged["importance"] = merged["data_value"].fillna(3.0)  # default: "Important"
    else:
        merged = t.copy()
        merged["importance"] = 3.0  # uniform weighting if ratings unavailable

    # Per-category total importance
    cat_totals = merged.groupby("category")["importance"].sum().to_dict()
    total_importance = merged["importance"].sum()

    if total_importance == 0:
        return 0.50, cat_totals, []

    # ATF = sum over all tasks of (importance × category_automatable_fraction) / total
    merged["automatable_contrib"] = merged.apply(
        lambda row: row["importance"] * TASK_AI_AUTOMATABLE_FRACTION.get(row["category"], 0.5),
        axis=1,
    )
    base_atf = merged["automatable_contrib"].sum() / total_importance

    # Sample top task per category for report display
    top_tasks: dict[str, list[str]] = {}
    for cat in TASK_AI_AUTOMATABLE_FRACTION:
        cat_tasks = merged[merged["category"] == cat].nlargest(3, "importance")["task"].tolist()
        if cat_tasks:
            top_tasks[cat] = cat_tasks

    task_sample = merged.nlargest(5, "importance")[["task", "category", "importance"]].to_dict("records")
    return float(base_atf), cat_totals, task_sample


def compute_profiles(
    statements_path: Path,
    ratings_path: Path,
    soc_codes: list[str],
) -> dict[str, SeniorityProfile]:
    """Build a SeniorityProfile for each SOC code."""
    statements = load_task_statements(statements_path)
    ratings    = load_task_ratings(ratings_path)

    profiles: dict[str, SeniorityProfile] = {}

    for soc in soc_codes:
        base_atf, cat_totals, task_sample = _compute_base_atf(statements, ratings, soc)

        # Seniority-adjusted ATF:
        # Blend the O*NET base ATF (mid-level ground truth) with the
        # seniority task-weight model.
        atf_by_seniority: dict[str, float] = {}
        for level in SENIORITY_LEVELS:
            weights = SENIORITY_TASK_WEIGHTS[level]
            seniority_atf = sum(
                weights[cat] * TASK_AI_AUTOMATABLE_FRACTION[cat]
                for cat in weights
            )
            # 60% weight on O*NET empirical profile, 40% on seniority model
            blended = 0.60 * base_atf + 0.40 * seniority_atf
            atf_by_seniority[level] = round(blended, 4)

        task_count = len(statements[statements["soc_code"] == soc])
        profiles[soc] = SeniorityProfile(
            soc_code=soc,
            onet_task_count=task_count,
            base_atf=round(base_atf, 4),
            atf_by_seniority=atf_by_seniority,
            top_tasks_by_category={},
        )

        log.info(
            "[O*NET] SOC %s | tasks=%d | base_atf=%.3f | Junior=%.3f Mid=%.3f Senior=%.3f",
            soc, task_count, base_atf,
            atf_by_seniority["Junior"], atf_by_seniority["Mid"], atf_by_seniority["Senior"],
        )

    return profiles
