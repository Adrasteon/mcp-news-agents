
# news-orchestrator-agent: AI-driven job control and flow manager (MCP SDK)

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Any, Dict, Optional, Tuple

import httpx
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from prometheus_client import start_http_server, Counter, Gauge

REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')


mcp = FastMCP("news-orchestrator-agent")

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

MEMORY_AGENT_URL = os.getenv("NEWS_MEMORY_AGENT_URL", "http://127.0.0.1:9507").rstrip("/")
SESSION_LOCK = asyncio.Lock()
GPU_SESSIONS: Dict[str, Dict[str, Any]] = {}


async def _reserve_with_memory_agent(agent: str, memory_fraction: float, min_memory_mb: int) -> Tuple[int, Dict[str, Any]]:
    payload = {
        "agent": agent,
        "memory_fraction": memory_fraction,
        "min_memory_mb": min_memory_mb,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{MEMORY_AGENT_URL}/gpu/reserve", json=payload)
    except Exception as exc:
        logging.warning("Memory agent unreachable while reserving GPU for %s: %s", agent, exc)
        return 503, {"error": "memory agent unavailable"}

    if response.headers.get("content-type", "").startswith("application/json"):
        body: Dict[str, Any] = response.json()
    else:  # pragma: no cover - defensive
        body = {"message": response.text.strip()}

    return response.status_code, body


async def _release_with_memory_agent(agent: str, reservation_id: Optional[str]) -> None:
    payload = {
        "agent": agent,
        "reservation_id": reservation_id,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(f"{MEMORY_AGENT_URL}/gpu/release", json=payload)
    except Exception as exc:
        logging.debug("Memory agent unreachable during GPU release for %s: %s", agent, exc)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")


@mcp.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading

    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")


@mcp.custom_route("/gpu/request", methods=["POST"])
async def request_gpu(request: Request):
    REQUESTS.inc()
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON payload"}, status_code=400)

    agent = payload.get("agent")
    memory_fraction = float(payload.get("memory_fraction", 0.0))
    min_memory_mb = int(payload.get("min_memory_mb", 0))

    if not agent:
        return JSONResponse({"error": "agent field is required"}, status_code=422)

    async with SESSION_LOCK:
        existing = GPU_SESSIONS.get(agent)
        if existing:
            return JSONResponse(existing)

        status, body = await _reserve_with_memory_agent(agent, memory_fraction, min_memory_mb)
        if status == 200:
            body.setdefault("reservation_id", str(uuid.uuid4()))
            body["agent"] = agent
            GPU_SESSIONS[agent] = body
            logging.info(
                "Allocated GPU reservation for %s (device=%s).",
                agent,
                body.get("device", "cuda"),
            )
            return JSONResponse(body)

        if status == 409:
            return JSONResponse(body, status_code=409)

        return JSONResponse(body, status_code=status or 500)


@mcp.custom_route("/gpu/release", methods=["POST"])
async def release_gpu(request: Request):
    REQUESTS.inc()
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON payload"}, status_code=400)

    agent = payload.get("agent")
    if not agent:
        return JSONResponse({"error": "agent field is required"}, status_code=422)

    reservation_id = payload.get("reservation_id")

    async with SESSION_LOCK:
        session = GPU_SESSIONS.pop(agent, None)

    if session is None:
        return JSONResponse({"status": "ok", "message": "no active reservation"})

    await _release_with_memory_agent(agent, reservation_id or session.get("reservation_id"))
    logging.info("Released GPU reservation for %s", agent)
    return JSONResponse({"status": "released", "agent": agent})


@mcp.tool()
def orchestrate_workflow() -> dict:
    """Manage and trigger agent workflows."""
    return {
        "status": "ok",
        "message": "Workflow orchestration placeholder. GPU coordination endpoints available.",
    }


if __name__ == "__main__":
    # Prefer config file for port, fallback to env var, then default
    config_port = None
    try:
        with open("config.json") as handle:
            config = json.load(handle)
            config_port = int(config.get("port", 9508))
    except Exception:
        pass

    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9508))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9608)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
