"""Page 1 — Upload CSKH and MB_Email Excel files to MotherDuck."""
import streamlit as st

from pipeline.db import upsert_cskh_rows, upsert_mb_email_rows, get_row_counts, get_date_range
from pipeline.parser import parse_cskh_bytes, parse_mb_email_bytes

st.title("Tải dữ liệu lên MotherDuck")

# ── Default product normalize map (editable) ──────────────────────────────────
_DEFAULT_NORMALIZE = """mat_tien_mb: Mất Tiền MB Đền
roi_vo_vds: Rơi Vỡ VDS
hong_man_hinh_mb: Hỏng màn hình MB sửa"""

_DEFAULT_EMAIL_KEYWORDS = """mất tiền mb đền: Mất Tiền MB Đền
rơi vỡ vds: Rơi Vỡ VDS"""

with st.expander("Cấu hình sản phẩm (nâng cao)", expanded=False):
    normalize_raw = st.text_area(
        "Product normalize (key: Tên sản phẩm)",
        value=_DEFAULT_NORMALIZE,
        height=120,
    )
    keywords_raw = st.text_area(
        "Email keywords (từ khóa: Tên sản phẩm)",
        value=_DEFAULT_EMAIL_KEYWORDS,
        height=100,
    )


def _parse_kv(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def _parse_kv_list(text: str) -> list[tuple[str, str]]:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if ":" in line:
            k, _, v = line.partition(":")
            out.append((k.strip(), v.strip()))
    return out


product_normalize = _parse_kv(normalize_raw)
product_keywords  = _parse_kv_list(keywords_raw)

st.divider()

# ── File uploaders ─────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)

with col1:
    st.subheader("File CSKH (DanhSachSuVu)")
    cskh_files = st.file_uploader(
        "Chọn file CSKH (.xlsx)", type="xlsx", accept_multiple_files=True,
        key="cskh_upload",
    )

with col2:
    st.subheader("File MB Email")
    email_files = st.file_uploader(
        "Chọn file MB Email (.xlsx)", type="xlsx", accept_multiple_files=True,
        key="email_upload",
    )

st.divider()

if st.button("Tải lên MotherDuck", type="primary", disabled=not (cskh_files or email_files)):
    total_cskh  = 0
    total_email = 0

    with st.status("Đang xử lý...", expanded=True) as status:
        for f in (cskh_files or []):
            st.write(f"Đọc CSKH: **{f.name}**")
            try:
                rows = parse_cskh_bytes(f.read(), f.name, product_normalize)
                n = upsert_cskh_rows(rows)
                st.write(f"  → {n} rows đã upsert")
                total_cskh += n
            except Exception as exc:
                st.error(f"Lỗi khi xử lý {f.name}: {exc}")

        for f in (email_files or []):
            st.write(f"Đọc MB Email: **{f.name}**")
            try:
                rows = parse_mb_email_bytes(f.read(), f.name, product_keywords)
                n = upsert_mb_email_rows(rows)
                st.write(f"  → {n} rows đã upsert")
                total_email += n
            except Exception as exc:
                st.error(f"Lỗi khi xử lý {f.name}: {exc}")

        status.update(
            label=f"Hoàn thành — CSKH: {total_cskh} rows, Email: {total_email} rows",
            state="complete",
        )

# ── Current DB stats ───────────────────────────────────────────────────────────
st.divider()
st.subheader("Dữ liệu hiện có trong MotherDuck")

try:
    counts    = get_row_counts()
    dr        = get_date_range()
    col_a, col_b, col_c = st.columns(3)
    col_a.metric("cskh_raw",     f"{counts['cskh_raw']:,} rows")
    col_b.metric("mb_email_raw", f"{counts['mb_email_raw']:,} rows")
    if dr:
        col_c.metric("Date range", f"{dr[0].strftime('%d/%m/%Y')} – {dr[1].strftime('%d/%m/%Y')}")
    else:
        col_c.metric("Date range", "Chưa có dữ liệu")
except Exception as exc:
    st.warning(f"Không thể kết nối MotherDuck: {exc}")
