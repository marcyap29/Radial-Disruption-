"""
Central configuration: case definitions, expert scores, NAICS/SOC mappings.
"""

# ---------------------------------------------------------------------------
# Case definitions
# Each disruption has:
#   disrupting_naics: the technology sector doing the disrupting
#   bls_year:         OEWS data year to use
#   bea_year:         BEA IO table year to use
#   pairs:            list of adjacent-industry dicts
# ---------------------------------------------------------------------------

CASES = {
    "smartphone_2007": {
        "label": "Smartphone (2007)",
        "disrupting_naics": "334",
        "bls_year": 2007,
        "bea_year": 2007,
        "pairs": [
            {"label": "GPS devices",          "naics": "334",  "expert_fij": 0.72,
             "bea_code": "334",  "note": "GPS hardware subset of NAICS 334 — same sector"},
            {"label": "Digital cameras",      "naics": "333",  "expert_fij": 0.68,
             "bea_code": "333"},
            {"label": "Feature phones",       "naics": "334",  "expert_fij": 0.88,
             "bea_code": "334",  "note": "same sector, high overlap expected"},
            {"label": "Semiconductor design", "naics": "3344", "expert_fij": 0.82,
             "bea_code": "3344"},
            {"label": "Mobile gaming",        "naics": "7132", "expert_fij": 0.65,
             "bea_code": "7132"},
            {"label": "App developers",       "naics": "5112", "expert_fij": 0.75,
             "bea_code": "5112"},
        ],
    },

    "internet_1993": {
        "label": "Internet (1993)",
        "disrupting_naics": "517",
        "bls_year": 2000,   # earliest reliable OEWS; 1997 OEWS very sparse
        "bea_year": 1997,
        "pairs": [
            {"label": "Travel agencies",         "naics": "5615", "expert_fij": 0.72,
             "bea_code": "5615"},
            {"label": "Classified advertising",  "naics": "511",  "expert_fij": 0.65,
             "bea_code": "511"},
            {"label": "Encyclopedia publishing", "naics": "5111", "expert_fij": 0.78,
             "bea_code": "5111"},
            {"label": "Video rental",            "naics": "5322", "expert_fij": 0.58,
             "bea_code": "5322",
             "bea_fallback_year": 2002},
            {"label": "Music retail",            "naics": "4512", "expert_fij": 0.55,
             "bea_code": "4512",
             "bea_fallback_year": 2002},
        ],
    },

    "ai_coding_2022": {
        "label": "AI Coding Tools (2022)",
        "disrupting_naics": "511210",
        "bls_year": 2022,
        "bea_year": 2021,
        # Adjacent industry is NAICS 541511 (custom software), split by SOC
        "adjacent_naics": "541511",
        "pairs": [
            {"label": "Junior engineers",  "soc": "15-1252", "expert_fij": 0.82},
            {"label": "Mid-level engineers","soc": "15-1251", "expert_fij": 0.68},
            {"label": "DevOps engineers",  "soc": "15-1244", "expert_fij": 0.72},
            {"label": "Senior engineers",  "soc": "15-1211", "expert_fij": 0.45},
            {"label": "QA engineers",      "soc": "15-1253", "expert_fij": 0.58},
        ],
    },
}

# ---------------------------------------------------------------------------
# BLS OEWS bulk download base URLs per year
# Format: https://www.bls.gov/oes/special.requests/oesm{YY}in4.zip
# (industry-specific national files)
# ---------------------------------------------------------------------------

BLS_BULK_URL_TEMPLATE = (
    "https://www.bls.gov/oes/special.requests/oesm{year_short}in4.zip"
)

BLS_NATIONAL_URL_TEMPLATE = (
    "https://www.bls.gov/oes/special.requests/oesm{year_short}nat.zip"
)

# ---------------------------------------------------------------------------
# BEA IO table URLs
# Use "Use" tables (what each industry buys) for supply-chain overlap.
# BEA provides Excel files; we use the summary-level (~73 industry) tables.
# ---------------------------------------------------------------------------

BEA_IO_URLS = {
    1997: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_1997_Detail.xlsx",
    2007: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_2007_Detail.xlsx",
    2021: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_2021_Detail.xlsx",
}

# Fallback summary (smaller, more stable) URLs
BEA_IO_SUMMARY_URLS = {
    1997: "https://www.bea.gov/industry/xls/io-annual/IOMake_Before_Redefinitions_1997_Summary.xlsx",
    2002: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_2002_Summary.xlsx",
    2007: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_2007_Summary.xlsx",
    2021: "https://www.bea.gov/industry/xls/io-annual/IOUse_Before_Redefinitions_PRO_2021_Summary.xlsx",
}

# Minimum employment fraction for an occupation to be considered "meaningful"
# in a given industry (used in OEWS overlap calculation).
OCC_SIGNIFICANCE_THRESHOLD = 0.005   # 0.5% of industry workforce

# IO overlap: minimum purchase share to consider a supplier "shared"
IO_SIGNIFICANCE_THRESHOLD = 0.01     # 1% of total inputs

# Range band half-width: derived point estimate ± BAND_HALF_WIDTH
BAND_HALF_WIDTH = 0.10

# Success threshold: fraction of expert scores that must fall within BOTH ranges
SUCCESS_THRESHOLD = 0.80
