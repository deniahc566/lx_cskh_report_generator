"""Metric calculation — pure functions, no I/O."""
import sys
from collections import defaultdict
from datetime import date

from pipeline.classify import (
    _norm, _classify, KHOONG_KQ, HUY_KQ,
    _is_ko_nghe, _is_da_ho_tro, _is_chua_du_tt, _is_goi_nham,
)

VALID_DATE_RANGE = (date(2026, 4, 22), date.max)

HARDCODED_METRICS_REAL = {
    date(2026, 5, 2): {
        "total": 199, "mb_total": 0, "mb_call": 0, "mb_email": 0, "mb_fanpage": 0,
        "litex_total": 199, "litex_goi_vao": 78, "litex_goi_ra": 121,
        "litex_kh_ko_tl": 85, "litex_email": 0, "litex_fanpage": 0,
        "tu_van": 1, "huy": 121, "so_huy": 65, "so_tiep_tuc": 41,
        "so_chua_kq": 15, "so_chua_kq_ko_nghe": 1, "so_chua_kq_da_ho_tro": 0,
        "so_chua_kq_tt": 9, "so_chua_kq_khac": 5,
        "khac": 77, "khac_ko_nghe": 73, "khac_da_ho_tro": 4,
        "khac_goi_nham": 0, "khac_khac": 0, "boi_thuong": 0,
    },
}

HARDCODED_METRICS_MB = {
    date(2026, 5, 2): {
        "total": 199, "mb_total": 0, "mb_call": 0, "mb_email": 0, "mb_fanpage": 0,
        "litex_total": 199, "litex_call": 199, "litex_email": 0, "litex_fanpage": 0,
        "tu_van": 78, "huy": 121, "so_huy": 65, "so_tiep_tuc": 41,
        "so_chua_kq": 15, "khac": 0, "boi_thuong": 0,
    },
}

PRODUCT_START_DATES: dict[str, date] = {
    "Hỏng màn hình MB sửa": date(2026, 5, 22),
}

DATE_GROUPS = [
    (date(2026, 4, 22), date(2026, 4, 29), "22-29/04"),
]


def _count_boi_thuong(rows: list[dict], seen: set | None = None) -> int:
    if seen is None:
        seen = set()
    count = 0
    for r in rows:
        if _classify(r) != "boi_thuong":
            continue
        name = _norm(r.get("ten_kh", "")).strip()
        if name:
            if name in seen:
                continue
            seen.add(name)
        count += 1
    return count


def _is_thai_do_gay_gat(n: str) -> bool:
    return "gay_gat" in n or "gây gắt" in n or "không hài lòng" in n or "khong hai long" in n


def _is_thai_do_binh_thuong(n: str) -> bool:
    return n == "" or "binh_thuong" in n or "bình thường" in n


def _is_thai_do_hai_long(n: str) -> bool:
    return "hai_long" in n or "hài lòng" in n


def calc_real(rows: list[dict], seen_bt: set | None = None) -> dict:
    mb    = [r for r in rows if r["loai"] in ("DVKH MB247", "Email MB")]
    litex = [r for r in rows if r["loai"] not in ("DVKH MB247", "Email MB")]

    goi_ra   = [r for r in litex if r["loai"] == "Gọi ra"]
    kh_ko_tl = [r for r in goi_ra if _norm(r["ket_qua"]) in KHOONG_KQ]

    huy_rows   = [r for r in rows if _classify(r) == "huy"]
    so_huy     = sum(1 for r in huy_rows if _norm(r["ket_qua"]) in HUY_KQ)
    so_tt      = sum(1 for r in huy_rows if _norm(r["ket_qua"]) == _norm("KH tiếp tục sử dụng"))
    kq_rows    = [r for r in huy_rows if _norm(r["ket_qua"]) in KHOONG_KQ]
    so_chua_kq = len(kq_rows)
    khac_rows  = [r for r in rows if _classify(r) == "khac"]

    unclassified = [r for r in litex if r["loai"] not in ("Gọi vào", "Gọi ra", "Email LiteX")]
    if unclassified:
        vals = {r["loai"].encode("ascii", "replace").decode() for r in unclassified}
        print(f"[DEBUG] LiteX unclassified ({len(unclassified)} rows): {vals}")

    return {
        "total":             len(rows),
        "mb_total":          len(mb),
        "mb_call":           sum(1 for r in mb if r["loai"] == "DVKH MB247"),
        "mb_email":          sum(1 for r in mb if r["loai"] == "Email MB"),
        "mb_fanpage":        0,
        "litex_total":       len(litex),
        "litex_goi_vao":     sum(1 for r in litex if r["loai"] == "Gọi vào"),
        "litex_goi_ra":      len(goi_ra),
        "litex_kh_ko_tl":    len(kh_ko_tl),
        "litex_email":       sum(1 for r in litex if r["loai"] == "Email LiteX"),
        "litex_fanpage":     sum(1 for r in litex if r["loai"] == "Mạng xã hội"),
        "tu_van":            sum(1 for r in rows if _classify(r) == "tu_van"),
        "huy":               len(huy_rows),
        "so_huy":            so_huy,
        "so_tiep_tuc":       so_tt,
        "so_chua_kq":        so_chua_kq,
        "so_chua_kq_ko_nghe":    sum(1 for r in kq_rows if _is_ko_nghe(_norm(r["noi_dung"]), _norm(r["ket_qua"]))),
        "so_chua_kq_da_ho_tro":  sum(1 for r in kq_rows if _is_da_ho_tro(_norm(r["noi_dung"]), _norm(r["ket_qua"]))),
        "so_chua_kq_tt":         sum(1 for r in kq_rows if _is_chua_du_tt(_norm(r["noi_dung"]))),
        "so_chua_kq_khac":       sum(1 for r in kq_rows if not (
            _is_ko_nghe(_norm(r["noi_dung"]), _norm(r["ket_qua"])) or
            _is_da_ho_tro(_norm(r["noi_dung"]), _norm(r["ket_qua"])) or
            _is_chua_du_tt(_norm(r["noi_dung"])))),
        "khac":              len(khac_rows),
        "khac_ko_nghe":      sum(1 for r in khac_rows if _is_ko_nghe(_norm(r["noi_dung"]), _norm(r["ket_qua"]))),
        "khac_da_ho_tro":    sum(1 for r in khac_rows if _is_da_ho_tro(_norm(r["noi_dung"]), _norm(r["ket_qua"]))),
        "khac_goi_nham":     sum(1 for r in khac_rows if _is_goi_nham(_norm(r["noi_dung"]), _norm(r["ket_qua"]))),
        "khac_khac":         sum(1 for r in khac_rows if not (
            _is_ko_nghe(_norm(r["noi_dung"]), _norm(r["ket_qua"])) or
            _is_da_ho_tro(_norm(r["noi_dung"]), _norm(r["ket_qua"])) or
            _is_goi_nham(_norm(r["noi_dung"]), _norm(r["ket_qua"])))),
        "boi_thuong":        _count_boi_thuong(rows, seen_bt),
        "loi_thu_phi":       sum(1 for r in rows if _classify(r) == "loi_thu_phi"),
        "thai_do_gay_gat":   sum(1 for r in rows if _is_thai_do_gay_gat(_norm(r.get("thai_do", "")))),
        "thai_do_binh_thuong": sum(1 for r in rows if _is_thai_do_binh_thuong(_norm(r.get("thai_do", "")))),
        "thai_do_hai_long":  sum(1 for r in rows if _is_thai_do_hai_long(_norm(r.get("thai_do", "")))),
    }


