"""
Industry-to-SOC-code crosswalk for AI coding roles.

Every row here is printed verbatim in report.md so the user can validate it
without reading Python. Change mappings here; they propagate automatically.

Structure per entry:
  role          — human-readable role name (matches expert_scores.csv)
  soc_primary   — (code, title, weight) — dominant occupation
  soc_secondary — (code, title, weight) or None — overlap occupation
  bea_naics     — NAICS code used to pull BEA productivity data
  bea_sector    — human-readable NAICS description
  notes         — rationale for the mapping choice
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class CrosswalkEntry:
    role: str
    soc_primary: Tuple[str, str, float]    # (code, title, weight)
    soc_secondary: Optional[Tuple[str, str, float]]
    bea_naics: str
    bea_sector: str
    notes: str

    @property
    def primary_code(self) -> str:
        return self.soc_primary[0]

    @property
    def secondary_code(self) -> Optional[str]:
        return self.soc_secondary[0] if self.soc_secondary else None

    @property
    def weighted_soc_codes(self) -> list[Tuple[str, float]]:
        codes = [(self.soc_primary[0], self.soc_primary[2])]
        if self.soc_secondary:
            codes.append((self.soc_secondary[0], self.soc_secondary[2]))
        return codes


CROSSWALK: list[CrosswalkEntry] = [
    CrosswalkEntry(
        role="Software Developer",
        soc_primary=("15-1252", "Software Developers", 1.00),
        soc_secondary=None,
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "Direct SOC match. '15-1252 Software Developers' is the canonical BLS code "
            "for this role as of the 2018 SOC revision. No secondary needed."
        ),
    ),
    CrosswalkEntry(
        role="Computer Programmer",
        soc_primary=("15-1251", "Computer Programmers", 1.00),
        soc_secondary=None,
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "Direct SOC match. Distinct from Software Developer in BLS classification — "
            "Programmers write code to spec; Developers design + write. Employment in "
            "15-1251 has been declining since ~2000 as the roles converge upward."
        ),
    ),
    CrosswalkEntry(
        role="Data Scientist / ML Engineer",
        soc_primary=("15-2051", "Data Scientists", 0.65),
        soc_secondary=("15-1299", "Computer Occupations, All Other", 0.35),
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "No dedicated 'ML Engineer' SOC code exists in the 2018 revision. "
            "15-2051 (Data Scientists) is the closest match for the modeling/research half. "
            "15-1299 (residual tech) covers the engineering/deployment half. "
            "Weights are approximate; adjust if your role definition is skewed one way."
        ),
    ),
    CrosswalkEntry(
        role="Web Developer",
        soc_primary=("15-1254", "Web Developers", 0.70),
        soc_secondary=("15-1255", "Web and Digital Interface Designers", 0.30),
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "15-1254 covers back-end + full-stack web roles. 15-1255 covers front-end "
            "UI/UX-heavy work. Weight split reflects that most 'Web Developer' job postings "
            "are code-first, not design-first, but UI skills are significant."
        ),
    ),
    CrosswalkEntry(
        role="DevOps / Site Reliability Engineer",
        soc_primary=("15-1244", "Network and Computer Systems Administrators", 0.55),
        soc_secondary=("15-1252", "Software Developers", 0.45),
        bea_naics="5182",
        bea_sector="Data Processing, Hosting, and Related Services",
        notes=(
            "No dedicated DevOps SOC code. Role spans infrastructure automation (closer to "
            "15-1244) and software engineering (closer to 15-1252). BEA NAICS 5182 used "
            "because DevOps labor is concentrated in cloud/hosting firms, not custom dev shops. "
            "Adjust secondary weight upward if the role you're scoring is SRE-heavy."
        ),
    ),
    CrosswalkEntry(
        role="Data Engineer",
        soc_primary=("15-1242", "Database Administrators and Architects", 0.55),
        soc_secondary=("15-2051", "Data Scientists", 0.45),
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "Data Engineering bridges DB administration (pipeline, storage, reliability) "
            "and data science programming (transforms, feature engineering). "
            "15-1242 and 15-2051 are the closest available codes; neither is a perfect match."
        ),
    ),
    CrosswalkEntry(
        role="QA / Test Engineer",
        soc_primary=("15-1253", "Software Quality Assurance Analysts and Testers", 1.00),
        soc_secondary=None,
        bea_naics="5415",
        bea_sector="Computer Systems Design and Related Services",
        notes=(
            "Direct SOC match. 15-1253 covers both manual QA and automated test engineering. "
            "High automatability expected because test execution and basic test-case generation "
            "are prime targets for AI coding tools — expect a high ATF here."
        ),
    ),
]


def as_table_rows() -> list[dict]:
    """Return crosswalk as a list of flat dicts for tabular display."""
    rows = []
    for e in CROSSWALK:
        rows.append({
            "Role": e.role,
            "Primary SOC": e.soc_primary[0],
            "Primary Title": e.soc_primary[1],
            "Primary Weight": f"{e.soc_primary[2]:.0%}",
            "Secondary SOC": e.soc_secondary[0] if e.soc_secondary else "—",
            "Secondary Title": e.soc_secondary[1] if e.soc_secondary else "—",
            "Secondary Weight": f"{e.soc_secondary[2]:.0%}" if e.soc_secondary else "—",
            "BEA NAICS": e.bea_naics,
            "BEA Sector": e.bea_sector,
            "Notes": e.notes,
        })
    return rows


def get_entry(role: str) -> CrosswalkEntry:
    for e in CROSSWALK:
        if e.role == role:
            return e
    raise KeyError(f"No crosswalk entry for role: {role!r}")


def all_roles() -> list[str]:
    return [e.role for e in CROSSWALK]
