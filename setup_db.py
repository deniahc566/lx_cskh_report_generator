"""One-time DDL: create MotherDuck tables in mb_data database.

Usage:
    python setup_db.py <motherduck_token>
"""
import sys
import duckdb

TOKEN = sys.argv[1] if len(sys.argv) > 1 else input("MotherDuck token: ").strip()

conn = duckdb.connect(f"md:mb_data?motherduck_token={TOKEN}")

conn.execute("""
    CREATE TABLE IF NOT EXISTS cskh_raw (
        id          VARCHAR PRIMARY KEY,
        ma_phieu    VARCHAR,
        source_file VARCHAR,
        format      VARCHAR,
        event_date  DATE NOT NULL,
        loai        VARCHAR,
        loai_kn     VARCHAR,
        noi_dung    VARCHAR,
        ket_qua     VARCHAR,
        product     VARCHAR,
        uploaded_at TIMESTAMP DEFAULT now()
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS mb_email_raw (
        ticket_id   VARCHAR PRIMARY KEY,
        source_file VARCHAR,
        event_date  DATE NOT NULL,
        content     VARCHAR,
        product     VARCHAR,
        uploaded_at TIMESTAMP DEFAULT now()
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS kh_active_cache (
        product_name VARCHAR PRIMARY KEY,
        kh_active    INTEGER NOT NULL,
        fetched_at   TIMESTAMP DEFAULT now()
    )
""")

conn.close()
print("Tables created (or already exist): cskh_raw, mb_email_raw, kh_active_cache")
