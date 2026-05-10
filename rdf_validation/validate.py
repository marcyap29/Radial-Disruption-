"""
Validation: compare expert scores against BLS and BEA ranges.

Rule (hard threshold — no tolerance band):
  within_bls = bls_low <= expert_score <= bls_high
  within_bea = bea_low <= expert_score <= bea_high

  CONSISTENT     if within_bls AND within_bea
  FLAGGED        otherwise — with specific reason
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import EXPERT_SCORES_FILE, SENIORITY_LEVELS, RDF_MIN, RDF_MAX
from .crosswalk import all_roles
from .bls_method import BLSRange
from .bea_method import BEARange

log = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    role: str
    seniority: str
    expert_score: Optional[float]

    bls_low: float
    bls_high: float
    bea_low: float
    bea_high: float

    within_bls: Optional[bool]
    within_bea: Optional[bool]

    status: str           # CONSISTENT | FLAGGED | NO_EXPERT_SCORE
    flag_reason: str      # empty string if CONSISTENT or NO_EXPERT_SCORE

    bls_notes: list[str] = field(default_factory=list)
    bea_notes: list[str] = field(default_factory=list)


def load_expert_scores(path: Path = EXPERT_SCORES_FILE) -> dict[tuple[str, str], float]:
    """Load expert_scores.csv → {(role, seniority): score}."""
    if not path.exists():
        log.warning("[VALIDATE] expert_scores.csv not found at %s", path)
        return {}

    try:
        df = pd.read_csv(path, encoding="utf-8-sig", skipinitialspace=True)
        df.columns = [c.strip() for c in df.columns]
        required = {"role", "seniority", "expert_rdf_score"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns in expert_scores.csv: {missing}")

        scores = {}
        for _, row in df.iterrows():
            role      = str(row["role"]).strip()
            seniority = str(row["seniority"]).strip()
            raw       = str(row["expert_rdf_score"]).strip()

            if raw.lower() in ("", "nan", "none", "n/a", "tbd"):
                log.info("[VALIDATE] No score for (%s, %s) — will report as NO_EXPERT_SCORE", role, seniority)
                continue

            try:
                score = float(raw)
            except ValueError:
                log.warning("[VALIDATE] Invalid score %r for (%s, %s) — skipping", raw, role, seniority)
                continue

            if not (RDF_MIN <= score <= RDF_MAX):
                log.warning("[VALIDATE] Score %.2f for (%s, %s) is outside [%.0f, %.0f] — clamping",
                            score, role, seniority, RDF_MIN, RDF_MAX)
                score = max(RDF_MIN, min(RDF_MAX, score))

            scores[(role, seniority)] = score

        log.info("[VALIDATE] Loaded %d expert scores", len(scores))
        return scores

    except Exception as exc:
        log.error("[VALIDATE] Failed to load expert_scores.csv: %s", exc)
        return {}


def run_validation(
    bls_ranges: dict[tuple[str, str], BLSRange],
    bea_ranges: dict[tuple[str, str], BEARange],
    expert_scores: dict[tuple[str, str], float],
) -> list[ValidationResult]:
    """Validate all (role, seniority) pairs. Returns one result per pair."""
    results = []
    roles = all_roles()

    for role in roles:
        for seniority in SENIORITY_LEVELS:
            key = (role, seniority)

            bls = bls_ranges.get(key)
            bea = bea_ranges.get(key)
            expert = expert_scores.get(key)

            if bls is None or bea is None:
                log.warning("[VALIDATE] Missing method range for %s | %s — skipping", role, seniority)
                continue

            if expert is None:
                results.append(ValidationResult(
                    role=role, seniority=seniority, expert_score=None,
                    bls_low=bls.low, bls_high=bls.high,
                    bea_low=bea.low, bea_high=bea.high,
                    within_bls=None, within_bea=None,
                    status="NO_EXPERT_SCORE",
                    flag_reason="No expert score provided in expert_scores.csv",
                    bls_notes=bls.notes, bea_notes=bea.notes,
                ))
                continue

            within_bls = bls.low <= expert <= bls.high
            within_bea = bea.low <= expert <= bea.high

            if within_bls and within_bea:
                status = "CONSISTENT"
                flag_reason = ""
            else:
                status = "FLAGGED"
                parts = []
                if not within_bls:
                    if expert < bls.low:
                        parts.append(f"expert {expert:.2f} is BELOW BLS lower bound {bls.low:.2f}")
                    else:
                        parts.append(f"expert {expert:.2f} is ABOVE BLS upper bound {bls.high:.2f}")
                if not within_bea:
                    if expert < bea.low:
                        parts.append(f"expert {expert:.2f} is BELOW BEA lower bound {bea.low:.2f}")
                    else:
                        parts.append(f"expert {expert:.2f} is ABOVE BEA upper bound {bea.high:.2f}")
                flag_reason = "; ".join(parts)

            results.append(ValidationResult(
                role=role, seniority=seniority, expert_score=expert,
                bls_low=bls.low, bls_high=bls.high,
                bea_low=bea.low, bea_high=bea.high,
                within_bls=within_bls, within_bea=within_bea,
                status=status, flag_reason=flag_reason,
                bls_notes=bls.notes, bea_notes=bea.notes,
            ))

            log.info(
                "[VALIDATE] %s | %s | expert=%.2f BLS=[%.2f,%.2f] BEA=[%.2f,%.2f] → %s",
                role, seniority, expert,
                bls.low, bls.high, bea.low, bea.high, status,
            )

    return results
