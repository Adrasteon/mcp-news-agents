import pytest
import json

from web_search_agent.browseros_client import BrowserOSClient, KlavisClient
from web_search_agent.executor import validate_plan, execute_plan
from web_search_agent import main as web_search_main


class DummyResp:
    def __init__(self, status_code=200, json_data=None, text=''):
        self.status_code = status_code
        self._json = json_data
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("No JSON")
        return self._json


def test_post_retry_and_json(monkeypatch):
    calls = {'count': 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls['count'] += 1
        if calls['count'] == 1:
            # Simulate server error
            return DummyResp(status_code=500, json_data=None, text='error')
        return DummyResp(status_code=200, json_data={"status": "ok", "echo": json})

    monkeypatch.setattr('web_search_agent.browseros_client.requests.post', fake_post)

    client = BrowserOSClient(base_url="http://127.0.0.1:9225/mcp", timeout=1)
    res = client.send_action({"action": "goto", "value": "https://example.com"})
    assert isinstance(res, dict)
    assert res.get('status') == 'ok'
    assert 'echo' in res


def test_klavis_call_tool_and_executor(monkeypatch):
    # Monkeypatch KlavisClient.call_tool to simulate successful tool responses
    def fake_call_tool(self, server_url, tool_name, tool_args, connection_type='StreamableHttp'):
        return {"success": True, "content": ["ok"], "isError": False}

    monkeypatch.setattr(KlavisClient, 'call_tool', fake_call_tool)

    # Use BrowserOSClient with Klavis enabled
    client = BrowserOSClient(base_url="http://127.0.0.1:9225/mcp", use_klavis=True)

    # Simple plan with two actions
    plan = [
        {"action": "goto", "value": "https://example.com"},
        {"action": "extract", "selector": "article"}
    ]

    # Validate plan and execute using the exported helpers
    validated = validate_plan(plan)
    result = execute_plan(validated, client)
    assert isinstance(result, dict)
    assert result['executed'] == 2


def test_execute_plan_retries_and_artifact(monkeypatch):
    # Create a fake client that fails first, then succeeds, and provides a screenshot
    class FakeClient:
        def __init__(self):
            self.calls = 0

        def send_action(self, action):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("simulated transient failure")
            return {"success": True, "data": "ok"}

        def get_screenshot(self, session_id):
            return b"PNGDATA"

    client = FakeClient()
    plan = [{"action": "goto", "value": "https://example.com", "retries": 1, "session_id": "s1"}]
    validated = validate_plan(plan)
    res = execute_plan(validated, client)
    assert res['executed'] >= 1
    outputs = res['outputs']
    # Ensure we captured an artifact entry (base64) after the first failure
    has_artifact = any('artifact_screenshot_base64' in o for o in outputs)
    assert has_artifact


def test_integration_with_mock_mcp_server():
    from web_search_agent.tests.mock_mcp_server import start_mock_mcp_server, stop_mock_mcp_server
    server, port = start_mock_mcp_server()
    try:
        base = f"http://127.0.0.1:{port}/mcp"
        client = BrowserOSClient(base_url=base, use_klavis=False)
        plan = [{"action": "goto", "value": "https://example.com"}, {"action": "extract", "selector": "article"}]
        validated = validate_plan(plan)
        res = execute_plan(validated, client)
        assert res['executed'] == 2
    finally:
        stop_mock_mcp_server(server)


def test_integration_transient_failure_and_retry():
    from web_search_agent.tests.mock_mcp_server import start_mock_mcp_server, stop_mock_mcp_server
    server, port = start_mock_mcp_server()
    try:
        base = f"http://127.0.0.1:{port}/mcp"
        # Use the /action endpoint but instruct the mock to transiently fail by sending simulate_transient
        class TransientPlanClient(BrowserOSClient):
            def send_action(self, action):
                payload = action.copy()
                payload['simulate_transient'] = True
                return self._post('action', payload)

        client = TransientPlanClient(base_url=base, use_klavis=False)
        plan = [{"action": "goto", "value": "https://example.com", "retries": 1, "session_id": "s1"}]
        validated = validate_plan(plan)
        res = execute_plan(validated, client)
        assert res['executed'] >= 1
        # should have at least one output entry with success True after retry
        assert any(o.get('result', {}).get('success') or o.get('result', {}).get('status') == 'ok' for o in res['outputs'])
    finally:
        stop_mock_mcp_server(server)
