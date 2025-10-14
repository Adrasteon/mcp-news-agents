
import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import psycopg
from crawl4ai import AdaptiveCrawler
from fastmcp import FastMCP
from prometheus_client import Counter, Gauge, Summary, start_http_server
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from pydantic import BaseModel, Field

from agent_config import AgentConfig, load_config


REQUESTS = Counter('requests_total', 'Total requests')
ARTICLES_STORED = Counter('research_articles_stored_total', 'Articles persisted into justnews.public.articles')
ARTICLES_SKIPPED = Counter('research_articles_skipped_total', 'Articles skipped due to validation or duplication')
SOURCES_FAILED = Counter('research_sources_failed_total', 'Sources that failed during crawl or persistence')
ARTICLES_EMBEDDED = Counter('research_articles_embedded_total', 'Articles with GPU embeddings generated')
EMBEDDING_FAILURES = Counter('research_embedding_failures_total', 'Embedding attempts that failed')
PIPELINE_LATENCY = Summary('research_pipeline_latency_seconds', 'Wall-clock time to crawl and store a batch')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')

LOG_LEVEL = os.getenv("NEWS_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), handlers=[logging.StreamHandler()])

class CrawlNewsInput(BaseModel):
    """Input for crawling top news (no fields required)."""
    pass

class CrawlNewsOutput(BaseModel):
    articles: List[Dict[str, Any]] = Field(..., description="List of crawled news articles.")


@dataclass
class SourceRecord:
    id: int
    url: str
    domain: Optional[str]
    metadata: Dict[str, Any]


@dataclass
class NormalizedArticle:
    url: str
    title: str
    content: str
    summary: str
    metadata: Dict[str, Any]
    source_map_metadata: Dict[str, Any]
    confidence: float
    embedding_input: str


class EmbeddingService:
    """Lazy GPU-aware embedding helper that enforces memory limits."""

    def __init__(self) -> None:
        self._model = None
        self._torch = None
        self._device = "cpu"
        self._model_name = os.getenv("NEWS_EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
        self._batch_size = int(os.getenv("NEWS_EMBEDDING_BATCH", "8"))
        self._gpu_fraction = float(os.getenv("NEWS_EMBEDDING_GPU_FRACTION", "0.65"))
        self._target_dim = int(os.getenv("NEWS_EMBEDDING_DIM", "768"))
        self._lock = asyncio.Lock()
        self._disabled = False

    @property
    def disabled(self) -> bool:
        return self._disabled

    async def _ensure_model(self) -> None:
        if self._model is not None or self._disabled:
            return

        async with self._lock:
            if self._model is not None or self._disabled:
                return

            try:
                import torch  # type: ignore
                from sentence_transformers import SentenceTransformer  # type: ignore
            except ImportError:
                logging.warning("Embedding libraries not available; disabling GPU embeddings.")
                self._disabled = True
                return

            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cuda":
                try:
                    torch.cuda.set_per_process_memory_fraction(self._gpu_fraction)
                except Exception as exc:  # pragma: no cover - defensive
                    logging.warning("Unable to apply GPU memory cap: %s", exc)

            model = SentenceTransformer(self._model_name, device=device)
            model_dim = getattr(model, "get_sentence_embedding_dimension", lambda: None)()
            if model_dim and model_dim != self._target_dim:
                logging.warning(
                    "Embedding dimension mismatch (model=%s driver=%s). Updating target to %s.",
                    model_dim,
                    self._target_dim,
                    model_dim,
                )
                self._target_dim = model_dim

            self._model = model
            self._torch = torch
            self._device = device

    async def encode(self, texts: Sequence[str]) -> List[List[float]]:
        if not texts:
            return []

        await self._ensure_model()
        if self._disabled or self._model is None or self._torch is None:
            return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._encode_sync, list(texts))

    def _encode_sync(self, texts: List[str]) -> List[List[float]]:
        assert self._model is not None and self._torch is not None
        torch = self._torch

        with torch.inference_mode():
            embeddings = self._model.encode(
                texts,
                batch_size=self._batch_size,
                convert_to_numpy=True,
                normalize_embeddings=False,
            )

        # Free cached GPU memory proactively to avoid fragmentation.
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return embeddings.tolist()


_EMBEDDING_SERVICE: Optional[EmbeddingService] = None
_EMBEDDING_FINGERPRINT: Optional[AgentConfig] = None


def embedding_service(config: AgentConfig) -> Optional[EmbeddingService]:
    global _EMBEDDING_SERVICE, _EMBEDDING_FINGERPRINT

    if not config.embedding_enabled:
        return None

    if _EMBEDDING_SERVICE is None or _EMBEDDING_FINGERPRINT != config:
        _EMBEDDING_SERVICE = EmbeddingService()
        _EMBEDDING_SERVICE._model_name = config.embedding_model
        _EMBEDDING_SERVICE._batch_size = config.embedding_batch_size
        _EMBEDDING_SERVICE._gpu_fraction = config.embedding_gpu_fraction
        _EMBEDDING_FINGERPRINT = config

    if _EMBEDDING_SERVICE.disabled:
        return None

    return _EMBEDDING_SERVICE


def build_conninfo(config: AgentConfig) -> str:
    password = os.getenv("JUSTNEWS_DB_PASSWORD")
    if not password:
        raise RuntimeError("JUSTNEWS_DB_PASSWORD must be provided via environment variable.")

    return make_conninfo(
        user=config.db_user,
        password=password,
        host=config.db_host,
        port=str(config.db_port),
        dbname=config.db_name,
        application_name="news-research-agent",
    )


@asynccontextmanager
async def justnews_connection(config: AgentConfig) -> AsyncIterator[psycopg.AsyncConnection]:
    conn = await psycopg.AsyncConnection.connect(conninfo=build_conninfo(config))
    conn.row_factory = dict_row
    try:
        yield conn
    finally:
        await conn.close()


async def fetch_sources(conn: psycopg.AsyncConnection, batch_size: int) -> List[SourceRecord]:
    query = """
        SELECT id, url, domain, COALESCE(metadata, '{}'::jsonb) AS metadata
        FROM public.sources
        WHERE url IS NOT NULL
        ORDER BY COALESCE(last_verified, created_at) DESC NULLS LAST
        LIMIT %s
    """
    async with conn.cursor() as cur:
        await cur.execute(query, (batch_size,))
        rows = await cur.fetchall()

    return [
        SourceRecord(
            id=row["id"],
            url=row["url"],
            domain=row.get("domain"),
            metadata=row.get("metadata", {}),
        )
        for row in rows
    ]


def extract_articles_from_state(state: Any) -> List[Dict[str, Any]]:
    if not hasattr(state, "results"):
        return []

    articles: List[Dict[str, Any]] = []
    for result in getattr(state, "results", []):
        payload = {
            "title": getattr(result, "title", None) or getattr(result, "text", None),
            "text": getattr(result, "text", None),
            "summary": getattr(result, "summary", None),
            "url": getattr(result, "url", None) or getattr(result, "link", None),
            "metadata": getattr(result, "metadata", {}) if hasattr(result, "metadata") else {},
        }
        articles.append(payload)

    return articles


def normalize_article(raw: Dict[str, Any], source: SourceRecord) -> Optional[NormalizedArticle]:
    url = (raw.get("url") or "").strip()
    if not url:
        return None

    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)
    if not parsed.netloc:
        return None

    title = (raw.get("title") or "").strip()
    text = (raw.get("text") or "").strip()
    if not text:
        return None

    summary = (raw.get("summary") or text[:512]).strip()

    metadata = raw.get("metadata") or {}
    metadata.setdefault("crawler", {})
    metadata["crawler"].update(
        {
            "agent": "news-research-agent",
            "source_id": source.id,
            "source_url": source.url,
            "normalized_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    source_map_metadata = {
        "agent": "news-research-agent",
        "confidence_basis": "direct-crawl",
        "crawl_started_at": metadata["crawler"]["normalized_at"],
    }

    return NormalizedArticle(
        url=url,
        title=title or text[:120],
        content=text,
        summary=summary,
        metadata=metadata,
        source_map_metadata=source_map_metadata,
        confidence=1.0,
        embedding_input=text,
    )


async def article_exists(cur: psycopg.AsyncCursor, url: str) -> bool:
    await cur.execute(
        "SELECT 1 FROM public.articles WHERE url = %s LIMIT 1",
        (url,),
    )
    return await cur.fetchone() is not None


async def persist_articles(
    conn: psycopg.AsyncConnection,
    source: SourceRecord,
    articles: Sequence[Dict[str, Any]],
    config: AgentConfig,
) -> List[Dict[str, Any]]:
    if not articles:
        logging.debug("Source %s (%s) produced no articles.", source.id, source.url)
        return []

    stored: List[Dict[str, Any]] = []
    pending_embeddings: List[Tuple[int, str]] = []

    async with conn.cursor() as cur:
        for raw_article in articles:
            normalized = normalize_article(raw_article, source)
            if not normalized:
                logging.debug(
                    "Skipping article from source %s (%s): normalization failed (url=%r, title=%r)",
                    source.id,
                    source.url,
                    raw_article.get("url"),
                    raw_article.get("title"),
                )
                ARTICLES_SKIPPED.inc()
                continue

            if await article_exists(cur, normalized.url):
                logging.debug(
                    "Skipping duplicate article: source=%s url=%s",
                    source.id,
                    normalized.url,
                )
                ARTICLES_SKIPPED.inc()
                continue

            await cur.execute(
                """
                INSERT INTO public.articles (
                    url,
                    title,
                    content,
                    summary,
                    metadata,
                    analyzed,
                    source_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    normalized.url,
                    normalized.title,
                    normalized.content,
                    normalized.summary,
                    Jsonb(normalized.metadata),
                    False,
                    source.id,
                ),
            )

            row = await cur.fetchone()
            if not row:
                continue

            article_id = row[0]

            await cur.execute(
                """
                SELECT 1
                FROM public.article_source_map
                WHERE article_id = %s AND source_id = %s
                LIMIT 1
                """,
                (article_id, source.id),
            )

            exists = await cur.fetchone()
            if not exists:
                await cur.execute(
                    """
                    INSERT INTO public.article_source_map (
                        article_id,
                        source_id,
                        confidence,
                        metadata
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        article_id,
                        source.id,
                        normalized.confidence,
                        Jsonb(normalized.source_map_metadata),
                    ),
                )

            stored.append(
                {
                    "id": article_id,
                    "url": normalized.url,
                    "title": normalized.title,
                    "summary": normalized.summary,
                }
            )
            pending_embeddings.append((article_id, normalized.embedding_input))

    if stored:
        logging.info(
            "Stored %d new articles for source %s (%s)",
            len(stored),
            source.id,
            source.url,
        )
    else:
        logging.debug("No new articles stored for source %s (%s)", source.id, source.url)

    if stored:
        ARTICLES_STORED.inc(len(stored))

    if pending_embeddings:
        await update_embeddings(conn, pending_embeddings, config)

    return stored


async def update_embeddings(
    conn: psycopg.AsyncConnection,
    items: Sequence[Tuple[int, str]],
    config: AgentConfig,
) -> None:
    service = embedding_service(config)
    if service is None:
        logging.debug("Embedding service disabled; skipping %d articles.", len(items))
        return

    article_ids, inputs = zip(*items)
    try:
        embeddings = await service.encode(inputs)
    except Exception as exc:  # pragma: no cover - defensive
        EMBEDDING_FAILURES.inc()
        logging.error("Embedding pipeline failed: %s", exc)
        return

    if not embeddings:
        logging.debug("Embedding service returned no vectors; skipping updates for %d articles.", len(items))
        return

    async with conn.cursor() as cur:
        for article_id, embedding in zip(article_ids, embeddings):
            embedding_literal = "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
            try:
                await cur.execute(
                    """
                    UPDATE public.articles
                    SET embedding = %s::vector,
                        analyzed = true,
                        updated_at = timezone('utc', now())
                    WHERE id = %s
                    """,
                    (embedding_literal, article_id),
                )
                ARTICLES_EMBEDDED.inc()
            except Exception as exc:  # pragma: no cover - defensive
                EMBEDDING_FAILURES.inc()
                logging.error("Failed to persist embedding for article %s: %s", article_id, exc)


async def run_pipeline(config: AgentConfig) -> List[Dict[str, Any]]:
    start = datetime.now(timezone.utc)
    async with justnews_connection(config) as conn:
        sources = await fetch_sources(conn, config.source_batch_size)

    if not sources:
        logging.info("No sources retrieved for ingestion batch.")
        return []

    logging.info("Starting ingestion for %d sources (parallelism=%d)", len(sources), config.crawl_parallelism)

    stored: List[Dict[str, Any]] = []
    stored_lock = asyncio.Lock()
    failure_lock = asyncio.Lock()
    failure_count = 0

    semaphore = asyncio.Semaphore(max(1, config.crawl_parallelism))

    async def process_source(source: SourceRecord) -> None:
        nonlocal failure_count

        async with semaphore:
            crawler = AdaptiveCrawler()
            try:
                query = source.metadata.get("primary_query", "top news") if source.metadata else "top news"
                state = await asyncio.wait_for(
                    crawler.digest(start_url=source.url, query=query),
                    timeout=config.crawl_timeout_seconds,
                )
            except Exception as exc:  # pragma: no cover - crawler issues
                SOURCES_FAILED.inc()
                logging.error("Crawler failed for source %s (%s): %s", source.id, source.url, exc)
                async with failure_lock:
                    failure_count += 1
                return

            articles = extract_articles_from_state(state)
            try:
                async with justnews_connection(config) as conn_inner:
                    persisted = await persist_articles(conn_inner, source, articles, config)
                    await conn_inner.commit()
            except Exception as exc:
                SOURCES_FAILED.inc()
                logging.error("Persistence failed for source %s: %s", source.id, exc)
                async with failure_lock:
                    failure_count += 1
                return

            if persisted:
                async with stored_lock:
                    stored.extend(persisted)

    tasks = [asyncio.create_task(process_source(source)) for source in sources]

    for task in asyncio.as_completed(tasks):
        await task
        async with failure_lock:
            if failure_count >= config.max_source_failures:
                logging.error("Max source failure threshold (%s) reached; cancelling remaining tasks.", config.max_source_failures)
                for pending in tasks:
                    if not pending.done():
                        pending.cancel()
                break

    duration = (datetime.now(timezone.utc) - start).total_seconds()
    PIPELINE_LATENCY.observe(duration)
    logging.info(
        "Ingestion run complete: stored=%d sources=%d failures=%d duration=%.2fs",
        len(stored),
        len(sources),
        failure_count,
        duration,
    )
    return stored



# Initialize FastMCP app before registering tools
app = FastMCP(
    name="news-research-agent",
    version="1.0.0"
)

@app.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")

@app.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading
    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")

# Register crawl_news as a FastMCP tool using the decorator
@app.tool(
    name="crawl_top_news",
    description="Ingest news articles from configured sources into the justnews PostgreSQL cluster."
)
def crawl_news(_: CrawlNewsInput) -> CrawlNewsOutput:
    """Crawl configured sources and persist results."""

    REQUESTS.inc()

    config = load_config()

    try:
        stored = asyncio.run(run_pipeline(config=config))
        return CrawlNewsOutput(articles=stored)
    except Exception as exc:  # pragma: no cover - defensive
        SOURCES_FAILED.inc()
        logging.error("Failed pipeline execution: %s", exc)
        return CrawlNewsOutput(articles=[])




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
            config_port = int(config.get("port", 9501))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9501))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    app.settings.host = host
    app.settings.port = port
    start_http_server(9601)
    AGENT_STATUS.set(1)
    app.run(transport="streamable-http")
