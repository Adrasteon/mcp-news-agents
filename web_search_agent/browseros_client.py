import time
import json
import logging
from typing import Any, Dict, Optional
import os
import requests

logger = logging.getLogger(__name__)


class KlavisClient:
    """Minimal Klavis call-tool adapter.

    Uses environment variable KLAVIS_API_KEY for Authorization.
    Wraps the /mcp-server/call-tool endpoint and normalizes responses.
    """

    DEFAULT_BASE = os.environ.get('KLAVIS_BASE_URL', 'https://api.klavis.ai')

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: int = 15):
        self.api_key = api_key or os.environ.get('KLAVIS_API_KEY')
        self.base_url = (base_url or self.DEFAULT_BASE).rstrip('/')
        self.timeout = timeout

    def call_tool(self, server_url: str, tool_name: str, tool_args: Dict[str, Any], connection_type: str = 'StreamableHttp') -> Dict[str, Any]:
        url = f"{self.base_url}/mcp-server/call-tool"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers['Authorization'] = f"Bearer {self.api_key}"

        payload = {
            "serverUrl": server_url,
            "toolName": tool_name,
            "toolArgs": tool_args or {},
            "connectionType": connection_type
        }

        last_exc = None
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                try:
                    body = resp.json()
                except ValueError:
                    return {"success": False, "error": "Non-JSON response", "raw": resp.text}

                # Normalize Klavis response shape
                if isinstance(body, dict) and body.get('success'):
                    result = body.get('result') or {}
                    return {
                        "success": True,
                        "content": result.get('content'),
                        "isError": result.get('isError', False),
                        "raw": body
                    }
                else:
                    return {"success": False, "error": body.get('error') if isinstance(body, dict) else 'unknown', "raw": body}

            except Exception as e:
                last_exc = e
                logger.warning(f"Klavis call-tool POST failed (attempt {attempt+1}/3): {e}")
                time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Klavis call-tool failed: {last_exc}")


class BrowserOSClient:
    """BrowserOS MCP client with optional Klavis adapter.

    If you set use_klavis=True (default), calls will be made via Klavis /mcp-server/call-tool
    using the KLAVIS_API_KEY from environment. Direct MCP HTTP calls are still available
    by setting use_klavis=False and providing a base_url that points to the BrowserOS MCP.
    """

    def __init__(self, base_url: str = "http://127.0.0.1:9225/mcp", timeout: int = 10, use_klavis: bool = False):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.use_klavis = use_klavis
        self.klavis = KlavisClient(timeout=timeout) if use_klavis else None

    def _post(self, path: str, payload: Dict[str, Any], retries: int = 2) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/') }"
        last_exc = None
        headers = {"Content-Type": "application/json"}
        for attempt in range(retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                try:
                    return resp.json()
                except ValueError:
                    # Non-JSON response
                    return {"status": "ok", "raw": resp.text}
            except Exception as e:
                last_exc = e
                logger.warning(f"POST {url} failed (attempt {attempt+1}/{retries+1}): {e}")
                time.sleep(0.5 * (attempt + 1))

        raise RuntimeError(f"Failed to POST to {url}: {last_exc}")

    def call_tool(self, tool_name: str, tool_args: Dict[str, Any], connection_type: str = 'StreamableHttp') -> Dict[str, Any]:
        """Call a BrowserOS tool via Klavis or direct MCP.

        When using Klavis, tool_name and tool_args are passed through. When using direct MCP,
        this will POST to /call-tool on the local MCP if available (best-effort).
        """
        if self.use_klavis:
            # Use the Klavis gateway. Provide our BrowserOS MCP URL as serverUrl so Klavis can proxy.
            try:
                return self.klavis.call_tool(self.base_url, tool_name, tool_args, connection_type=connection_type)
            except Exception:
                # Reraise to let caller handle fallback
                raise
        else:
            # Try direct POST to local MCP endpoint: /call-tool (convention used by some MCP gateways)
            payload = {"tool": tool_name, "args": tool_args}
            return self._post("call-tool", payload)

    def send_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Send a single browser action. For Klavis, map to a tool call named 'browser_action'."""
        return self.call_tool("browser_action", action)

    def send_plan(self, plan: Any) -> Dict[str, Any]:
        """Send a plan as a single tool call named 'browser_plan' for servers that support bulk plans."""
        return self.call_tool("browser_plan", {"plan": plan})

    def get_screenshot(self, session_id: str) -> Optional[bytes]:
        """Attempt to fetch screenshot directly from local MCP artifact endpoint.

        If using Klavis, the preferred pattern is to request a screenshot via a tool call instead.
        """
        if self.use_klavis:
            # Ask Klavis to call a tool that returns a screenshot artifact (tool dependent)
            try:
                res = self.call_tool("get_screenshot", {"session_id": session_id})
                if isinstance(res, dict) and res.get('content'):
                    # Klavis wraps content as a list; return first item bytes if available
                    content = res.get('content')
                    if isinstance(content, list) and content:
                        return content[0].encode('utf-8') if isinstance(content[0], str) else content[0]
                return None
            except Exception as e:
                logger.debug(f"Failed to fetch screenshot via Klavis for session {session_id}: {e}")
                return None
        else:
            url = f"{self.base_url}/artifact/{session_id}/screenshot"
            try:
                resp = requests.get(url, timeout=self.timeout)
                resp.raise_for_status()
                return resp.content
            except Exception as e:
                logger.debug(f"Failed to fetch screenshot for session {session_id}: {e}")
                return None
