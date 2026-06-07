"""MotherDuck I/O — connect, upsert, fetch."""
from __future__ import annotations

from datetime import date, datetime

import duckdb
import pandas as pd
import streamlit as st


@st.cache_resource
def get_conn() -> duckdb.DuckDBPyConnection:
    token = st.secrets["motherduck_token"]
    return duckdb.connect(f"md:mb_data?motherduck_token={token}")


# ── Upsert ────────────────────────────────────────────────────────────────────

def upsert_cskh_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_conn()
    source_file = rows[0]["source_file"]
    df = pd.DataFrame(rows)
    df["uploaded_at"] = datetime.utcnow()
    if "thai_do" not in df.columns:
        df["thai_do"] = ""
    df = df[["id", "ma_phieu", "source_file", "format", "event_date",
             "loai", "loai_kn", "noi_dung", "ket_qua", "product", "uploaded_at", "thai_do"]]
    conn.execute("DELETE FROM cskh_raw WHERE source_file = ?", [source_file])
    conn.register("_tmp_cskh", df)
    conn.execute("INSERT INTO cskh_raw SELECT * FROM _tmp_cskh")
    conn.unregister("_tmp_cskh")
    return len(df)


def upsert_mb_email_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_conn()
    source_file = rows[0]["source_file"]
    df = pd.DataFrame(rows)
    df["uploaded_at"] = datetime.utcnow()
    df = df[["ticket_id", "source_file", "event_date", "content", "product", "uploaded_at"]]
    conn.execute("DELETE FROM mb_email_raw WHERE source_file = ?", [source_file])
    conn.register("_tmp_email", df)
    conn.execute("INSERT INTO mb_email_raw SELECT * FROM _tmp_email")
    conn.unregister("_tmp_email")
    return len(df)


# ── Fetch ─────────────────────────────────────────────────────────────────────

def fetch_cskh_rows(
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Return rows as dicts compatible with calc_real / calc_mb.

    Keys: event_date, loai, loai_kn, noi_dung, ket_qua, product, id
    """
    conn = get_conn()
    where, params = _date_filter(date_from, date_to, col="event_date")
    sql = f"""
        SELECT id, event_date, loai, loai_kn, noi_dung, ket_qua, product,
               COALESCE(thai_do, '') AS thai_do
        FROM cskh_raw
        {where}
        ORDER BY event_date
    """
    res = conn.execute(sql, params).fetchall()
    cols = ["id", "event_date", "loai", "loai_kn", "noi_dung", "ket_qua", "product", "thai_do"]
    return [dict(zip(cols, row)) for row in res]


def fetch_mb_email_rows(
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    """Return MB_Email rows shaped like CSKH rows (loai='Email MB', loai_kn='hủy', etc.)."""
    conn = get_conn()
    where, params = _date_filter(date_from, date_to, col="event_date")
    sql = f"""
        SELECT ticket_id, event_date, product
        FROM mb_email_raw
        {where}
        ORDER BY event_date
    """
    res = conn.execute(sql, params).fetchall()
    rows = []
    for ticket_id, event_date, product in res:
        rows.append({
            "id":         f"mb_email_{ticket_id}",
            "event_date": event_date,
            "loai":       "Email MB",
            "loai_kn":    "hủy",
            "noi_dung":   "",
            "ket_qua":    "Yêu cầu hủy",
            "product":    product,
        })
    return rows


def get_date_range() -> tuple[date, date] | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT MIN(event_date), MAX(event_date) FROM (
                SELECT event_date FROM cskh_raw
                UNION ALL
                SELECT event_date FROM mb_email_raw
            )
            """
        ).fetchone()
        if row and row[0]:
            return row[0], row[1]
    except Exception:
        pass
    return None


# ── KH active cache ───────────────────────────────────────────────────────────

def load_kh_active_cache() -> dict[str, int]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT product_name, kh_active FROM kh_active_cache"
        ).fetchall()
        return {name: val for name, val in rows}
    except Exception:
        return {}


def save_kh_active_cache(product_name: str, value: int) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT OR REPLACE INTO kh_active_cache (product_name, kh_active, fetched_at)
        VALUES (?, ?, now())
        """,
        [product_name, value],
    )


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_row_counts() -> dict[str, int]:
    conn = get_conn()
    try:
        cskh  = conn.execute("SELECT COUNT(*) FROM cskh_raw").fetchone()[0]
        email = conn.execute("SELECT COUNT(*) FROM mb_email_raw").fetchone()[0]
        return {"cskh_raw": cskh, "mb_email_raw": email}
    except Exception:
        return {"cskh_raw": 0, "mb_email_raw": 0}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _date_filter(
    date_from: date | None,
    date_to: date | None,
    col: str = "event_date",
) -> tuple[str, list]:
    clauses, params = [], []
    if date_from:
        clauses.append(f"{col} >= ?")
        params.append(date_from)
    if date_to:
        clauses.append(f"{col} <= ?")
        params.append(date_to)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params
