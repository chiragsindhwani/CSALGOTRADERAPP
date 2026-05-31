"""
Trade Logger — dual-backend: CSV (local) or SQLite/PostgreSQL (AWS).

Backend selection (automatic, no config needed):
  Local machine  → trades/trade_log.csv
  AWS EC2        → trades/trades.db  (SQLite, or PostgreSQL if DATABASE_URL is set)

Auto-detection:
  Tries the EC2 instance-metadata endpoint (169.254.169.254). If it responds
  within 0.5 s the process is on EC2 → DB backend is chosen.
  Explicit override: set DEPLOYMENT_ENV=local | aws in .env.

DB schema (SQLite / PostgreSQL compatible):
  Table: trade_log
  Every column maps to a field in the forward-test JSON record PLUS extra
  columns captured at fill time (actual_credit, exit_cost, order IDs, etc.).

Usage in live_trader.py:
    from .trade_logger import TradeLogger
    logger = TradeLogger(root_dir=_ROOT)
    logger.log_trade(record_dict)
"""

from __future__ import annotations

import csv
import logging
import os
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Column definition (order matters for CSV header) ──────────────────────────
COLUMNS: list[str] = [
    "id",               # auto-increment (DB) / row number (CSV)
    "date",             # YYYY-MM-DD
    "logged_at",        # ISO UTC timestamp
    "environment",      # LIVE | SANDBOX
    "account_id",
    "account_name",
    "symbol",           # SPY
    "strategy",         # Iron Condor 0DTE
    "contracts",
    "long_put",
    "short_put",
    "short_call",
    "long_call",
    "wing_width",
    "entry_time",       # HH:MM ET
    "exit_time",        # HH:MM ET
    "outcome",          # profit_target | stop_loss | force_close | aborted | no_fill | no_trade
    "entry_order_id",
    "exit_order_id",
    "entry_credit",     # per-share actual fill (abs value)
    "bs_credit",        # per-share Black-Scholes estimate
    "exit_cost",        # per-share actual close fill (abs value)
    "gross_pnl",
    "commission",
    "net_pnl",
    "cumulative_pnl",
    "vix_sigma",        # decimal e.g. 0.163
    "spy_price_entry",
    "notes",
]

