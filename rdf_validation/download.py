"""
Download and cache all external data.

Rules:
- Download once per file; subsequent calls return the cached path.
- Pass refresh=True to force re-download.
- Never silently substitute data. Log every URL tried and every fallback taken.
- No API keys. Free bulk-download endpoints only.
"""

from __future__ import annotations

import io
import logging
import time
import zipfile
from pathlib import Path
from typing import Optional
import requests

from .config import (
    CACHE_DIR,
    BLS_OEWS_CURRENT_URLS,
    BLS_OEWS_HISTORICAL_URLS,
    BEA_SECTION6_URLS,
    BLS_QCEW_URL,
    ONET_URLS,
)

log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; rdf-validation-tool/1.0; "
        "academic research use; no-auth)"
    )
}
TIMEOUT = 60  # seconds per request


def _cache_path(filename: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / filename


def _download_url(url: str, dest: Path) -> bool:
    """Attempt to download url to dest. Returns True on success."""
    try:
        log.info("  GET %s", url)
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        resp.raise_for_status()
        content = resp.content
        # Reject HTML responses masquerading as data files
        if content[:100].lstrip().startswith(b"<!DOCTYPE") or content[:100].lstrip().startswith(b"<html"):
            log.warning("  → rejected: server returned HTML instead of data file (redirect/login page)")
            return False
        dest.write_bytes(content)
        log.info("  → saved %d bytes to %s", len(content), dest.name)
        return True
    except Exception as exc:
        log.warning("  → failed: %s", exc)
        return False


def _try_urls(urls: list[str], dest: Path, refresh: bool) -> Optional[Path]:
    """Try each URL in order. Return dest path on first success, None if all fail."""
    if dest.exists() and not refresh:
        log.info("[CACHED] %s", dest.name)
        return dest
    for url in urls:
        if _download_url(url, dest):
            return dest
        time.sleep(1)
    log.error("[DOWNLOAD FAILED] All URLs failed for %s. Tried: %s", dest.name, urls)
    return None


# ---------------------------------------------------------------------------
# Public download functions
# ---------------------------------------------------------------------------

def bls_oews_current(refresh: bool = False) -> Optional[Path]:
    """BLS OEWS national estimates — current year (occupation wages)."""
    dest = _cache_path("bls_oews_current.xlsx")
    return _try_urls(BLS_OEWS_CURRENT_URLS, dest, refresh)


def bls_oews_historical(refresh: bool = False) -> Optional[Path]:
    """BLS OEWS national estimates — 1997 (earliest available; closest to 1993 target).

    The 1997 file is distributed as a ZIP containing one or more Excel/text files.
    We cache the ZIP, then extract the first xlsx/xls/txt file found inside it.
    """
    zip_dest = _cache_path("bls_oews_1997.zip")
    extracted_dest = _cache_path("bls_oews_1997_national.xlsx")

    if extracted_dest.exists() and not refresh:
        log.info("[CACHED] %s", extracted_dest.name)
        return extracted_dest

    path = _try_urls(BLS_OEWS_HISTORICAL_URLS, zip_dest, refresh)
    if path is None:
        return None

    try:
        with zipfile.ZipFile(zip_dest) as zf:
            for name in zf.namelist():
                if name.lower().endswith((".xlsx", ".xls")):
                    data = zf.read(name)
                    extracted_dest.write_bytes(data)
                    log.info("[EXTRACTED] %s from zip → %s", name, extracted_dest.name)
                    return extracted_dest
            # Fall back to any file with 'nat' in the name
            for name in zf.namelist():
                if "nat" in name.lower():
                    data = zf.read(name)
                    extracted_dest = _cache_path(f"bls_oews_1997_{Path(name).name}")
                    extracted_dest.write_bytes(data)
                    log.info("[EXTRACTED] %s from zip → %s", name, extracted_dest.name)
                    return extracted_dest
    except Exception as exc:
        log.error("[EXTRACT FAILED] %s: %s", zip_dest.name, exc)

    log.error("[DOWNLOAD FAILED] Could not extract national file from 1997 OEWS zip.")
    return None


def bea_section6(refresh: bool = False) -> Optional[Path]:
    """BEA NIPA Section 6 — income and employment by industry.

    Returns path to the Excel file, or None if all BEA URLs fail.
    Caller is responsible for falling back to QCEW.
    """
    dest = _cache_path("bea_section6.xlsx")
    return _try_urls(BEA_SECTION6_URLS, dest, refresh)


def bls_qcew(refresh: bool = False) -> Optional[Path]:
    """BLS QCEW annual by industry (2023) — used as BEA fallback.

    Returns the directory containing the extracted CSVs, or None on failure.
    """
    zip_dest = _cache_path("bls_qcew_2023.zip")
    extract_dir = CACHE_DIR / "qcew_2023"

    if extract_dir.exists() and any(extract_dir.iterdir()) and not refresh:
        log.info("[CACHED] QCEW extract dir %s", extract_dir)
        return extract_dir

    path = _try_urls([BLS_QCEW_URL], zip_dest, refresh)
    if path is None:
        return None

    extract_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(zip_dest) as zf:
            zf.extractall(extract_dir)
        log.info("[EXTRACTED] QCEW zip → %s (%d files)", extract_dir, len(list(extract_dir.rglob("*"))))
        return extract_dir
    except Exception as exc:
        log.error("[EXTRACT FAILED] QCEW zip: %s", exc)
        return None


def onet_file(key: str, refresh: bool = False) -> Optional[Path]:
    """Download one O*NET data file by key (see config.ONET_URLS).

    Keys: task_statements, task_ratings, skills, work_experience
    """
    url = ONET_URLS.get(key)
    if not url:
        raise ValueError(f"Unknown O*NET file key: {key!r}. Valid: {list(ONET_URLS)}")
    dest = _cache_path(f"onet_{key}.txt")
    return _try_urls([url], dest, refresh)


def download_all(refresh: bool = False) -> dict[str, Optional[Path]]:
    """Download every data source. Returns a dict of name → path (None = failed)."""
    log.info("=== Downloading data sources ===")
    results = {}
    results["bls_oews_current"]    = bls_oews_current(refresh)
    results["bls_oews_historical"] = bls_oews_historical(refresh)
    results["bea_section6"]        = bea_section6(refresh)
    results["bls_qcew"]            = bls_qcew(refresh)
    for key in ONET_URLS:
        results[f"onet_{key}"]     = onet_file(key, refresh)

    failed = [k for k, v in results.items() if v is None]
    if failed:
        log.warning("[DOWNLOAD SUMMARY] %d source(s) failed: %s", len(failed), failed)
    else:
        log.info("[DOWNLOAD SUMMARY] All sources cached successfully.")
    return results
