"""Classification logic — pure functions, no I/O."""
import unicodedata
from datetime import date


def _norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).lower()


_HUY_KW = ("hủy", "huỷ")

KHOONG_KQ = {_norm("Không có kết quả"), _norm("Chưa có kết quả")}
HUY_KQ    = {_norm("Yêu cầu hủy"), _norm("Đã chuyển IT hủy")}

_KO_NGHE_KW = frozenset([
    "không nghe máy", "k nghe máy", "ko nghe máy",
    "ngắt kết nối", "mất kết nối", "ngắt máy", "tắt máy", "cúp máy",
    "tắt cuộc gọi", "không phản hồi", "không trả lời",
])

_THAT_BAI_KW = _KO_NGHE_KW | frozenset([
    "không có kết quả", "chưa có kết quả",
    "hỗ trợ", "không cần", "không còn nhu cầu", "đã được giải đáp",
])

_LOI_THU_PHI_EMAIL_KW = frozenset([
    "lỗi thu phí", "loi thu phi", "thu phí sai", "thu phí lỗi",
    "trừ phí sai", "trừ tiền sai", "lỗi phí",
])


def _has_huy(text: str) -> bool:
    return any(kw in text for kw in _HUY_KW)


def _is_ko_nghe(nd: str, kq: str) -> bool:
    return any(kw in nd for kw in _KO_NGHE_KW) or any(kw in kq for kw in _KO_NGHE_KW)


def _is_da_ho_tro(nd: str, kq: str) -> bool:
    return ("hỗ trợ" in nd or "không cần" in nd or "đã được giải đáp" in nd
            or "hỗ trợ" in kq or "không cần" in kq)


def _is_chua_du_tt(nd: str) -> bool:
    return ("chưa đủ thông tin" in nd or "thông tin chưa đủ" in nd
            or "thiếu thông tin" in nd or "chưa cung cấp" in nd
            or "không cung cấp đủ" in nd)


def _is_goi_nham(nd: str, kq: str) -> bool:
    return "nhầm tổng đài" in nd or "gọi nhầm" in nd or "nhầm tổng đài" in kq


def _is_that_bai(nd: str, kq: str) -> bool:
    return any(kw in nd for kw in _THAT_BAI_KW) or any(kw in kq for kw in _THAT_BAI_KW)


def _classify(row: dict) -> str:
    lkn = _norm(row["loai_kn"])
    nd  = _norm(row["noi_dung"])
    kq  = _norm(row["ket_qua"])

    is_email_mb = _norm(row.get("loai", "")) == "email mb"
    is_litex = not is_email_mb and _norm(row.get("loai", "")) != "dvkh mb247"

    if "bồi thường" in lkn or (is_email_mb and "bồi thường" in nd):
        return "boi_thuong"

    if (is_litex and "loi_thu_phi" in lkn) or (
        is_email_mb and any(kw in nd for kw in _LOI_THU_PHI_EMAIL_KW)
    ):
        return "loi_thu_phi"

    if _has_huy(lkn) or _has_huy(nd) or _has_huy(kq):
        return "huy"
    if ("tư vấn" in lkn or "tìm hiểu" in lkn
            or "tư vấn" in kq or "tư vấn" in nd
            or "xác nhận" in nd):
        return "tu_van"
    return "khac"


def detect_email_product(content: str, keywords: list[tuple[str, str]]) -> str:
    cn = _norm(content)
    for kw, product in keywords:
        if _norm(kw) in cn:
            return product
    return "Khác"
