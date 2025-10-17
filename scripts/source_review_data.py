#!/usr/bin/env python3
"""Shared helpers for the source verification utilities."""

from __future__ import annotations

import csv
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import psycopg
from psycopg.rows import dict_row

DEFAULT_OUTPUT = Path("docs/source_verification_log.csv")
STATUS_DESCRIPTIONS = {
    "ok": "Legitimate source",
    "paywall": "Paywalled",
    "cookie": "Cookie consent blocker",
    "modal": "Modal or other overlay",
    "non_news": "Not a news source",
}
CHOICE_TO_STATUS = {
    "o": "ok",
    "p": "paywall",
    "c": "cookie",
    "m": "modal",
    "n": "non_news",
    "s": "skip",
}
FIELDNAMES = [
    "source_id",
    "label",
    "url",
    "status",
    "notes",
    "reviewer",
    "reviewed_at_utc",
]


def _require_db_password() -> str:
    password = os.environ.get("JUSTNEWS_DB_PASSWORD")
    if not password:
        sys.exit("JUSTNEWS_DB_PASSWORD is not set.")
    return password


def fetch_sources() -> List[dict]:
    password = _require_db_password()
    conn = psycopg.connect(
        host=os.environ.get("JUSTNEWS_DB_HOST", "localhost"),
        port=os.environ.get("JUSTNEWS_DB_PORT", "5432"),
        dbname=os.environ.get("JUSTNEWS_DB_NAME", "justnews"),
        user=os.environ.get("JUSTNEWS_DB_USER", "justnews_user"),
        password=password,
        row_factory=dict_row,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, url, domain, name, metadata
                FROM public.sources
                ORDER BY id
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def label_for(source: dict) -> str:
    metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else None
    label = source.get("name") or source.get("domain")
    if not label and metadata:
        label = metadata.get("display_name") or metadata.get("title")
    return label or source["url"]


def load_existing_results(path: Path) -> Dict[int, dict]:
    if not path.exists():
        return {}
    existing: Dict[int, dict] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                source_id = int(row.get("source_id", ""))
            except ValueError:
                continue
            existing[source_id] = row
    return existing


def build_result_row(
    source_id: int,
    label: str,
    url: str,
    status: str,
    notes: str,
    reviewer: str,
    reviewed_at: datetime | None = None,
) -> dict:
    reviewed = (reviewed_at or datetime.utcnow()).isoformat(timespec="seconds")
    return {
        "source_id": source_id,
        "label": label,
        "url": url,
        "status": status,
        "notes": notes,
        "reviewer": reviewer,
        "reviewed_at_utc": reviewed,
    }


def write_result(path: Path, row: dict) -> None:
    exists = path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def filter_sources(
    sources: Iterable[dict],
    start_id: int | None,
    existing: Dict[int, dict],
    recheck: bool,
) -> List[dict]:
    result: List[dict] = []
    for source in sources:
        if start_id and source["id"] < start_id:
            continue
        if not recheck and source["id"] in existing:
            continue
        result.append(source)
    return result
