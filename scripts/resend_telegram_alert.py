"""
Resend today's session-complete Telegram alert with corrected actual P&L.

Usage:
    python resend_telegram_alert.py

Reads:
  - .env  (TRADIER_API_TOKEN, TRADIER_ACCOUNT_ID, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
  - CS_ALGOTRADER_APP/forward_test_results.json  (today's trade record)
  - Tradier /v1/accounts/{id}/orders              (today's orders for spread details)
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET   = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parent

# ── Load .env ─────────────────────────────────────────────────────────────────
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

TOKEN      = os.getenv("TRADIER_API_TOKEN", "")
ACCOUNT_ID = os.getenv("TRADIER_ACCOUNT_ID", "")
TG_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT    = os.getenv("TELEGRAM_CHAT_ID", "")
PAPER      = os.getenv("TRADIER_PAPER_TRADE", "false").lower() == "true"
BASE_HOST  = "sandbox.tradier.com" if PAPER else "api.tradier.com"
HEADERS    = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"}

if not TOKEN or not ACCOUNT_ID:
    print("ERROR: TRADIER_API_TOKEN and TRADIER_ACCOUNT_ID must be set in .env")
    sys.exit(1)
if not TG_TOKEN or not TG_CHAT:
    print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    sys.exit(1)


# ── Tradier helpers ────────────────────────────────────────────────────────────
def _api_get(path: str) -> dict:
    conn = http.client.HTTPSConnection(BASE_HOST, timeout=15)
    conn.request("GET", path, headers=HEADERS)
    resp = conn.getresponse()
    raw  = resp.read().decode()
    conn.close()
    return json.loads(raw)


def _tg_send(message: str) -> None:
    payload = json.dumps({"chat_id": TG_CHAT, "text": message, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        resp_body = json.loads(r.read())
    if not resp_body.get("ok"):
        raise RuntimeError(f"Telegram error: {resp_body}")


# ── Fetch account profile ──────────────────────────────────────────────────────
print("Fetching account profile ...")
profile_raw  = _api_get("/v1/user/profile")
profile      = profile_raw.get("profile", {})
account_name = profile.get("name", "Unknown")
acct_obj     = profile.get("account", {})
if isinstance(acct_obj, list):
    acct_obj = next((a for a in acct_obj if a.get("account_number") == ACCOUNT_ID),
                    acct_obj[0] if acct_obj else {})
account_number = acct_obj.get("account_number", ACCOUNT_ID)
print(f"  Account : {account_number}  ({account_name})")

# ── Load today's trade from forward_test_results.json ─────────────────────────
today_iso    = datetime.now(ET).strftime("%Y-%m-%d")
results_path = ROOT / "CS_ALGOTRADER_APP" / "forward_test_results.json"
if not results_path.exists():
    print("ERROR: forward_test_results.json not found.")
    sys.exit(1)

results   = json.loads(results_path.read_text(encoding="utf-8"))
today_rec = next((r for r in results if r["date"] == today_iso), None)
if not today_rec:
    print(f"No trade record found for {today_iso} in forward_test_results.json")
    sys.exit(0)

gross_pnl      = today_rec.get("gross_pnl", 0.0)
commission     = today_rec.get("commission", 0.0)
net_pnl        = today_rec.get("pnl", gross_pnl - commission)
cumulative_pnl = today_rec.get("cumulative_pnl", 0.0)
contracts      = today_rec.get("contracts", 0)
credit_total   = today_rec.get("credit_collected", 0.0)
outcome        = today_rec.get("outcome", "exit")
print(f"  Trade   : gross=${gross_pnl:+.2f}  net=${net_pnl:+.2f}  cum=${cumulative_pnl:+.2f}")

# ── Fetch today's orders for spread details ────────────────────────────────────
print("Fetching today's orders ...")
orders_raw = _api_get(f"/v1/accounts/{ACCOUNT_ID}/orders")
ord_obj    = orders_raw.get("orders", {})
orders: list = []
if ord_obj and ord_obj != "null":
    o = ord_obj.get("order", [])
    orders = [o] if isinstance(o, dict) else (o or [])

# Find today's filled multileg SPY orders
today_orders = [
    o for o in orders
    if (o.get("create_date") or "")[:10] == today_iso
    and o.get("status") == "filled"
    and o.get("class") == "multileg"
]

# Reconstruct spread strikes from leg symbols
def _parse_strikes(order: dict) -> str:
    """Return 'P738/740 | C756/758' from a multileg order's legs."""
    legs = order.get("leg", [])
    if isinstance(legs, dict):
        legs = [legs]
    puts  = sorted(
        [int((lg.get("option_symbol") or "")[-8:]) / 1000 for lg in legs
         if "P" in (lg.get("option_symbol") or "")[-9:-7]],
    )
    calls = sorted(
        [int((lg.get("option_symbol") or "")[-8:]) / 1000 for lg in legs
         if "C" in (lg.get("option_symbol") or "")[-9:-7]],
    )
    parts = []
    if puts:  parts.append("P" + "/".join(f"{int(s)}" for s in puts))
    if calls: parts.append("C" + "/".join(f"{int(s)}" for s in calls))
    return " | ".join(parts) if parts else "—"

