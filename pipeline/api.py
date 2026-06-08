"""Fetch KH active count from Orders API with MotherDuck cache fallback."""
from __future__ import annotations

import http.cookiejar
import json
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone, timedelta
from typing import Callable


def fetch_kh_active(
    product_name: str,
    base_url: str,
    username: str,
    password: str,
    product_api_filters: dict[str, dict],
    product_start_dates: dict[str, date],
    cache_loader: Callable[[], dict[str, int]],
    cache_saver: Callable[[str, int], None],
    lifetime_start_ts: int = 1745082000,  # 2025-04-20 00:00 UTC+7
) -> int:
    """Return total KH active orders for *product_name*.

    Falls back to MotherDuck cache on network failure. Returns 0 for products
    not in product_api_filters (e.g. 'Khác').
    """
    if product_name not in product_api_filters:
        return 0

    filters         = product_api_filters[product_name]
    sub_order_types = filters.get("sub_order_types", [])
    partner_codes   = filters.get("partner_codes", [])

    product_start = product_start_dates.get(product_name)
    if product_start:
        start_ts = int(datetime(
            product_start.year, product_start.month, product_start.day,
            tzinfo=timezone(timedelta(hours=7)),
        ).timestamp())
    else:
        start_ts = lifetime_start_ts

    jar    = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    login_req = urllib.request.Request(
        f"{base_url}/api/auth/login",
        data=json.dumps({"username": username, "password": password}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(login_req, timeout=10) as resp:
            resp.read()
    except Exception as exc:
        cached = cache_loader().get(product_name)
        if cached is not None:
            return cached
        raise RuntimeError(f"Orders login failed: {exc}") from exc

    stats_req = urllib.request.Request(
        f"{base_url}/api/report/order-statistics",
        data=json.dumps({
            "ctime": {"start_date": start_ts, "end_date": int(time.time())},
            "granularity": 2,
            "sub_order_types": sub_order_types,
            "partner_codes":   partner_codes,
            "draft_stuck_threshold_hours": 24,
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with opener.open(stats_req, timeout=10) as resp:
            data = json.loads(resp.read())
        value = int(data["total_created"])
        cache_saver(product_name, value)
        return value
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:500]
        cached = cache_loader().get(product_name)
        if cached is not None:
            return cached
        raise RuntimeError(f"Orders API HTTP {exc.code}: {body}") from exc
    except Exception as exc:
        cached = cache_loader().get(product_name)
        if cached is not None:
            return cached
        raise RuntimeError(f"Orders API failed and no cache: {exc}") from exc
