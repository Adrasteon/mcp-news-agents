

import os
from pathlib import Path
import psycopg2
import numpy as np
from transformers import pipeline
import spacy
from textblob import TextBlob
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import sys
from prometheus_client import start_http_server, Counter, Gauge

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')


# --- CONFIGURATION ---
DB_HOST = os.getenv("NEWS_DB_HOST", "localhost")
# --- AI PIPELINES ---
# Get model path from orchestrator/memory agent (placeholder function)
BASE_DIR = Path(__file__).resolve().parent
MODEL_STORE_ROOT = (BASE_DIR.parent / "model_store").resolve()


def get_local_model_path(model_name: str) -> Path:
    """Resolve the local path for a model managed by the orchestrator."""
    # TODO: Replace with actual orchestrator/memory agent API call
    return (MODEL_STORE_ROOT / "news-cleaner-agent" / "current" / model_name).resolve()

# Load model and tokenizer from local model_store
summarization_model_path = get_local_model_path("bart-large-cnn")


def _fallback_summarizer(text, max_length=200, min_length=60, **_):
    """Fallback summarizer that trims the text when no local model is available."""
    cleaned = (text or "").strip()
    if not cleaned:
        return [{"summary_text": ""}]
    sentences = cleaned.replace("\n", " ").split(".")
    summary = ".".join(sentences[:3]).strip()
    summary = summary[:max_length]
    return [{"summary_text": summary}]


if summarization_model_path.exists():
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            str(summarization_model_path),
            local_files_only=True
        )
        model = AutoModelForSeq2SeqLM.from_pretrained(
            str(summarization_model_path),
            local_files_only=True
        )
        summarizer = pipeline(
            "summarization",
            model=model,
            tokenizer=tokenizer,
            framework="pt"
        )
    except Exception as exc:  # pragma: no cover - safety
        print(f"[WARNING] Failed to load summarization model locally: {exc}")
        summarizer = _fallback_summarizer
else:
    print(
        f"[WARNING] Local model path not found for summarization: {summarization_model_path}."
        " Falling back to naive summarizer."
    )
    summarizer = _fallback_summarizer
DB_NAME = os.getenv("NEWS_DB_NAME", "newsdb")
DB_USER = os.getenv("NEWS_DB_USER", "postgres")
DB_PASS = os.getenv("NEWS_DB_PASS", "password")

# Load spaCy model for NER
nlp = spacy.load("en_core_web_sm")

# --- DATABASE CONNECTION ---
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def fetch_article_groups():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cluster_title, array_agg(id), array_agg(title), array_agg(content), array_agg(analysis_score)
                FROM news_articles
                WHERE cluster_title IS NOT NULL
                GROUP BY cluster_title
            """)
            return cur.fetchall()

def save_cleaned_article(cluster_title, cleaned_title, cleaned_content, metrics):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cleaned_articles (cluster_title, cleaned_title, cleaned_content, metrics)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (cluster_title) DO UPDATE SET cleaned_title=EXCLUDED.cleaned_title, cleaned_content=EXCLUDED.cleaned_content, metrics=EXCLUDED.metrics
                """,
                (cluster_title, cleaned_title, cleaned_content, metrics)
            )
        conn.commit()

def extract_attributed_quotes(articles, titles):
    quotes = []
    for content, title in zip(articles, titles):
        doc = nlp(content)
        for sent in doc.sents:
            if '"' in sent.text or "'" in sent.text:
                # Simple quote detection
                quotes.append({
                    "quote": sent.text,
                    "source": title
                })
    return quotes

def synthesize_article(articles, titles, scores, cluster_title):
    # Weigh articles by analysis score
    weighted_text = " ".join([
        (content * int(score)) if score and score > 0 else content
        for content, score in zip(articles, scores)
    ])
    # Summarize the story
    summary = summarizer(weighted_text[:2048], max_length=200, min_length=60, do_sample=False)[0]["summary_text"]
    # Extract and filter quotes
    quotes = extract_attributed_quotes(articles, titles)
    # Remove offensive content (simple filter)
    summary = filter_offensive_language(summary)
    # Compose cleaned article
    cleaned_content = summary + "\n\nKey Quotes:\n" + "\n".join([
        f'"{q["quote"]}" — {q["source"]}' for q in quotes if not contains_offensive(q["quote"])
    ])
    # Metrics
    metrics = {
        "num_variants": len(articles),
        "num_quotes": len(quotes),
        "avg_score": float(np.mean(scores)) if scores else 0.0
    }
    return cluster_title, summary, cleaned_content, metrics

def filter_offensive_language(text):
    # Placeholder: Replace with a more robust filter as needed
    offensive_words = ["hate", "racist", "offensive"]
    for word in offensive_words:
        text = text.replace(word, "[removed]")
    return text

def contains_offensive(text):
    # Placeholder: Replace with a more robust filter as needed
    offensive_words = ["hate", "racist", "offensive"]
    return any(word in text.lower() for word in offensive_words)


# --- MCP Server (FastMCP) ---

mcp = FastMCP("news-cleaner-agent")

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
def clean_article_group(cluster_title: str) -> dict:
    """Synthesize a neutral, cleaned article for a group of articles with the same cluster title."""
    groups = fetch_article_groups()
    for group in groups:
        group_title, ids, titles, articles, scores = group
        if group_title == cluster_title:
            group_title, cleaned_title, cleaned_content, metrics = synthesize_article(articles, titles, scores, group_title)
            save_cleaned_article(group_title, cleaned_title, cleaned_content, str(metrics))
            return {"cluster_title": group_title, "cleaned_title": cleaned_title, "metrics": metrics}
    return {"error": "Cluster title not found."}


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
            config_port = int(config.get("port", 9504))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9504))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9604)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
