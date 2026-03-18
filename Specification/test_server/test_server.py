#!/usr/bin/env python3
"""
PDM V2 — Phase 1 Local Test Server
===================================
Simple HTTP server for Phase 1 throughput testing.

Endpoints:
  GET  /ping          → 200 OK, confirms server reachable
  POST /upload        → 200 OK, logs payload size + throughput
  GET  /results       → Returns JSON summary of all received uploads

Usage:
  python test_server.py

Server listens on 0.0.0.0:5000 (all interfaces).
Find your PC's IP address and use that in the firmware sketch.

Windows: ipconfig → look for IPv4 Address on your network adapter
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import time
import datetime

# ── Config ──────────────────────────────────────────────────────────────────
PORT = 5000
upload_log = []  # In-memory log of all received uploads


# ── Request Handler ──────────────────────────────────────────────────────────
class TestServerHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        """Override to add timestamps to console output."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] {format % args}")

    def do_GET(self):
        if self.path == "/ping":
            self._send_response(200, "pong")
            print(f"  → PING from {self.client_address[0]}")

        elif self.path == "/results":
            body = json.dumps(upload_log, indent=2)
            self._send_response(200, body, content_type="application/json")

        else:
            self._send_response(404, "Not Found")

    def do_POST(self):
        if self.path == "/upload":
            content_length = int(self.headers.get("Content-Length", 0))
            start_time = time.time()
            body = self.rfile.read(content_length)
            elapsed_ms = (time.time() - start_time) * 1000

            received_bytes = len(body)
            received_kb = received_bytes / 1024.0
            throughput_kbs = received_kb / (elapsed_ms / 1000.0) if elapsed_ms > 0 else 0

            record = {
                "timestamp": datetime.datetime.now().isoformat(),
                "client_ip": self.client_address[0],
                "received_bytes": received_bytes,
                "received_kb": round(received_kb, 2),
                "transfer_time_ms": round(elapsed_ms, 1),
                "throughput_kbs": round(throughput_kbs, 1),
            }
            upload_log.append(record)

            print(f"  → UPLOAD received:")
            print(f"     Size:       {received_kb:.1f} KB ({received_bytes} bytes)")
            print(f"     Time:       {elapsed_ms:.1f} ms")
            print(f"     Throughput: {throughput_kbs:.1f} KB/s")
            print(f"     From:       {self.client_address[0]}")

            response = json.dumps({
                "status": "ok",
                "received_bytes": received_bytes,
                "throughput_kbs": round(throughput_kbs, 1)
            })
            self._send_response(200, response, content_type="application/json")

        else:
            self._send_response(404, "Not Found")

    def _send_response(self, code, body, content_type="text/plain"):
        encoded = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


# ── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import socket

    # Print local IP addresses to help user configure firmware
    hostname = socket.gethostname()
    try:
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        local_ip = "unknown"

    print("=" * 55)
    print(" PDM V2 — Phase 1 Test Server")
    print("=" * 55)
    print(f" Listening on:  0.0.0.0:{PORT}")
    print(f" Hostname:      {hostname}")
    print(f" Local IP:      {local_ip}")
    print()
    print(" Endpoints:")
    print(f"   GET  http://<your-ip>:{PORT}/ping")
    print(f"   POST http://<your-ip>:{PORT}/upload")
    print(f"   GET  http://<your-ip>:{PORT}/results")
    print()
    print(" Use 'ipconfig' (Windows) to find your PC's IP address.")
    print(" Enter that IP in the firmware sketch.")
    print("=" * 55)
    print()

    server = HTTPServer(("0.0.0.0", PORT), TestServerHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
        if upload_log:
            print(f"\nSession summary: {len(upload_log)} upload(s) received")
            for r in upload_log:
                print(f"  {r['timestamp']}  {r['received_kb']:.1f} KB  {r['throughput_kbs']:.1f} KB/s")
