

from typing import Dict, Any
from textblob import TextBlob
import spacy
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import sys
from prometheus_client import start_http_server, Counter, Gauge
import os
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import sys

REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')

# Load spaCy model for entity recognition
try:
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    nlp = None
    print("[WARNING] spaCy model 'en_core_web_sm' not loaded. Entity recognition will not work.")

shutdown_flag = threading.Event()

mcp = FastMCP("news-analyzer-agent")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")

@mcp.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading
    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")

BIAS_KEYWORDS = ["alleged", "reportedly", "claims", "sources say", "controversial", "unsubstantiated"]
PERSUASION_KEYWORDS = ["must", "should", "need to", "obviously", "clearly", "undeniable"]

@mcp.tool()
def analyze_article(title: str, text: str, metadata: Dict[str, Any] = {}) -> dict:
    """Analyze a news article for bias, sentiment, entities, and persuasion techniques."""
    # Sentiment
    blob = TextBlob(text)
    sentiment = blob.sentiment.polarity

    # Entities
    if nlp:
        doc = nlp(text)
        entities = [(ent.text, ent.label_) for ent in doc.ents]
    else:
        entities = []

    # Bias detection (very basic)
    bias = "neutral"
    lowered = text.lower()
    if any(word in lowered for word in BIAS_KEYWORDS):
        bias = "potential bias"

    # Persuasion detection (very basic)
    persuasion = "none"
    if any(word in lowered for word in PERSUASION_KEYWORDS):
        persuasion = "persuasive language detected"

    return {
        "bias": bias,
        "sentiment": sentiment,
        "entities": entities,
        "persuasion": persuasion
    }


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
    # Prefer config file for port, fallback to env var, then default
    config_port = None
    try:
        with open("config.json") as f:
            config = json.load(f)
            config_port = int(config.get("port", 9500))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9500))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9600)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
