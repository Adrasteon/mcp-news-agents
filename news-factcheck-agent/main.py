# news-factcheck-agent: AI-driven fact checker for all facts in new articles

import os
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse
import sys
from prometheus_client import start_http_server, Counter, Gauge

REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')


mcp = FastMCP("news-factcheck-agent")

@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")

@mcp.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading
    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")

@mcp.tool()
def fact_check_article(article_id: int, text: str) -> dict:
    """Fact-check all facts in the given article text (including quotes/statements)."""
    # TODO: Implement AI-driven fact-checking logic
    return {"article_id": article_id, "result": "No implementation yet."}


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
            config_port = int(config.get("port", 9505))
    except Exception:
        pass
    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9505))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9605)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
