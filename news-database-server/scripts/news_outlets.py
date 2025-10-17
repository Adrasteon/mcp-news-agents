"""Import news outlet listings from markdown into the JustNews Postgres database.

Example usage:

    python scripts/news_outlets.py --dry-run
    python scripts/news_outlets.py --map-articles

Connection details are resolved via `DATABASE_URL` or the
`JUSTNEWS_DB_*` environment variables, falling back to `~/.pgpass` if
available.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from scripts.db_config import get_db_conn

import psycopg
from psycopg import Connection
from psycopg.errors import UndefinedTable
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


def parse_markdown_table_rows(md: str) -> Iterable[tuple[str, str, str]]:
    """Yield (url, name, description) rows from markdown tables.

    The markdown contains repeated tables with the header:
    `| URL | Name | Description |`. Each data row is emitted verbatim with
    surrounding whitespace/backticks stripped.
    """

    lines = md.splitlines()
    i = 0
    header_re = re.compile(r"\|\s*URL\s*\|\s*Name\s*\|\s*Description\s*\|", re.I)
    while i < len(lines):
        line = lines[i]
        if header_re.search(line):
            # Skip the separator line (| :--- | :--- | :--- |)
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if re.match(r"^\|\s*:?-+", row):
                    i += 1
                    continue
                columns = [c.strip(" `") for c in row.split("|") if c.strip()]
                if len(columns) >= 3:
                    yield columns[0], columns[1], columns[2]
                i += 1
        else:
            i += 1


def domain_from_url(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url)
    return match.group(1).lower() if match else url.lower()


UPSERT_SQL = """
WITH updated AS (
    UPDATE public.sources
       SET domain = %(domain)s,
           name = %(name)s,
           description = %(description)s,
           metadata = public.sources.metadata || %(metadata)s::jsonb,
           last_verified = now(),
           updated_at = now()
     WHERE lower(url) = lower(%(url)s)
 RETURNING id
), inserted AS (
    INSERT INTO public.sources (url, domain, name, description, last_verified, metadata, updated_at)
    SELECT %(url)s, %(domain)s, %(name)s, %(description)s, now(), %(metadata)s::jsonb, now()
    WHERE NOT EXISTS (SELECT 1 FROM updated)
 RETURNING id
)
SELECT id FROM updated
UNION ALL
SELECT id FROM inserted;
"""


def upsert_outlets(rows: Iterable[tuple[str, str, str]], conn: Connection) -> list[int]:
    ids: list[int] = []
    with conn.cursor() as cur:
        for url, name, description in rows:
            domain = domain_from_url(url)
            metadata = Jsonb({"source": "potential_news_sources.md"})
            cur.execute(
                UPSERT_SQL,
                {
                    "url": url,
                    "domain": domain,
                    "name": name,
                    "description": description,
                    "metadata": metadata,
                },
            )
            row = cur.fetchone()
            if row:
                ids.append(row[0])
    conn.commit()
    return ids


def create_provenance_mappings(conn: Connection) -> None:
    """Best-effort mapping of article metadata URLs onto sources by domain."""

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, domain FROM public.sources WHERE domain IS NOT NULL")
            domain_map = {row["domain"].lower(): row["id"] for row in cur}
    except UndefinedTable:
        conn.rollback()
        print("Warning: table public.sources not found; skipping provenance mapping", file=sys.stderr)
        return

    if not domain_map:
        return

    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT id, metadata FROM public.articles WHERE metadata ? 'url'")
            articles = list(cur)
    except UndefinedTable:
        conn.rollback()
        print("Warning: table public.articles not found; skipping provenance mapping", file=sys.stderr)
        return

    if not articles:
        return

    insert_sql = (
        "INSERT INTO public.article_source_map "
        "(article_id, source_id, confidence, detected_at, metadata) "
        "VALUES (%s, %s, %s, now(), %s) "
        "ON CONFLICT DO NOTHING"
    )

    with conn.cursor() as insert_cur:
        for article in articles:
            metadata = article["metadata"] or {}
            url = metadata.get("url") if isinstance(metadata, dict) else None
            if not url:
                continue
            domain = domain_from_url(url)
            source_id = domain_map.get(domain)
            if not source_id:
                continue
            insert_cur.execute(
                insert_sql,
                (article["id"], source_id, 0.95, Jsonb({"matched_by": "domain_match"})),
            )

    conn.commit()


def load_markdown(path: Path) -> list[tuple[str, str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Markdown source not found: {path}")
    text = path.read_text(encoding="utf-8")
    rows = list(parse_markdown_table_rows(text))
    if not rows:
        raise ValueError("No rows parsed from markdown table")
    return rows


def main(argv: list[str] | None = None) -> int:
    default_md = REPO_ROOT / "reference" / "potential_news_sources.md"

    parser = argparse.ArgumentParser(description="Populate public.sources from markdown")
    parser.add_argument(
        "--file",
        "-f",
        default=str(default_md),
        help="Path to potential_news_sources.md (default: reference/potential_news_sources.md)",
    )
    parser.add_argument(
        "--map-articles",
        action="store_true",
        help="Attempt to map existing articles to sources via domain matching",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse markdown and print the first rows without touching the database",
    )
    args = parser.parse_args(argv)

    try:
        rows = load_markdown(Path(args.file))
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"Dry run: parsed {len(rows)} rows")
        for row in rows[:20]:
            print(row)
        if len(rows) > 20:
            print("…")
        return 0

    conn = get_db_conn()
    try:
        upserted_ids = upsert_outlets(rows, conn)
        print(f"Upserted {len(upserted_ids)} sources")
        if args.map_articles:
            print("Creating provenance mappings (domain match)…")
            create_provenance_mappings(conn)
            print("Provenance mapping complete")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
