
import logging
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import sys
    # ToolInput/ToolOutput removed; use standard types and docstrings
from typing import Dict, Any, List, Optional
import psycopg
import numpy as np
from prometheus_client import start_http_server, Counter, Gauge

REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')

# Configure logging
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

DB_CONN_STR = "postgresql://postgres:postgres@localhost:5432/newsdb"

  # Tool schemas now defined by function signatures and docstrings

# --- DB Setup ---
def ensure_schema():
    with psycopg.connect(DB_CONN_STR) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE TABLE IF NOT EXISTS news_articles (
                    id SERIAL PRIMARY KEY,
                    title TEXT,
                    content TEXT,
                    metadata JSONB,
                    bias TEXT,
                    sentiment FLOAT,
                    entities JSONB,
                    persuasion TEXT,
                    embedding vector(384)
                );
            """)
        conn.commit()


# --- MCP Server (FastMCP) ---

mcp = FastMCP("news-database-server")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")

@mcp.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading
    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")

# --- Tool Registration ---
@mcp.tool()
def insert_article(
    title: str,
    text: str,
    metadata: Dict[str, Any] = {},
    bias: Optional[str] = None,
    sentiment: Optional[float] = None,
    entities: Optional[List[str]] = None,
    persuasion: Optional[str] = None,
    vector: Optional[List[float]] = None
) -> dict:
    """Insert a news article and its analysis into the database (with vector support)."""
    try:
        ensure_schema()
        with psycopg.connect(DB_CONN_STR) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO news_articles (title, content, metadata, bias, sentiment, entities, persuasion, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (title) DO NOTHING
                    """,
                    (
                        title,
                        text,
                        metadata,
                        bias,
                        sentiment,
                        entities,
                        persuasion,
                        np.array(vector, dtype=np.float32) if vector else None
                    )
                )
            conn.commit()
        return {"success": True}
    except Exception as e:
        logging.error(f"Insert failed: {e}")
        return {"success": False, "error": str(e)}

@mcp.tool()
def query_articles(
    query: Optional[str] = None,
    vector: Optional[List[float]] = None,
    top_k: int = 10
) -> dict:
    """Query news articles by recency or vector similarity."""
    try:
        ensure_schema()
        with psycopg.connect(DB_CONN_STR) as conn:
            with conn.cursor() as cur:
                if vector:
                    cur.execute(
                        """
                        SELECT title, content, metadata, bias, sentiment, entities, persuasion
                        FROM news_articles
                        ORDER BY embedding <-> %s
                        LIMIT %s
                        """,
                        (np.array(vector, dtype=np.float32), top_k)
                    )
                else:
                    cur.execute(
                        """
                        SELECT title, content, metadata, bias, sentiment, entities, persuasion
                        FROM news_articles
                        ORDER BY id DESC
                        LIMIT %s
                        """,
                        (top_k,)
                    )
                rows = cur.fetchall()
                articles = [
                    {
                        "title": r[0],
                        "text": r[1],
                        "metadata": r[2],
                        "bias": r[3],
                        "sentiment": r[4],
                        "entities": r[5],
                        "persuasion": r[6],
                    }
                    for r in rows
                ]
        return {"articles": articles}
    except Exception as e:
        logging.error(f"Query failed: {e}")
        return {"articles": []}

# --- MCP Server ---



import threading
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

shutdown_flag = threading.Event()

class ShutdownHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/shutdown":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"shutting down")
            threading.Thread(target=lambda: (shutdown_flag.set(), sys.exit(0))).start()
        elif self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    import os
    import json
    # Prefer config file for port, fallback to env var, then default
    config_port = None
    try:
        with open("config.json") as f:
            config = json.load(f)
            config_port = int(config.get("port", 9502))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9502))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9602)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
