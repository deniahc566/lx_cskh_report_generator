"""
Bulk-load CSKH and MB_Email Excel files from local directories into MotherDuck.
Uses the same parsers as the Streamlit upload UI (pipeline/parser.py).
Reads MOTHERDUCK_TOKEN from ../.env

Usage:
    python load_from_local.py                 # full reload all files
    python load_from_local.py --resume        # skip files already loaded
    python load_from_local.py --cskh-dir X --mb-email-dir Y
"""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from pipeline.parser import parse_cskh_bytes, parse_mb_email_bytes

# ── Defaults ──────────────────────────────────────────────────────────────────
_CSKH_DIR     = r"D:\LiteX\MB\Data\CSKH"
_MB_EMAIL_DIR = r"D:\LiteX\MB\Data\MB_Email"

_PRODUCT_NORMALIZE = {
    "mat_tien_mb":      "Mất Tiền MB Đền",
    "roi_vo_vds":       "Rơi Vỡ VDS",
    "BH_MHDT_MBB":      "Hỏng màn hình MB sửa",
    "hong_man_hinh_mb": "Hỏng màn hình MB sửa",
}

_EMAIL_KEYWORDS = [
    ("mất tiền mb đền", "Mất Tiền MB Đền"),
    ("rơi vỡ vds",      "Rơi Vỡ VDS"),
]

_RETRY_DELAY = 15
_MAX_RETRIES = 4


# ── DB ────────────────────────────────────────────────────────────────────────
def _connect(token: str) -> duckdb.DuckDBPyConnection:
    return duckdb.connect(f"md:mb_data?motherduck_token={token}")


def _insert_df(con, table: str, df: pd.DataFrame):
    con.register("_tmp", df)
    con.execute(f"INSERT OR IGNORE INTO {table} SELECT * FROM _tmp")
    con.unregister("_tmp")


# ── Loaders ───────────────────────────────────────────────────────────────────
def _load_cskh_file(fp: Path) -> pd.DataFrame:
    rows = parse_cskh_bytes(fp.read_bytes(), fp.name, _PRODUCT_NORMALIZE)
    if not rows:
        return pd.DataFrame()
    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["uploaded_at"] = now
    if "thai_do" not in df.columns:
        df["thai_do"] = ""
    if "ten_kh" not in df.columns:
        df["ten_kh"] = ""
    return df[["id", "ma_phieu", "source_file", "format", "event_date",
               "loai", "loai_kn", "noi_dung", "ket_qua", "product", "uploaded_at", "thai_do", "ten_kh"]]


def _load_mb_email_file(fp: Path) -> pd.DataFrame:
    rows = parse_mb_email_bytes(fp.read_bytes(), fp.name, _EMAIL_KEYWORDS)
    if not rows:
        return pd.DataFrame()
    now = datetime.now(timezone.utc)
    df = pd.DataFrame(rows)
    df["uploaded_at"] = now
    return df[["ticket_id", "source_file", "event_date", "content", "product", "uploaded_at"]]


def _load_dir(
    token: str,
    table: str,
    id_col: str,
    files: list[Path],
    build_df_fn,
    resume: bool = False,
) -> tuple[duckdb.DuckDBPyConnection, int]:
    con   = _connect(token)
    total = 0

    for fp in files:
        source_file = fp.name

        if resume:
            existing = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE source_file = ?", [source_file]
            ).fetchone()[0]
            if existing > 0:
                print(f"Skipping (already loaded): {source_file} ({existing} rows)")
                total += existing
                continue

        print(f"Reading: {source_file}")
        df = build_df_fn(fp)
        if df.empty:
            print("  0 rows — skipped")
            continue
        print(f"  {len(df)} rows")

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                con.execute(f"DELETE FROM {table} WHERE source_file = ?", [source_file])
                _insert_df(con, table, df)
                break
            except duckdb.Error as exc:
                print(f"  MotherDuck error (attempt {attempt}/{_MAX_RETRIES}): {exc}")
                if attempt == _MAX_RETRIES:
                    raise
                import time
                print(f"  Reconnecting in {_RETRY_DELAY}s...")
                time.sleep(_RETRY_DELAY)
                try:
                    con.close()
                except Exception:
                    pass
                con = _connect(token)

        count = con.execute(
            f"SELECT COUNT(*) FROM {table} WHERE source_file = ?", [source_file]
        ).fetchone()[0]
        print(f"  {count} rows in {table}")
        total += count

    return con, total


# ── Main ──────────────────────────────────────────────────────────────────────
def load(cskh_dir: str, mb_email_dir: str, resume: bool = False):
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise RuntimeError("MOTHERDUCK_TOKEN not set in environment / .env")

    cskh_files = sorted(
        f for f in Path(cskh_dir).glob("*.xlsx") if not f.name.startswith("~$")
    )
    print(f"\nLoading cskh_raw: {len(cskh_files)} file(s) from {cskh_dir}")
    if resume:
        print("  (--resume: skipping files already loaded)")
    con, total_cskh = _load_dir(
        token, "cskh_raw", "id", cskh_files, _load_cskh_file, resume=resume,
    )

    mb_email_files = []
    if Path(mb_email_dir).is_dir():
        mb_email_files = sorted(
            f for f in Path(mb_email_dir).glob("*.xlsx") if not f.name.startswith("~$")
        )
    print(f"\nLoading mb_email_raw: {len(mb_email_files)} file(s) from {mb_email_dir}")
    con, total_email = _load_dir(
        token, "mb_email_raw", "ticket_id", mb_email_files, _load_mb_email_file, resume=resume,
    )

    cskh_total  = con.execute("SELECT COUNT(*) FROM cskh_raw").fetchone()[0]
    email_total = con.execute("SELECT COUNT(*) FROM mb_email_raw").fetchone()[0]
    print(f"\nDone.")
    print(f"  cskh_raw:     {total_cskh:,} rows written | {cskh_total:,} total in table")
    print(f"  mb_email_raw: {total_email:,} rows written | {email_total:,} total in table")
    con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Bulk-load local CSKH/MB_Email files into MotherDuck"
    )
    parser.add_argument("--cskh-dir",     default=_CSKH_DIR)
    parser.add_argument("--mb-email-dir", default=_MB_EMAIL_DIR)
    parser.add_argument("--resume", action="store_true",
                        help="Skip files already present in the table")
    args = parser.parse_args()
    load(args.cskh_dir, args.mb_email_dir, resume=args.resume)


if __name__ == "__main__":
    main()