# Entry order = avg_fill_price < 0 (credit received)
entry_order = next((o for o in today_orders if float(o.get("avg_fill_price", 0) or 0) < 0), None)
close_order = next((o for o in today_orders if float(o.get("avg_fill_price", 0) or 0) > 0), None)

spreads_str   = _parse_strikes(entry_order) if entry_order else "—"
entry_time_str = (entry_order.get("create_date") or "")
close_time_str = (close_order.get("create_date") or "")

def _fmt_time(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(ET).strftime("%I:%M %p ET")
    except Exception:
        return iso[11:16] + " ET"

entry_time = _fmt_time(entry_time_str)
close_time = _fmt_time(close_time_str)

actual_credit_per = credit_total / (contracts * 100) if contracts > 0 else 0.0
capital_used      = (2.0 - actual_credit_per) * 100 * contracts   # $2 wing width assumed
roi               = (net_pnl / capital_used * 100) if capital_used > 0 else 0.0

# ── Format close reason ────────────────────────────────────────────────────────
label_map = {
    "profit_target": "PROFIT TARGET HIT",
    "stop_loss":     "STOP LOSS HIT",
    "force_close":   "FORCE CLOSE (3:45 PM)",
    "exit":          "POSITION CLOSED",
    "no_trade":      "NO TRADE",
}
close_label = label_map.get(outcome, outcome.replace("_", " ").upper())
emoji = "💰" if net_pnl >= 0 else "📉"

# ── Build and send the corrected alert ────────────────────────────────────────
acct_header = (
    f"👤 <b>{account_name}</b>  ·  <code>#{account_number}</code>\n"
    f"━━━━━━━━━━━━━━━━━━━\n"
)

message = (
    acct_header
    + f"{emoji} <b>SESSION COMPLETE — {today_iso}</b>  <i>[CORRECTED]</i>\n"
    + f"━━━━━━━━━━━━━━━━━━━\n"
    + f"📋 Outcome     : {close_label}\n"
    + f"📊 Spreads     : {spreads_str}\n"
    + f"⏰ Entry Time  : {entry_time}\n"
    + f"⏰ Close Time  : {close_time}\n"
    + f"━━━━━━━━━━━━━━━━━━━\n"
    + f"📦 Contracts   : {contracts}\n"
    + f"💵 Credit Rcvd : ${credit_total:.2f} total  (${actual_credit_per * 100:.2f}/contract)\n"
    + f"💰 Gross P&L   : ${gross_pnl:+.2f}\n"
    + f"🏛️ Commission  : -${commission:.2f}\n"
    + f"✅ Net P&L     : ${net_pnl:+.2f}\n"
    + f"📊 ROI on Risk  : {roi:+.2f}%\n"
    + f"━━━━━━━━━━━━━━━━━━━\n"
    + f"📈 Cumulative Net P&L : ${cumulative_pnl:+.2f}\n"
    + f"🎯 Daily Target: $203.00  "
    + (f"✅ TARGET MET" if net_pnl >= 203 else f"⚠️ Below target")
)

print("\nSending Telegram alert ...")
print("-" * 48)
# Print a plain-text preview (strip HTML tags; encode for Windows console)
import re
preview = re.sub(r"<[^>]+>", "", message)
print(preview.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8", errors="replace"))
print("-" * 48)

try:
    _tg_send(message)
    print("\nALERT SENT SUCCESSFULLY.")
except Exception as e:
    print(f"\nFAILED TO SEND ALERT: {e}")
    sys.exit(1)
