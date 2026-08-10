"""One-time seed: import all CSKH Excel files from local Data folder into MotherDuck.

Usage:
    python seed_data.py [--token TOKEN] [--cskh-dir DIR] [--email-dir DIR]
"""
import sys
import os
import argparse
import duckdb

sys.path.insert(0, os.path.dirname(__file__))

from pipeline.parser import parse_cskh_bytes, parse_mb_email_bytes

PRODUCT_NORMALIZE = {
    "mat_tien_mb":             "Mất Tiền MB Đền",
    "roi_vo_vds":              "Rơi Vỡ VDS",
    "BH_MHDT_MBB":             "Hỏng màn hình MB sửa",
    "benh_ly_nghiem_trong_mbdh": "Bệnh lý nghiêm trọng MB đồng hành",
    "an_ninh_mang_bidv":         "Bảo An Tài Khoản BIDV",
    # canonical names pass-through
    "Mất Tiền MB Đền":         "Mất Tiền MB Đền",
    "Rơi Vỡ VDS":              "Rơi Vỡ VDS",
    "Hỏng màn hình MB sửa":    "Hỏng màn hình MB sửa",
    "Bệnh lý nghiêm trọng MB đồng hành": "Bệnh lý nghiêm trọng MB đồng hành",
    "Bảo An Tài Khoản BIDV":   "Bảo An Tài Khoản BIDV",
}

PRODUCT_KEYWORDS = [
    ("mất tiền mb đền",    "Mất Tiền MB Đền"),
    ("rơi vỡ vds",         "Rơi Vỡ VDS"),
    ("hỏng màn hình",      "Hỏng màn hình MB sửa"),
]


def upsert_cskh(conn, rows):
    if not rows:
        return
    params = [
        (r["id"], r.get("ma_phieu"), r["source_file"], r["format"],
         r["event_date"], r["loai"], r["loai_kn"],
         r["noi_dung"], r["ket_qua"], r["product"])
        for r in rows
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO cskh_raw
            (id, ma_phieu, source_file, format, event_date,
             loai, loai_kn, noi_dung, ket_qua, product, uploaded_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
        """,
        params,
    )


def upsert_email(conn, rows):
    if not rows:
        return
    params = [
        (r["ticket_id"], r["source_file"], r["event_date"], r["content"], r["product"])
        for r in rows
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO mb_email_raw
            (ticket_id, source_file, event_date, content, product, uploaded_at)
        VALUES (?, ?, ?, ?, ?, now())
        """,
        params,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token",     required=True)
    parser.add_argument("--cskh-dir",  default=r"D:\LiteX\CSKH_BaoCao\Data\CSKH")
    parser.add_argument("--email-dir", default=r"D:\LiteX\CSKH_BaoCao\Data\MB_Email")
    args = parser.parse_args()

    conn = duckdb.connect(f"md:mb_data?motherduck_token={args.token}")
    print("Connected to MotherDuck mb_data")

    # ── CSKH files ────────────────────────────────────────────────────────────
    cskh_files = sorted(
        os.path.join(args.cskh_dir, f)
        for f in os.listdir(args.cskh_dir)
        if f.lower().endswith(".xlsx") and not f.startswith("~$")
    ) if os.path.isdir(args.cskh_dir) else []

    total_cskh = 0
    for fp in cskh_files:
        fname = os.path.basename(fp)
        with open(fp, "rb") as fh:
            data = fh.read()
        rows = parse_cskh_bytes(data, fname, PRODUCT_NORMALIZE)
        upsert_cskh(conn, rows)
        total_cskh += len(rows)
        print(f"  CSKH {fname}: {len(rows)} rows")

    # ── MB_Email files ────────────────────────────────────────────────────────
    email_files = sorted(
        os.path.join(args.email_dir, f)
        for f in os.listdir(args.email_dir)
        if f.lower().endswith(".xlsx") and not f.startswith("~$")
    ) if os.path.isdir(args.email_dir) else []

    total_email = 0
    for fp in email_files:
        fname = os.path.basename(fp)
        with open(fp, "rb") as fh:
            data = fh.read()
        rows = parse_mb_email_bytes(data, fname, PRODUCT_KEYWORDS)
        upsert_email(conn, rows)
        total_email += len(rows)
        print(f"  MB_Email {fname}: {len(rows)} rows")

    conn.close()

    print(f"\nDone — CSKH: {total_cskh} rows, MB_Email: {total_email} rows")
    count = duckdb.connect(f"md:mb_data?motherduck_token={args.token}").execute(
        "SELECT COUNT(*) FROM cskh_raw"
    ).fetchone()[0]
    print(f"cskh_raw total in MotherDuck: {count}")


if __name__ == "__main__":
    main()
