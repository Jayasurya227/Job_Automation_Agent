import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

VITE_PORT = 5173
BACKEND_PORT = 8000
BRIDGE_PORT = 5174

class BridgeHandler(BaseHTTPRequestHandler):
    """
    HTTP Bridge for Port 5174:
    - Automatically redirects browser page visits to the native Vite port 5173
    - Proxies /api/* and /output/* directly to FastAPI backend on port 8000
    - Proxies other direct requests to Vite on port 5173
    Prevents raw socket connection resets on mobile browsers.
    """

    def log_message(self, format, *args):
        # Suppress noisy logs
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def _handle_request(self):
        client_host = self.headers.get("Host", "").split(":")[0] or "127.0.0.1"

        # If it's a root or HTML page visit from a browser, redirect seamlessly to :5173
        accept_header = self.headers.get("Accept", "")
        if self.path == "/" or ("text/html" in accept_header and not self.path.startswith("/api")):
            target_redirect = f"http://{client_host}:{VITE_PORT}{self.path}"
            self.send_response(302)
            self.send_header("Location", target_redirect)
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            return

        # Direct API or static call: proxy to Backend (8000) or Vite (5173)
        if self.path.startswith("/api") or self.path.startswith("/output"):
            target_url = f"http://127.0.0.1:{BACKEND_PORT}{self.path}"
        else:
            target_url = f"http://127.0.0.1:{VITE_PORT}{self.path}"

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        req_headers = {k: v for k, v in self.headers.items() if k.lower() not in ["host", "content-length"]}

        try:
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=req_headers,
                method=self.command
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                self.send_response(resp.status)
                for key, val in resp.headers.items():
                    if key.lower() not in ["transfer-encoding", "content-length", "connection"]:
                        self.send_header(key, val)
                self.send_header("Access-Control-Allow-Origin", "*")
                data = resp.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            err_data = e.read()
            self.send_header("Content-Length", str(len(err_data)))
            self.end_headers()
            self.wfile.write(err_data)
        except Exception as e:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error": "Bridge error: {str(e)}"}}'.encode("utf-8"))

    def do_GET(self):
        self._handle_request()

    def do_POST(self):
        self._handle_request()

    def do_PUT(self):
        self._handle_request()

    def do_DELETE(self):
        self._handle_request()

def run_server():
    server_address = ("0.0.0.0", BRIDGE_PORT)
    httpd = HTTPServer(server_address, BridgeHandler)
    print(f"HTTP Bridge active on http://0.0.0.0:{BRIDGE_PORT} -> forwarding to {VITE_PORT}/{BACKEND_PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()

if __name__ == "__main__":
    run_server()