# Columns used in CREATE TABLE (excludes "id" which is auto-generated)
_DB_COLS = [c for c in COLUMNS if c != "id"]

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS trade_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL,
    logged_at       TEXT NOT NULL,
    environment     TEXT,
    account_id      TEXT,
    account_name    TEXT,
    symbol          TEXT DEFAULT 'SPY',
    strategy        TEXT DEFAULT 'Iron Condor 0DTE',
    contracts       INTEGER,
    long_put        REAL,
    short_put       REAL,
    short_call      REAL,
    long_call       REAL,
    wing_width      REAL,
    entry_time      TEXT,
    exit_time       TEXT,
    outcome         TEXT,
    entry_order_id  TEXT,
    exit_order_id   TEXT,
    entry_credit    REAL,
    bs_credit       REAL,
    exit_cost       REAL,
    gross_pnl       REAL,
    commission      REAL,
    net_pnl         REAL,
    cumulative_pnl  REAL,
    vix_sigma       REAL,
    spy_price_entry REAL,
    notes           TEXT
);
"""

# ── Environment detection ──────────────────────────────────────────────────────

def _detect_env() -> str:
    """
    Return 'aws' if running on EC2, 'local' otherwise.

    Checks (in order):
      1. DEPLOYMENT_ENV env var (local | aws | ec2 | prod)
      2. EC2 instance-metadata endpoint reachability (0.5 s timeout)
    """
    explicit = os.getenv("DEPLOYMENT_ENV", "").strip().lower()
    if explicit in ("aws", "ec2", "prod", "production"):
        return "aws"
    if explicit in ("local", "dev", "development"):
        return "local"
    # Auto-detect via EC2 IMDS
    try:
        urllib.request.urlopen(
            "http://169.254.169.254/latest/meta-data/", timeout=0.5
        )
        return "aws"
    except Exception:
        return "local"


# ── TradeLogger ───────────────────────────────────────────────────────────────

class TradeLogger:
    """
    Logs one trade record per call to log_trade().

    On local  → appends a row to  <root>/trades/trade_log.csv
    On AWS    → inserts a row into <root>/trades/trades.db  (SQLite)
                or the PostgreSQL DB at DATABASE_URL if that env var is set.
    """

    def __init__(self, root_dir: Path | str | None = None):
        self.root_dir  = Path(root_dir) if root_dir else Path(__file__).resolve().parent.parent
        self.trades_dir = self.root_dir / "trades"
        self.trades_dir.mkdir(exist_ok=True)

        self.env       = _detect_env()
        self.csv_path  = self.trades_dir / "trade_log.csv"
        self.db_path   = self.trades_dir / "trades.db"
        self.db_url    = os.getenv("DATABASE_URL", "")   # PostgreSQL override

        if self.env == "aws":
            self._init_db()
            log.info("TradeLogger: AWS mode -> %s",
                     self.db_url or str(self.db_path))
        else:
            self._init_csv()
            log.info("TradeLogger: LOCAL mode -> %s", self.csv_path)

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_csv(self) -> None:
        """Create CSV with header row if it does not already exist."""
        if not self.csv_path.exists():
            with self.csv_path.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=COLUMNS)
                writer.writeheader()
            log.info("TradeLogger: created %s", self.csv_path)

    def _init_db(self) -> None:
        """Create SQLite DB (or PostgreSQL table) with trade_log schema."""
        if self.db_url:
            self._pg_execute(_CREATE_SQL.replace(
                "INTEGER PRIMARY KEY AUTOINCREMENT",
                "SERIAL PRIMARY KEY",         # PostgreSQL syntax
            ))
        else:
            with sqlite3.connect(self.db_path) as con:
                con.execute(_CREATE_SQL)
                con.commit()
        log.info("TradeLogger: trade_log table ready")

    # ── Public API ────────────────────────────────────────────────────────────

    def log_trade(self, record: dict[str, Any]) -> None:
        """
        Persist one trade record.

        Required keys (others are optional / filled with None):
          date, outcome, gross_pnl, commission, net_pnl, cumulative_pnl, contracts

        Extra keys recognised (captured from position / close info):
          account_id, account_name, environment,
          long_put, short_put, short_call, long_call, wing_width,
          entry_time, exit_time, entry_order_id, exit_order_id,
          entry_credit, bs_credit, exit_cost,
          vix_sigma, spy_price_entry, notes
        """
        row = self._build_row(record)
        try:
            if self.env == "aws":
                self._write_db(row)
            else:
                self._write_csv(row)
            log.info("TradeLogger: logged trade %s | %s | net=$%.2f",
                     row["date"], row["outcome"], row["net_pnl"] or 0)
        except Exception as e:
            log.error("TradeLogger: failed to persist trade record: %s", e)

    # ── Row builder ───────────────────────────────────────────────────────────

    def _build_row(self, record: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()
        row: dict[str, Any] = {col: None for col in COLUMNS}
        row["logged_at"] = now
        row["symbol"]    = record.get("symbol", "SPY")
        row["strategy"]  = record.get("strategy", "Iron Condor 0DTE")
        for col in COLUMNS:
            if col in record:
                row[col] = record[col]
        return row

    # ── CSV backend ───────────────────────────────────────────────────────────

    def _write_csv(self, row: dict[str, Any]) -> None:
        # Assign sequential id (= current row count)
        with self.csv_path.open("r", encoding="utf-8") as f:
            # header counts as 1, so num rows = line count - 1
            row["id"] = max(sum(1 for _ in f) - 1, 0) + 1
        with self.csv_path.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
            writer.writerow(row)

    # ── SQLite backend ────────────────────────────────────────────────────────

    def _write_db(self, row: dict[str, Any]) -> None:
        if self.db_url:
            self._pg_insert(row)
            return
        cols   = _DB_COLS
        vals   = [row.get(c) for c in cols]
        ph     = ", ".join("?" * len(cols))
        sql    = f"INSERT INTO trade_log ({', '.join(cols)}) VALUES ({ph})"
        with sqlite3.connect(self.db_path) as con:
            con.execute(sql, vals)
            con.commit()

    # ── PostgreSQL backend (optional) ─────────────────────────────────────────

    def _pg_conn(self):
        try:
            import psycopg2  # type: ignore
            return psycopg2.connect(self.db_url)
        except ImportError:
            raise RuntimeError(
                "DATABASE_URL is set but psycopg2 is not installed. "
                "Run: pip install psycopg2-binary"
            )

    def _pg_execute(self, sql: str) -> None:
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    def _pg_insert(self, row: dict[str, Any]) -> None:
        cols = _DB_COLS
        vals = [row.get(c) for c in cols]
        ph   = ", ".join(["%s"] * len(cols))
        sql  = f"INSERT INTO trade_log ({', '.join(cols)}) VALUES ({ph})"
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, vals)
            conn.commit()

    # ── Read helpers (for dashboard / reporting) ──────────────────────────────

    def all_trades(self) -> list[dict[str, Any]]:
        """Return all logged trade rows as a list of dicts."""
        if self.env == "aws":
            if self.db_url:
                with self._pg_conn() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT * FROM trade_log ORDER BY date, logged_at")
                        cols = [d[0] for d in cur.description]
                        return [dict(zip(cols, row)) for row in cur.fetchall()]
            else:
                with sqlite3.connect(self.db_path) as con:
                    con.row_factory = sqlite3.Row
                    rows = con.execute(
                        "SELECT * FROM trade_log ORDER BY date, logged_at"
                    ).fetchall()
                    return [dict(r) for r in rows]
        else:
            if not self.csv_path.exists():
                return []
            with self.csv_path.open("r", encoding="utf-8") as f:
                return list(csv.DictReader(f))
