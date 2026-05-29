"""MotherDuck I/O — connect, upsert, fetch."""
from __future__ import annotations

from datetime import date, datetime

import duckdb
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
    inserted = 0
    for r in rows:
        conn.execute(
            """
            INSERT OR REPLACE INTO cskh_raw
                (id, ma_phieu, source_file, format, event_date,
                 loai, loai_kn, noi_dung, ket_qua, product, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, now())
            """,
            [
                r["id"], r.get("ma_phieu"), r["source_file"], r["format"],
                r["event_date"], r["loai"], r["loai_kn"],
                r["noi_dung"], r["ket_qua"], r["product"],
            ],
        )
        inserted += 1
    return inserted


def upsert_mb_email_rows(rows: list[dict]) -> int:
    if not rows:
        return 0
    conn = get_conn()
    inserted = 0
    for r in rows:
        conn.execute(
            """
            INSERT OR REPLACE INTO mb_email_raw
                (ticket_id, source_file, event_date, content, product, uploaded_at)
            VALUES (?, ?, ?, ?, ?, now())
            """,
            [r["ticket_id"], r["source_file"], r["event_date"], r["content"], r["product"]],
        )
        inserted += 1
    return inserted


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
        SELECT id, event_date, loai, loai_kn, noi_dung, ket_qua, product
        FROM cskh_raw
        {where}
        ORDER BY event_date
    """
    res = conn.execute(sql, params).fetchall()
    cols = ["id", "event_date", "loai", "loai_kn", "noi_dung", "ket_qua", "product"]
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
