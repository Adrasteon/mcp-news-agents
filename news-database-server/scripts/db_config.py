"""Database connection helper for the MCP news database tooling."""
from __future__ import annotations

import os
from pathlib import Path

import psycopg


def _read_pgpass(params: dict[str, object]) -> None:
    """Populate user/password from ~/.pgpass when env vars omit them."""
    pgpass_path = Path.home() / ".pgpass"
    if not pgpass_path.exists():
        return

    try:
        with pgpass_path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(":")
                if len(parts) != 5:
                    continue
                host, port, database, user, password = parts
                host_match = host in {params["host"], "*"}
                port_match = str(port) in {str(params["port"]), "*"}
                db_match = database in {params["dbname"], "*"}
                if not (host_match and port_match and db_match):
                    continue

                explicit_user = os.environ.get("JUSTNEWS_DB_USER") is not None
                if explicit_user:
                    if user in {params["user"], "*"}:
                        params["password"] = password
                        return
                    continue

                params["user"] = user
                params["password"] = password
                return
    except OSError:
        # Best-effort only; leave credentials unchanged on failure.
        return


def get_db_conn():
    """Return a psycopg connection using env vars or ~/.pgpass fallback."""
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg.connect(database_url)

    params: dict[str, object] = {
        "host": os.environ.get("JUSTNEWS_DB_HOST", "localhost"),
        "port": int(os.environ.get("JUSTNEWS_DB_PORT", "5432")),
        "dbname": os.environ.get("JUSTNEWS_DB_NAME", "justnews"),
        "user": os.environ.get("JUSTNEWS_DB_USER", os.getenv("USER", "justnews_user")),
        "password": os.environ.get("JUSTNEWS_DB_PASSWORD"),
    }

    if not params.get("password"):
        _read_pgpass(params)

    return psycopg.connect(**params)
