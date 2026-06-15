#!/usr/bin/env python3
"""Dashboard HTTP server — serves static files + broker toggle API + live options data."""
import http.server
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

ROOT          = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = ROOT / "dashboard"
ENV_FILE      = ROOT / ".env"
PORT          = 8888

# Add project root to path for imports
sys.path.insert(0, str(ROOT))

# Cache for live options data (to avoid hammering IBKR)
LIVE_OPTIONS_CACHE = {"data": None, "timestamp": 0}
CACHE_TTL = 60  # 60 seconds


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


def _fetch_live_spy_options():
    """Fetch live SPY options data using yfinance (fastest/most reliable for streaming)."""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta

        # Get SPY current price
        spy = yf.Ticker("SPY")
        spy_info = spy.info
        spy_price = spy_info.get("currentPrice", 0) or spy_info.get("regularMarketPrice", 0)

        if not spy_price:
            return {"error": "Cannot fetch SPY price"}

        # Get today's date for 0DTE options
        today = datetime.now().strftime("%Y-%m-%d")

        # Get options chain for 0DTE (today)
        try:
            # Try to get 0DTE options
            expirations = spy.options
            if not expirations:
                return {"error": "No options expirations available"}

            # Use today's expiration if available, otherwise use first available
            target_exp = today
            exp_to_use = target_exp if target_exp in expirations else expirations[0]

            opts = spy.option_chain(exp_to_use)
            calls_df = opts.calls
            puts_df = opts.puts

            if calls_df.empty or puts_df.empty:
                return {"error": f"No options available for expiration {exp_to_use}"}

            # Build strikes list with both calls and puts
            all_strikes = sorted(set(calls_df["strike"].tolist() + puts_df["strike"].tolist()))

            options_list = []
            for strike in all_strikes:
                call_row = calls_df[calls_df["strike"] == strike].iloc[0] if strike in calls_df["strike"].values else None
                put_row = puts_df[puts_df["strike"] == strike].iloc[0] if strike in puts_df["strike"].values else None

                strike_data = {"strike": strike}

                # Call data
                if call_row is not None:
                    strike_data["call"] = {
                        "bid": float(call_row.get("bid", 0)) if call_row.get("bid") and call_row.get("bid") > 0 else None,
                        "ask": float(call_row.get("ask", 0)) if call_row.get("ask") and call_row.get("ask") > 0 else None,
                        "iv": float(call_row.get("impliedVolatility", 0)) if call_row.get("impliedVolatility") else None,
                        "delta": float(call_row.get("delta", 0)) if call_row.get("delta") else None,
                        "gamma": float(call_row.get("gamma", 0)) if call_row.get("gamma") else None,
                        "theta": float(call_row.get("theta", 0)) if call_row.get("theta") else None,
                        "vega": float(call_row.get("vega", 0)) if call_row.get("vega") else None,
                    }

                # Put data
                if put_row is not None:
                    strike_data["put"] = {
                        "bid": float(put_row.get("bid", 0)) if put_row.get("bid") and put_row.get("bid") > 0 else None,
                        "ask": float(put_row.get("ask", 0)) if put_row.get("ask") and put_row.get("ask") > 0 else None,
                        "iv": float(put_row.get("impliedVolatility", 0)) if put_row.get("impliedVolatility") else None,
                        "delta": float(put_row.get("delta", 0)) if put_row.get("delta") else None,
                        "gamma": float(put_row.get("gamma", 0)) if put_row.get("gamma") else None,
                        "theta": float(put_row.get("theta", 0)) if put_row.get("theta") else None,
                        "vega": float(put_row.get("vega", 0)) if put_row.get("vega") else None,
                    }

                options_list.append(strike_data)

            timestamp = datetime.now().isoformat()
            return {
                "timestamp": timestamp,
                "spy_price": spy_price,
                "options": options_list,
                "strike_count": len(options_list),
                "expiration": exp_to_use
            }

        except Exception as e:
            return {"error": f"No options data: {str(e)}", "timestamp": datetime.now().isoformat()}

    except ImportError:
        return {"error": "yfinance not installed", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"error": f"Failed to fetch options: {str(e)}", "timestamp": datetime.now().isoformat()}


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """HTTP handler: static files + broker API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/api/broker":
            broker = _read_env_var("BROKER", "tradier")
            self._json(200, {"broker": broker})
        elif self.path == "/api/spy-options":
            # Check cache first
            now = time.time()
            if LIVE_OPTIONS_CACHE["data"] and (now - LIVE_OPTIONS_CACHE["timestamp"]) < CACHE_TTL:
                self._json(200, LIVE_OPTIONS_CACHE["data"])
            else:
                # Fetch fresh data
                data = _fetch_live_spy_options()
                LIVE_OPTIONS_CACHE["data"] = data
                LIVE_OPTIONS_CACHE["timestamp"] = now
                self._json(200, data)
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
