"""
All methodology parameters live here.
Change a number here → it propagates to every method automatically.
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
OUTPUT_DIR = BASE_DIR / "output"
EXPERT_SCORES_FILE = BASE_DIR / "expert_scores.csv"

RDF_MIN = 0.0
RDF_MAX = 10.0

# O*NET database version — update when onetcenter.org releases a new db
ONET_VERSION = "29_0"

# Internet-era target year and limitation note
INTERNET_TARGET_YEAR = 1993
INTERNET_EARLIEST_OEWS = 1997
INTERNET_NOTE = (
    f"Requested historical year {INTERNET_TARGET_YEAR} predates BLS OEWS availability. "
    f"Earliest available OEWS year ({INTERNET_EARLIEST_OEWS}) used as closest substitute. "
    "This is the first year of the modern OEWS program and captures the early commercial "
    "internet era, though it post-dates the precise target year by four years."
)

# BLS method: half-width of the uncertainty band around the ATF-derived point estimate.
# Represents methodological uncertainty in keyword-based task classification.
BLS_UNCERTAINTY_HW = 1.5  # RDF points

# BEA method: rolling window (years) for computing the range via year-to-year variance
BEA_ROLLING_YEARS = 5

# Wage adjustment strength: how much lower wages boost the disruption score.
# 0.0 = wages have no effect. 0.20 = a role at the bottom of the wage distribution
# gets a 20% disruption boost relative to a role at the top.
WAGE_ADJUSTMENT_STRENGTH = 0.20

# Task category → estimated fraction automatable by current-generation AI coding tools.
# Derived from task analysis literature and adjusted for software-domain specificity.
TASK_AI_AUTOMATABLE_FRACTION = {
    "implementation": 0.78,  # code generation, unit tests, linting, formatting
    "design":         0.22,  # architectural decisions, trade-off evaluation
    "communication":  0.12,  # stakeholder coordination, mentoring, docs requiring judgment
    "leadership":     0.08,  # strategy, hiring, prioritization across competing interests
}

# Seniority-level task-category weights.
# These represent the approximate fraction of a role's working time spent in each
# category at each experience band, derived from O*NET Work Experience Requirements
# and task-importance distributions across job levels.
# Show these in the report so the user can validate.
SENIORITY_TASK_WEIGHTS = {
    "Junior": {
        "implementation": 0.65,
        "design":         0.20,
        "communication":  0.10,
        "leadership":     0.05,
    },
    "Mid": {
        "implementation": 0.45,
        "design":         0.30,
        "communication":  0.15,
        "leadership":     0.10,
    },
    "Senior": {
        "implementation": 0.20,
        "design":         0.40,
        "communication":  0.20,
        "leadership":     0.20,
    },
}

SENIORITY_LEVELS = ["Junior", "Mid", "Senior"]

# --- Download URLs ---
# Multiple patterns tried in order; first success wins.

BLS_OEWS_CURRENT_URLS = [
    "https://www.bls.gov/oes/current/oes_nat.xlsx",
    "https://www.bls.gov/oes/special.requests/oes_research_estimates.xlsx",
]

BLS_OEWS_HISTORICAL_URLS = [
    "https://www.bls.gov/oes/special.requests/oesm97nat.zip",
    "https://www.bls.gov/oes/1997/oes_nat.zip",
]

BEA_SECTION6_URLS = [
    "https://apps.bea.gov/national/Release/XLS/Section6All_xls.xlsx",
    "https://www.bea.gov/national/Release/XLS/Section6All_xls.xlsx",
]

# QCEW used as BEA fallback (industry-level wages, independent from OEWS)
BLS_QCEW_URL = "https://www.bls.gov/cew/data/files/2023/csv/2023_annual_by_industry.zip"

_onet_base = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION}_text"
ONET_URLS = {
    "task_statements": f"{_onet_base}/Task%20Statements.txt",
    "task_ratings":    f"{_onet_base}/Task%20Ratings.txt",
    "skills":          f"{_onet_base}/Skills.txt",
    "work_experience": f"{_onet_base}/Work%20Experience%20Requirements.txt",
}

# --- Column name aliases ---
# Map historical / variant column names to the canonical name expected by each module.

BLS_COL_ALIASES = {
    "MEDIAN":     "H_MEDIAN",
    "HRLY_WAGE":  "H_MEAN",
    "A_MEDIAN_2": "A_MEDIAN",
}

ONET_COL_ALIASES = {
    "Scale Name": "Scale ID",
    "Element Name": "Element ID",
    "O*NET-SOC Code": "O*NET-SOC Code",  # identity — kept for explicitness
}

# BEA sheet names to try (BEA renames sheets between annual releases)
BEA_SHEET_NAMES = [
    "T60500A-D",   # Table 6.5: FTE employees by industry (older format)
    "T60500",
    "Table 6.5A",
    "6.5A",
    "6.5D",
    "T60100A-D",   # Table 6.1: National income by industry
    "T60100",
]

# NAICS codes of interest for BEA extraction
BEA_NAICS_TARGETS = {
    "5415": "Computer Systems Design and Related Services",
    "5112": "Software Publishers",
    "51":   "Information",        # broad fallback if 5415 not present
}

# SOC codes covered by the crosswalk — used to filter O*NET and OEWS data
SOC_CODES = [
    "15-1251",  # Computer Programmers
    "15-1252",  # Software Developers
    "15-1253",  # Software Quality Assurance Analysts and Testers
    "15-1254",  # Web Developers
    "15-1242",  # Database Administrators and Architects
    "15-1244",  # Network and Computer Systems Administrators
    "15-1299",  # Computer Occupations, All Other
    "15-2051",  # Data Scientists
]
