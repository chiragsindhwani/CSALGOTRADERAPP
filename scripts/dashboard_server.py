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
    """Fetch live SPY options data from TWS/IBKR market data."""
    try:
        from iron_condor_0dte.ibkr_client import IBKRClient
        from iron_condor_0dte.config import Config
        from datetime import datetime
        import yfinance as yf
        from ib_insync import Option
        import math

        # Helper to safely convert to int (handles NaN)
        def safe_int(val):
            if val is None or val == '' or (isinstance(val, float) and math.isnan(val)):
                return 0
            try:
                return int(val)
            except (ValueError, TypeError):
                return 0

        # Helper to safely convert to float (handles NaN)
        def safe_float(val):
            if val is None or val == '':
                return 0.0
            try:
                f = float(val)
                return 0.0 if math.isnan(f) else f
            except (ValueError, TypeError):
                return 0.0

        # Connect to IBKR via TWS
        cfg = Config()

        try:
            client = IBKRClient(
                host=cfg.IBKR_HOST,
                port=7497,  # TWS Paper Trading port
                client_id=100,  # Unique client ID for dashboard
                account_id=cfg.IBKR_ACCOUNT_ID,
                paper=cfg.PAPER_TRADE
            )
        except Exception as conn_err:
            # If TWS not available, fall back to yfinance
            print(f"Warning: TWS connection failed: {conn_err}, falling back to yfinance")
            client = None

        # Get SPY current quote
        spy_price = None
        if client:
            try:
                spy_quote = client.get_quote("SPY")
                spy_price = spy_quote.get("last", 0) or spy_quote.get("bid", 0)
            except Exception as e:
                print(f"Warning: Failed to get SPY quote from TWS: {e}")

        # Fallback to yfinance for SPY price if needed
        if not spy_price:
            try:
                spy = yf.Ticker("SPY")
                spy_info = spy.info
                spy_price = spy_info.get("currentPrice", 0) or spy_info.get("regularMarketPrice", 0)
            except:
                spy_price = 0

        if not spy_price:
            return {"error": "Cannot fetch SPY price", "timestamp": datetime.now().isoformat()}

        # Get options chain structure from yfinance
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            spy = yf.Ticker("SPY")
            expirations = spy.options
            target_exp = today
            exp_to_use = target_exp if target_exp in expirations else (expirations[0] if expirations else None)

            opts = spy.option_chain(exp_to_use)
            calls_df = opts.calls
            puts_df = opts.puts

            if calls_df.empty or puts_df.empty:
                return {"error": f"No options available for {exp_to_use}", "timestamp": datetime.now().isoformat()}

            all_strikes = sorted(set(calls_df["strike"].tolist() + puts_df["strike"].tolist()))

        except Exception as e:
            return {"error": f"Failed to get options chain: {str(e)}", "timestamp": datetime.now().isoformat()}

        # Build options list
        options_list = []
        for strike in all_strikes:
            call_row = calls_df[calls_df["strike"] == strike].iloc[0] if strike in calls_df["strike"].values else None
            put_row = puts_df[puts_df["strike"] == strike].iloc[0] if strike in puts_df["strike"].values else None

            strike_data = {"strike": float(strike)}

            # Try to get live data from TWS, fallback to yfinance data
            if client and abs(strike - spy_price) <= 20:  # Only request nearby strikes from TWS
                try:
                    exp_yyyymmdd = exp_to_use.replace("-", "")
                    call_contract = Option("SPY", exp_yyyymmdd, strike, "CALL", "SMART")
                    put_contract = Option("SPY", exp_yyyymmdd, strike, "PUT", "SMART")

                    client.ib.qualifyContracts(call_contract, put_contract)
                    call_ticker = client.ib.reqMktData(call_contract, "100,101,104,106,107,165,221", False, False)
                    put_ticker = client.ib.reqMktData(put_contract, "100,101,104,106,107,165,221", False, False)

                    client.ib.sleep(0.1)

                    strike_data["call"] = {
                        "last": safe_float(call_ticker.last) or (call_row.get("lastPrice") if call_row is not None else 0),
                        "bid": safe_float(call_ticker.bid) or (call_row.get("bid") if call_row is not None else 0),
                        "ask": safe_float(call_ticker.ask) or (call_row.get("ask") if call_row is not None else 0),
                        "volume": safe_int(call_ticker.volume) or safe_int(call_row.get("volume") if call_row is not None else 0),
                        "openInterest": safe_int(call_ticker.openInterest) or safe_int(call_row.get("openInterest") if call_row is not None else 0),
                        "iv": safe_float(call_ticker.impliedVolatility) or (call_row.get("impliedVolatility") if call_row is not None else 0),
                        "delta": safe_float(call_ticker.delta) or (call_row.get("delta") if call_row is not None else 0),
                        "gamma": safe_float(call_ticker.gamma) or (call_row.get("gamma") if call_row is not None else 0),
                        "theta": safe_float(call_ticker.theta) or (call_row.get("theta") if call_row is not None else 0),
                        "vega": safe_float(call_ticker.vega) or (call_row.get("vega") if call_row is not None else 0),
                    }

                    strike_data["put"] = {
                        "last": safe_float(put_ticker.last) or (put_row.get("lastPrice") if put_row is not None else 0),
                        "bid": safe_float(put_ticker.bid) or (put_row.get("bid") if put_row is not None else 0),
                        "ask": safe_float(put_ticker.ask) or (put_row.get("ask") if put_row is not None else 0),
                        "volume": safe_int(put_ticker.volume) or safe_int(put_row.get("volume") if put_row is not None else 0),
                        "openInterest": safe_int(put_ticker.openInterest) or safe_int(put_row.get("openInterest") if put_row is not None else 0),
                        "iv": safe_float(put_ticker.impliedVolatility) or (put_row.get("impliedVolatility") if put_row is not None else 0),
                        "delta": safe_float(put_ticker.delta) or (put_row.get("delta") if put_row is not None else 0),
                        "gamma": safe_float(put_ticker.gamma) or (put_row.get("gamma") if put_row is not None else 0),
                        "theta": safe_float(put_ticker.theta) or (put_row.get("theta") if put_row is not None else 0),
                        "vega": safe_float(put_ticker.vega) or (put_row.get("vega") if put_row is not None else 0),
                    }
                except Exception as e:
                    # Fallback to yfinance data
                    if call_row is not None:
                        strike_data["call"] = {
                            "last": safe_float(call_row.get("lastPrice", 0)),
                            "bid": safe_float(call_row.get("bid", 0)),
                            "ask": safe_float(call_row.get("ask", 0)),
                            "volume": safe_int(call_row.get("volume", 0)),
                            "openInterest": safe_int(call_row.get("openInterest", 0)),
                            "iv": safe_float(call_row.get("impliedVolatility", 0)),
                            "delta": safe_float(call_row.get("delta", 0)),
                            "gamma": safe_float(call_row.get("gamma", 0)),
                            "theta": safe_float(call_row.get("theta", 0)),
                            "vega": safe_float(call_row.get("vega", 0)),
                        }
                    if put_row is not None:
                        strike_data["put"] = {
                            "last": safe_float(put_row.get("lastPrice", 0)),
                            "bid": safe_float(put_row.get("bid", 0)),
                            "ask": safe_float(put_row.get("ask", 0)),
                            "volume": safe_int(put_row.get("volume", 0)),
                            "openInterest": safe_int(put_row.get("openInterest", 0)),
                            "iv": safe_float(put_row.get("impliedVolatility", 0)),
                            "delta": safe_float(put_row.get("delta", 0)),
                            "gamma": safe_float(put_row.get("gamma", 0)),
                            "theta": safe_float(put_row.get("theta", 0)),
                            "vega": safe_float(put_row.get("vega", 0)),
                        }
            else:
                # Use yfinance data
                if call_row is not None:
                    strike_data["call"] = {
                        "last": safe_float(call_row.get("lastPrice", 0)),
                        "bid": safe_float(call_row.get("bid", 0)),
                        "ask": safe_float(call_row.get("ask", 0)),
                        "volume": safe_int(call_row.get("volume", 0)),
                        "openInterest": safe_int(call_row.get("openInterest", 0)),
                        "iv": safe_float(call_row.get("impliedVolatility", 0)),
                        "delta": safe_float(call_row.get("delta", 0)),
                        "gamma": safe_float(call_row.get("gamma", 0)),
                        "theta": safe_float(call_row.get("theta", 0)),
                        "vega": safe_float(call_row.get("vega", 0)),
                    }
                if put_row is not None:
                    strike_data["put"] = {
                        "last": safe_float(put_row.get("lastPrice", 0)),
                        "bid": safe_float(put_row.get("bid", 0)),
                        "ask": safe_float(put_row.get("ask", 0)),
                        "volume": safe_int(put_row.get("volume", 0)),
                        "openInterest": safe_int(put_row.get("openInterest", 0)),
                        "iv": safe_float(put_row.get("impliedVolatility", 0)),
                        "delta": safe_float(put_row.get("delta", 0)),
                        "gamma": safe_float(put_row.get("gamma", 0)),
                        "theta": safe_float(put_row.get("theta", 0)),
                        "vega": safe_float(put_row.get("vega", 0)),
                    }

            options_list.append(strike_data)

        # Disconnect from TWS if connected
        if client:
            try:
                client.disconnect()
            except:
                pass

        timestamp = datetime.now().isoformat()
        return {
            "timestamp": timestamp,
            "spy_price": safe_float(spy_price) if spy_price else 0.0,
            "options": options_list,
            "strike_count": len(options_list),
            "expiration": exp_to_use,
            "source": "TWS + yfinance hybrid"
        }

    except Exception as e:
        return {"error": f"Options data unavailable: {str(e)}", "timestamp": datetime.now().isoformat()}


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
