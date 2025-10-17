import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import socket


class _State:
    # shared state for transient failure simulation
    transient_fail_next = False
    call_count = 0


class MockMCPHandler(BaseHTTPRequestHandler):
    def _read_json(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length) if length else b''
        if not raw:
            return {}
        try:
            return json.loads(raw.decode('utf-8'))
        except Exception:
            return {}

    def _send_json(self, obj, status=200):
        data = json.dumps(obj).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        _State.call_count += 1
        payload = self._read_json()

        # Simulate transient failure if payload contains simulate_transient=True
        if payload.get('simulate_transient'):
            if _State.transient_fail_next:
                # Return 500 first time then flip flag
                _State.transient_fail_next = False
                self._send_json({"error": "transient"}, status=500)
                return

        # Klavis-style call-tool
        if self.path.endswith('/mcp-server/call-tool') or self.path.endswith('/mcp/call-tool'):
            # Respond with Klavis shaped success
            resp = {"success": True, "result": {"content": ["ok"], "isError": False}, "error": None}
            self._send_json(resp)
            return

        # Direct MCP action
        if self.path.endswith('/action'):
            # Echo back action
            resp = {"status": "ok", "echo": payload}
            self._send_json(resp)
            return

        # Direct MCP plan
        if self.path.endswith('/plan'):
            plan = payload.get('plan')
            executed = []
            if isinstance(plan, list):
                for a in plan:
                    executed.append({"action": a, "result": {"success": True}})
            resp = {"status": "ok", "executed": len(executed), "outputs": executed}
            self._send_json(resp)
            return

        # Default: not found
        self._send_json({"error": "not found"}, status=404)


def start_mock_mcp_server(host='127.0.0.1'):
    # bind to an ephemeral port
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((host, 0))
    addr, port = sock.getsockname()
    sock.close()

    server = HTTPServer((host, port), MockMCPHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Reset transient flag default
    _State.transient_fail_next = True
    return server, port


def stop_mock_mcp_server(server: HTTPServer):
    try:
        server.shutdown()
        server.server_close()
    except Exception:
        pass
