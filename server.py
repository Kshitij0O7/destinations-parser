"""HTTP wrapper so the pipeline can run as a Cloudflare Container.

Cloudflare's Container class proxies requests to a port, so the container has
to be a server rather than a script that exits. That also means Ollama stays
resident between requests, saving the ~17s model load each time.

    GET  /health                                 -> 200
    POST /process  {"url": "...", "city": "..."} -> 202, runs in background

Uses only the standard library: no framework, no extra dependency.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from main import process

PORT = 8080


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        else:
            self._respond(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/process":
            self._respond(404, {"error": "not found"})
            return

        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._respond(400, {"error": "invalid json"})
            return

        url = body.get("url")
        if not url:
            self._respond(400, {"error": "url is required"})
            return

        # The pipeline takes minutes, far longer than a caller should hold a
        # connection open, so acknowledge now and work in the background.
        threading.Thread(
            target=self._run,
            args=(url, body.get("city")),
            daemon=True,
        ).start()
        self._respond(202, {"status": "processing", "url": url})

    @staticmethod
    def _run(url, city):
        try:
            key = process(url, city)
            print(f"done: {key or 'FAILED'}  <- {url}")
        except Exception as e:
            # A thread that raises would die silently, so log it here.
            print(f"error processing {url}: {e}")

    def _respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} {fmt % args}")


if __name__ == "__main__":
    print(f"listening on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
