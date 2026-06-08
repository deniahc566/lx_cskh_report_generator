"""Page 2 — Generate and download CSKH Excel reports."""
from __future__ import annotations

import io
import zipfile
from collections import defaultdict
from datetime import date, timedelta

import streamlit as st

from pipeline.api import fetch_kh_active
from pipeline.calc import PRODUCT_START_DATES, VALID_DATE_RANGE
from pipeline.db import (
    fetch_cskh_rows, fetch_mb_email_rows,
    get_date_range, load_kh_active_cache, save_kh_active_cache,
)
from pipeline.reclassify import apply_mb_reclassification
from pipeline.report_mb import build_report_mb
from pipeline.report_real import build_report_real

PRODUCT_API_FILTERS: dict[str, dict] = {
    "Mất Tiền MB Đền":       {"sub_order_types": [3], "partner_codes": ["MB"]},
    "Rơi Vỡ VDS":            {"sub_order_types": [4], "partner_codes": ["VDS"]},
    "Hỏng màn hình MB sửa": {"sub_order_types": [4], "partner_codes": ["MB"]},
}

st.title("Tạo báo cáo CSKH")

# ── Date range ────────────────────────────────────────────────────────────────
dr = get_date_range()
default_from = dr[0] if dr else VALID_DATE_RANGE[0]
default_to   = dr[1] if dr else date.today()

col1, col2 = st.columns(2)
with col1:
    date_from = st.date_input("Từ ngày", value=default_from)
with col2:
    date_to = st.date_input("Đến ngày", value=default_to)

# ── Report type ────────────────────────────────────────────────────────────────
report_type = st.radio(
    "Loại báo cáo",
    ["Báo cáo LiteX", "Báo cáo MB (reclassified)", "Cả hai"],
    horizontal=True,
)

# ── KH active override ────────────────────────────────────────────────────────
with st.expander("KH active override (để trống = gọi API + cache)", expanded=False):
    st.caption("Nhập số thủ công cho từng sản phẩm nếu API không khả dụng.")
    overrides: dict[str, int] = {}
    for pname in PRODUCT_API_FILTERS:
        val = st.number_input(pname, min_value=0, value=0, step=1, key=f"kha_{pname}")
        if val > 0:
            overrides[pname] = val

st.divider()

if st.button("Tạo báo cáo", type="primary"):
    with st.status("Đang tạo báo cáo...", expanded=True) as status:
        # ── Fetch rows ────────────────────────────────────────────────────────
        st.write("Đang tải dữ liệu từ MotherDuck...")
        cskh_rows  = fetch_cskh_rows(date_from, date_to)
        email_rows = fetch_mb_email_rows(date_from, date_to)
        all_rows   = cskh_rows + email_rows

        # Dedup by id
        seen, deduped = set(), []
        for r in all_rows:
            if r["id"] not in seen:
                seen.add(r["id"])
                deduped.append(r)
        st.write(f"  {len(deduped)} rows sau dedup ({len(all_rows) - len(deduped)} trùng)")

        if not deduped:
            status.update(label="Không có dữ liệu trong khoảng thời gian này.", state="error")
            st.stop()

        # ── Group by product ──────────────────────────────────────────────────
        products: dict[str, list] = defaultdict(list)
        for r in deduped:
            products[r["product"]].append(r)
        products = dict(products)
        st.write(f"  Sản phẩm: {list(products.keys())}")

        # ── KH active ─────────────────────────────────────────────────────────
        st.write("Đang lấy số KH active...")
        base_url = st.secrets.get("orders_base_url", "")
        username = st.secrets.get("orders_username", "")
        password = st.secrets.get("orders_password", "")

        kh_active_by_product: dict[str, int] = {}
        for pname in products:
            if pname in overrides:
                kh_active_by_product[pname] = overrides[pname]
                st.write(f"  [{pname}] KH active (override): {overrides[pname]:,}")
            else:
                try:
                    val = fetch_kh_active(
                        product_name=pname,
                        base_url=base_url,
                        username=username,
                        password=password,
                        product_api_filters=PRODUCT_API_FILTERS,
                        product_start_dates=PRODUCT_START_DATES,
                        cache_loader=load_kh_active_cache,
                        cache_saver=save_kh_active_cache,
                    )
                    kh_active_by_product[pname] = val
                    st.write(f"  [{pname}] KH active: {val:,}")
                except Exception as exc:
                    st.warning(f"  [{pname}] Không lấy được KH active: {exc}. Dùng 0.")
                    kh_active_by_product[pname] = 0

        # ── Build reports ─────────────────────────────────────────────────────
        report_bytes_real = None
        report_bytes_mb   = None

        if report_type in ("Báo cáo LiteX", "Cả hai"):
            st.write("Đang tạo báo cáo thật...")
            report_bytes_real = build_report_real(products, kh_active_by_product)

        if report_type in ("Báo cáo MB (reclassified)", "Cả hai"):
            st.write("Đang reclassify và tạo báo cáo MB...")
            mb_products: dict[str, list] = {}
            for pname, rows in products.items():
                mb_products[pname] = apply_mb_reclassification(rows)
            report_bytes_mb = build_report_mb(mb_products, kh_active_by_product)

        status.update(label="Hoàn thành!", state="complete")

    # ── Download buttons ──────────────────────────────────────────────────────
    st.success("Báo cáo đã sẵn sàng để tải về.")
    d0 = date_from.strftime("%d%m")
    d1 = date_to.strftime("%d%m_%Y")

    if report_bytes_real and report_bytes_mb:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(f"BC_CSKH_{d0}_{d1}.xlsx", report_bytes_real)
            zf.writestr(f"BC_CSKH_mb_{d0}_{d1}.xlsx", report_bytes_mb)
        st.download_button(
            label="Tải cả hai báo cáo (.zip)",
            data=buf.getvalue(),
            file_name=f"BC_CSKH_{d0}_{d1}.zip",
            mime="application/zip",
        )
    elif report_bytes_real:
        st.download_button(
            label="Tải Báo cáo Thật (.xlsx)",
            data=report_bytes_real,
            file_name=f"BC_CSKH_{d0}_{d1}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif report_bytes_mb:
        st.download_button(
            label="Tải Báo cáo MB (.xlsx)",
            data=report_bytes_mb,
            file_name=f"BC_CSKH_mb_{d0}_{d1}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
