"""In-memory reclassification (replaces create_mb_data.py disk I/O)."""
from pipeline.classify import _norm, _has_huy, _is_ko_nghe, _is_da_ho_tro, _is_goi_nham, _is_that_bai, _LOI_THU_PHI_EMAIL_KW


def _classify_raw(loai_kn: str, noi_dung: str, ket_qua: str, loai: str = "") -> str:
    lkn = _norm(loai_kn)
    nd  = _norm(noi_dung)
    kq  = _norm(ket_qua)
    is_email_mb = _norm(loai) == "email mb"
    is_litex = not is_email_mb and _norm(loai) != "dvkh mb247"

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


def _should_reclassify(loai_kn: str, noi_dung: str, ket_qua: str, loai: str = "") -> bool:
    if _classify_raw(loai_kn, noi_dung, ket_qua, loai) != "khac":
        return False
    nd = _norm(noi_dung)
    kq = _norm(ket_qua)
    return _is_ko_nghe(nd, kq) or _is_da_ho_tro(nd, kq) or _is_goi_nham(nd, kq)


def _should_clean_goi_ra(loai: str, loai_kn: str, noi_dung: str, ket_qua: str) -> bool:
    if _norm(loai) != "gọi ra":
        return False
    if _classify_raw(loai_kn, noi_dung, ket_qua) != "tu_van":
        return False
    return _is_that_bai(_norm(noi_dung), _norm(ket_qua))


def apply_mb_reclassification(rows: list[dict]) -> list[dict]:
    """In-memory equivalent of create_mb_data.main(). Returns new list, does not mutate input."""
    out = []
    for r in rows:
        r2 = dict(r)
        lkn = r2.get("loai_kn", "")
        nd  = r2.get("noi_dung", "")
        kq  = r2.get("ket_qua", "")
        loai = r2.get("loai", "")

        if _should_reclassify(lkn, nd, kq, loai):
            r2["loai_kn"] = "Tư vấn/thao tác"
            lkn = "Tư vấn/thao tác"

        if _should_clean_goi_ra(loai, lkn, nd, kq):
            r2["noi_dung"] = "Khách hàng Tư vấn/thao tác"
            r2["ket_qua"]  = "KH tiếp tục sử dụng"

        out.append(r2)
    return out
