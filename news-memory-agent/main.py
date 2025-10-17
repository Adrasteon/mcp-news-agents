
# news-memory-agent: AI-driven resource manager for all agents (MCP SDK)

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from prometheus_client import start_http_server, Counter, Gauge

try:  # Optional dependency; agent degrades gracefully without torch
    import torch  # type: ignore
except Exception:  # pragma: no cover - torch not available
    torch = None


REQUESTS = Counter('requests_total', 'Total requests')
AGENT_STATUS = Gauge('agent_status', 'Status of the agent (1=up, 0=down)')
GPU_AVAILABLE = Gauge('gpu_available', 'Flag indicating GPU availability (1=available, 0=offline)')


mcp = FastMCP("news-memory-agent")

logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler()])

GPU_DEVICE = os.getenv("NEWS_GPU_DEVICE", "cuda:0")
RESERVATION_LOCK = asyncio.Lock()
ACTIVE_RESERVATION: Optional[Dict[str, Any]] = None


def _gpu_status() -> Dict[str, Any]:
    if torch is None or not torch.cuda.is_available():
        GPU_AVAILABLE.set(0)
        return {
            "cuda_available": False,
            "device": None,
            "total_memory_mb": None,
            "free_memory_mb": None,
            "timestamp": time.time(),
        }

    try:
        device_index = int(GPU_DEVICE.split(":", 1)[1]) if ":" in GPU_DEVICE else 0
        torch.cuda.set_device(device_index)
        free_bytes, total_bytes = torch.cuda.mem_get_info()
        total_memory_mb = total_bytes / (1024 * 1024)
        free_memory_mb = free_bytes / (1024 * 1024)
    except Exception as exc:  # pragma: no cover - driver quirks
        logging.warning("Unable to query GPU state: %s", exc)
        GPU_AVAILABLE.set(0)
        return {
            "cuda_available": False,
            "device": None,
            "total_memory_mb": None,
            "free_memory_mb": None,
            "timestamp": time.time(),
        }

    GPU_AVAILABLE.set(1)
    return {
        "cuda_available": True,
        "device": GPU_DEVICE,
        "total_memory_mb": total_memory_mb,
        "free_memory_mb": free_memory_mb,
        "timestamp": time.time(),
    }


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request):
    return PlainTextResponse("ok")


@mcp.custom_route("/shutdown", methods=["GET"])
async def shutdown(request: Request):
    import threading

    threading.Thread(target=lambda: sys.exit(0)).start()
    return PlainTextResponse("shutting down")


@mcp.custom_route("/gpu/status", methods=["GET"])
async def gpu_status(request: Request):
    REQUESTS.inc()
    return JSONResponse(_gpu_status())


@mcp.custom_route("/gpu/reserve", methods=["POST"])
async def gpu_reserve(request: Request):
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

    async with RESERVATION_LOCK:
        status = _gpu_status()
        if not status.get("cuda_available"):
            return JSONResponse({"error": "no GPU available"}, status_code=503)

        global ACTIVE_RESERVATION
        if ACTIVE_RESERVATION is not None:
            if ACTIVE_RESERVATION["agent"] == agent:
                return JSONResponse(ACTIVE_RESERVATION)
            return JSONResponse(
                {
                    "error": "GPU already reserved",
                    "active_agent": ACTIVE_RESERVATION["agent"],
                },
                status_code=409,
            )

        free_memory_mb = status.get("free_memory_mb") or 0.0
        total_memory_mb = status.get("total_memory_mb") or free_memory_mb
        required_mb = max(min_memory_mb, 0)
        if required_mb and free_memory_mb < required_mb:
            return JSONResponse(
                {
                    "error": "insufficient free memory",
                    "free_memory_mb": free_memory_mb,
                    "required_memory_mb": required_mb,
                },
                status_code=409,
            )

        granted_mb = None
        if memory_fraction > 0 and total_memory_mb:
            granted_mb = min(total_memory_mb * memory_fraction, free_memory_mb)

        ACTIVE_RESERVATION = {
            "agent": agent,
            "reservation_id": str(uuid.uuid4()),
            "device": status.get("device") or GPU_DEVICE,
            "granted_memory_mb": granted_mb,
            "free_memory_mb": free_memory_mb,
            "total_memory_mb": total_memory_mb,
            "timestamp": time.time(),
        }

        logging.info(
            "Reserved GPU for %s (device=%s granted=%.2fMB free=%.2fMB)",
            agent,
            ACTIVE_RESERVATION["device"],
            granted_mb or 0.0,
            free_memory_mb,
        )
        return JSONResponse(ACTIVE_RESERVATION)


@mcp.custom_route("/gpu/release", methods=["POST"])
async def gpu_release(request: Request):
    REQUESTS.inc()
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid JSON payload"}, status_code=400)

    agent = payload.get("agent")
    reservation_id = payload.get("reservation_id")

    if not agent:
        return JSONResponse({"error": "agent field is required"}, status_code=422)

    async with RESERVATION_LOCK:
        global ACTIVE_RESERVATION
        if ACTIVE_RESERVATION is None:
            return JSONResponse({"status": "ok", "message": "no active reservation"})

        if ACTIVE_RESERVATION["agent"] != agent and reservation_id != ACTIVE_RESERVATION.get("reservation_id"):
            return JSONResponse({"error": "reservation mismatch"}, status_code=409)

        logging.info("Released GPU from %s", ACTIVE_RESERVATION["agent"])
        ACTIVE_RESERVATION = None
        if torch and torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except Exception:  # pragma: no cover - cleanup best effort
                pass

        return JSONResponse({"status": "released", "agent": agent})


@mcp.tool()
def manage_resources() -> dict:
    """Report current GPU reservation state."""
    current = ACTIVE_RESERVATION.copy() if ACTIVE_RESERVATION else None
    return {
        "status": "ok",
        "gpu": _gpu_status(),
        "active_reservation": current,
    }


if __name__ == "__main__":
    # Prefer config file for port, fallback to env var, then default
    config_port = None
    try:
        with open("config.json") as handle:
            config = json.load(handle)
            config_port = int(config.get("port", 9507))
    except Exception:
        pass

    port = config_port or int(os.getenv("NEWS_AGENT_PORT", 9507))
    host = os.getenv("NEWS_AGENT_HOST", "127.0.0.1")
    mcp.settings.host = host
    mcp.settings.port = port
    start_http_server(9607)
    AGENT_STATUS.set(1)
    mcp.run(transport="streamable-http")
