"""
Convert the latest NinjaTrader CSV export in MyTradingJournal/
into CS_ALGOTRADER_APP/journal_data.js so the dashboard auto-loads it.

Usage:
    python generate_journal_data.py
    python generate_journal_data.py --csv "path/to/file.csv"
"""

import argparse
import csv
import json
import os
import re
from datetime import datetime
from pathlib import Path


def parse_pnl(value: str) -> float:
    if not value:
        return 0.0
    v = value.replace("$", "").replace(",", "").strip()
    if v.startswith("(") and v.endswith(")"):
        return -float(v[1:-1])
    try:
        return float(v)
    except ValueError:
        return 0.0


def load_csv(path: str) -> list[dict]:
    trades = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            num = row.get("Trade number", "").strip()
            if not num or not num.isdigit():
                continue
            trades.append({
                "num":        int(num),
                "instrument": row.get("Instrument", "").strip(),
                "pos":        row.get("Market pos.", "").strip(),
                "qty":        int(row.get("Qty", "1") or 1),
                "entryPrice": float(row.get("Entry price", "0") or 0),
                "exitPrice":  float(row.get("Exit price", "0") or 0),
                "entryTime":  row.get("Entry time", "").strip(),
                "exitTime":   row.get("Exit time", "").strip(),
                "entryName":  row.get("Entry name", "").strip(),
                "exitName":   row.get("Exit name", "").strip(),
                "profit":     parse_pnl(row.get("Profit", "")),
                "cumPnl":     parse_pnl(row.get("Cum. net profit", "")),
                "mae":        parse_pnl(row.get("MAE", "")),
                "mfe":        parse_pnl(row.get("MFE", "")),
            })
    return trades


def find_latest_csv(folder: str) -> str | None:
    csvs = sorted(Path(folder).glob("*.csv"), key=os.path.getmtime, reverse=True)
    return str(csvs[0]) if csvs else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=None, help="Path to NinjaTrader CSV")
    args = parser.parse_args()

    journal_dir = Path(__file__).parent / "MyTradingJournal"
    output_path = Path(__file__).parent / "CS_ALGOTRADER_APP" / "journal_data.js"

    csv_path = args.csv or find_latest_csv(str(journal_dir))
    if not csv_path or not Path(csv_path).exists():
        print("No CSV found. Place NinjaTrader export in MyTradingJournal/ or pass --csv.")
        return

    trades = load_csv(csv_path)
    if not trades:
        print("No trades parsed from CSV.")
        return

    data = {
        "source":       Path(csv_path).name,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "trades":       trades,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("window.JOURNAL_DATA = ")
        json.dump(data, f)
        f.write(";")

    print(f"Parsed {len(trades)} trades from: {Path(csv_path).name}")
    print(f"journal_data.js saved -> {output_path}")


if __name__ == "__main__":
    main()
