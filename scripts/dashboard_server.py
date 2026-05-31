#!/usr/bin/env python3
"""Dashboard HTTP server — serves static files + broker toggle API."""
import http.server
import json
import os
from pathlib import Path

ROOT          = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
ENV_FILE      = ROOT / ".env"
PORT          = 8888


def _read_env_var(key: str, default: str = "") -> str:
    """Read a single variable from .env file."""
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return default


def _write_env_var(key: str, value: str) -> None:
    """Update a single variable in .env, preserving all other content."""
    if not ENV_FILE.exists():
        ENV_FILE.write_text(f"{key}={value}\n", encoding="utf-8")
        return

    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler: static files + broker API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/api/broker":
            broker = _read_env_var("BROKER", "tradier")
            self._json(200, {"broker": broker})
        else:
            super().do_GET()

    def do_POST(self):
        """Handle POST requests."""
        if self.path == "/api/set-broker":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length))
                broker = body.get("broker", "tradier").lower()

                if broker not in ("tradier", "ibkr"):
                    self._json(400, {"error": "broker must be 'tradier' or 'ibkr'"})
                    return

                _write_env_var("BROKER", broker)
                self._json(200, {"broker": broker, "ok": True})
            except Exception as e:
                self._json(500, {"error": str(e)})
        else:
            self._json(404, {"error": "not found"})

    def _json(self, code: int, data: dict) -> None:
        """Send JSON response."""
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """Suppress per-request console noise."""
        pass


if __name__ == "__main__":
    os.chdir(DASHBOARD_DIR)
    server = http.server.HTTPServer(("", PORT), DashboardHandler)
    print(f"Dashboard: http://localhost:{PORT}/tradier_dashboard.html")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
