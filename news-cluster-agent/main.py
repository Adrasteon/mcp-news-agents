

import os
import psycopg2
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from transformers import pipeline
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import sys
from prometheus_client import start_http_server, Counter, Gauge

REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')



# --- CONFIGURATION ---
DB_HOST = os.getenv("NEWS_DB_HOST", "localhost")
DB_PORT = os.getenv("NEWS_DB_PORT", "5432")
DB_NAME = os.getenv("NEWS_DB_NAME", "newsdb")
DB_USER = os.getenv("NEWS_DB_USER", "postgres")
DB_PASS = os.getenv("NEWS_DB_PASS", "password")

# --- AI PIPELINES ---
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# --- DATABASE CONNECTION ---
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )

def fetch_analyzed_articles():
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, content FROM news_articles WHERE cluster_title IS NULL")
            return cur.fetchall()

def update_article_cluster(article_id, cluster_title):
    with get_db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE news_articles SET cluster_title = %s WHERE id = %s",
                (cluster_title, article_id)
            )
        conn.commit()

def cluster_articles(articles, n_clusters=5):
    texts = [title + ". " + content for _, title, content in articles]
    vectorizer = TfidfVectorizer(stop_words="english", max_features=512)
    X = vectorizer.fit_transform(texts)
    kmeans = KMeans(n_clusters=min(n_clusters, len(articles)), random_state=42)
    labels = kmeans.fit_predict(X)
    return labels

def generate_cluster_titles(articles, labels):
    clusters = {}
    for label in set(labels):
        cluster_texts = [articles[i][2] for i in range(len(articles)) if labels[i] == label]
        joined = " ".join(cluster_texts)[:1024]
        summary = summarizer(joined, max_length=15, min_length=5, do_sample=False)[0]["summary_text"]
        clusters[label] = summary
    return clusters


# --- MCP Server (FastMCP) ---

mcp = FastMCP("news-cluster-agent")

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
def cluster_new_articles(n_clusters: int = 5) -> dict:
    """Cluster new analyzed articles by topic and assign group titles."""
    articles = fetch_analyzed_articles()
    if not articles:
        return {"message": "No new articles to cluster."}
    labels = cluster_articles(articles, n_clusters=n_clusters)
    cluster_titles = generate_cluster_titles(articles, labels)
    assignments = []
    for idx, (article_id, _, _) in enumerate(articles):
        cluster_title = cluster_titles[labels[idx]]
        update_article_cluster(article_id, cluster_title)
        assignments.append({"article_id": article_id, "cluster_title": cluster_title})
    return {"assignments": assignments, "message": "Clustering complete."}


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
            config_port = int(config.get("port", 9503))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9503))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9603)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
