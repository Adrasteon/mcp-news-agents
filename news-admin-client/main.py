# news-admin-client: Administrative front-end for the news multi-agent system

import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

import os
import threading
import sys

class ShutdownHandler(HealthHandler):
    def do_GET(self):
        if self.path == "/shutdown":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"shutting down")
            threading.Thread(target=lambda: sys.exit(0)).start()
        else:
            super().do_GET()

def main():
    print("[news-admin-client] Starting News Admin Client...")
    port = int(os.getenv("NEWS_AGENT_PORT", 9510))
    server_address = ("", port)
    httpd = HTTPServer(server_address, ShutdownHandler)
    print(f"[news-admin-client] Health endpoint running at http://localhost:{port}/health")
    httpd.serve_forever()

if __name__ == "__main__":
    main()