def calc_mb(rows: list[dict], seen_bt: set | None = None) -> dict:
    mb    = [r for r in rows if r["loai"] in ("DVKH MB247", "Email MB")]
    litex = [r for r in rows if r["loai"] not in ("DVKH MB247", "Email MB")]

    huy_rows   = [r for r in rows if _classify(r) == "huy"]
    so_huy     = sum(1 for r in huy_rows if _norm(r["ket_qua"]) in HUY_KQ)
    so_tt      = sum(1 for r in huy_rows if _norm(r["ket_qua"]) == _norm("KH tiếp tục sử dụng"))
    so_chua_kq = sum(1 for r in huy_rows if _norm(r["ket_qua"]) in KHOONG_KQ)

    return {
        "total":         len(rows),
        "mb_total":      len(mb),
        "mb_call":       sum(1 for r in mb if r["loai"] == "DVKH MB247"),
        "mb_email":      sum(1 for r in mb if r["loai"] == "Email MB"),
        "mb_fanpage":    0,
        "litex_total":   len(litex),
        "litex_call":    sum(1 for r in litex if r["loai"] in ("Gọi vào", "Gọi ra")),
        "litex_email":   sum(1 for r in litex if r["loai"] == "Email LiteX"),
        "litex_fanpage": sum(1 for r in litex if r["loai"] == "Mạng xã hội"),
        "tu_van":        sum(1 for r in rows if _classify(r) == "tu_van"),
        "huy":           len(huy_rows),
        "so_huy":        so_huy,
        "so_tiep_tuc":   so_tt,
        "so_chua_kq":    so_chua_kq,
        "khac":          sum(1 for r in rows if _classify(r) == "khac"),
        "boi_thuong":    _count_boi_thuong(rows, seen_bt),
        "loi_thu_phi":   sum(1 for r in rows if _classify(r) == "loi_thu_phi"),
        "thai_do_gay_gat":    sum(1 for r in rows if _is_thai_do_gay_gat(_norm(r.get("thai_do", "")))),
        "thai_do_binh_thuong": sum(1 for r in rows if _is_thai_do_binh_thuong(_norm(r.get("thai_do", "")))),
        "thai_do_hai_long":   sum(1 for r in rows if _is_thai_do_hai_long(_norm(r.get("thai_do", "")))),
    }


def _build_columns(all_dates: list[date], metrics_by_date: dict) -> list[tuple[str, dict]]:
    used = set()
    cols = []
    for d in all_dates:
        if d in used:
            continue
        group = next((g for g in DATE_GROUPS if g[0] <= d <= g[1]), None)
        if group:
            start, end, label = group
            group_dates = [x for x in all_dates if start <= x <= end]
            keys   = metrics_by_date[group_dates[0]].keys()
            merged = {k: sum(metrics_by_date[x].get(k) or 0 for x in group_dates) for k in keys}
            cols.append((label, merged))
            used.update(group_dates)
        else:
            fmt = d.strftime("%-d/%m/%Y") if sys.platform != "win32" else d.strftime("%#d/%m/%Y")
            cols.append((fmt, metrics_by_date[d]))
            used.add(d)
    return cols
