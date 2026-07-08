#!/usr/bin/env python3
"""Reverse Image OSINT — helpers for URL normalization, deduplication, and OSINT scoring."""
from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs, urlencode
from collections import Counter


_WEAK_PATH_TRAILERS = re.compile(
    r"^/(search|images/search|tbm|webhp|.*(cbir_page|cache|retpath|rdrnd|tmpl_version)).*",
    re.I,
)

_WEAK_QUERY_PARAMS = {"retpath", "rdrnd", "tmpl_version", "lr", "rpt", "ncrnd"}


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        host = (p.netloc or "").lower().replace("www.", "")
        if not host:
            return url
        path = re.sub(r"//+", "/", p.path or "/")
        if _WEAK_PATH_TRAILERS.match(path):
            return ""
        qs = parse_qs(p.query, keep_blank_values=False)
        cleaned = {k: v for k, v in qs.items() if k.lower() not in _WEAK_QUERY_PARAMS}
        query = "?" + urlencode(cleaned, doseq=True) if cleaned else ""
        return f"{p.scheme}://{host}{path}{query}"
    except Exception:
        return ""


OSINT_DOMAIN_SCORES = {
    "vk.com": 20,
    "ok.ru": 20,
    "userapi.com": 18,
    "tgcnt.ru": 18,
    "t.me": 18,
    "telegram.me": 18,
    "mail.ru": 14,
    "vk.link": 14,
    "vk.cc": 14,
    "youtube.com": 10,
    "instagram.com": 12,
    "facebook.com": 10,
    "twitter.com": 12,
    "x.com": 12,
    "pinterest.com": 8,
    "wamba.com": 12,
    "loveplanet.ru": 12,
    "avito.ru": 6,
    "olx.ua": 6,
    "drive.google.com": 6,
    "docs.google.com": 6,
    "yandex.ru": 4,
    "yandex.com": 4,
}


def normalize_results(urls: list[str], max_results: int = 50) -> list[str]:
    seen = set()
    out = []
    for raw in urls:
        u = _normalize_url(raw)
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= max_results:
            break
    return out


def domain_info(url: str) -> tuple[str, str, int]:
    try:
        host = urlparse(url).netloc.lower().replace("www.", "")
        score = OSINT_DOMAIN_SCORES.get(host, 1)
        return host, host, score
    except Exception:
        return "", "", 0


def domain_summary(urls: list[str]) -> list[dict]:
    hosts, scores, rows = [], [], []
    for url in urls:
        host, label, score = domain_info(url)
        hosts.append(host)
        scores.append(score)
        rows.append({"url": url, "host": host, "score": score, "label": label})
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
