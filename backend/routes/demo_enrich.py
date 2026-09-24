"""Iter173 — Site enrichment for the public ARIA demo personalisation flow.

Endpoint: `GET /api/enrich?domain=example.com`

Fetches the target site's `<title>`, `<meta description>`, `og:image`, and a
short keyword list (from meta keywords / title / description). Everything
has a 3-second timeout. On any failure — DNS, TLS, HTTP error, timeout —
we return a graceful fallback derived from the domain so the demo never
shows an error to a prospect.

Results are cached in MongoDB (`demo_enrichment` collection) for 24h so
repeat demos of the same company are instant.

Auth: none (public — this endpoint powers the /aria-demo landing overlay).
Safety: constrained to http(s) URLs, private/localhost hosts rejected,
response body capped at 512 KB before parsing.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, HTTPException, Query
from slowapi import Limiter
from slowapi.util import get_remote_address

from deps import db

router = APIRouter(prefix="/api", tags=["demo-enrich"])

_enrich_col = db["demo_enrichment"]

_TIMEOUT       = 3.0
_MAX_BYTES     = 512 * 1024
_UA            = "AriaDemoBot/1.0 (+https://aria.emergentagent.com)"
_CACHE_HOURS   = 24
_KW_STOP       = set(
    "the a an and or but of for to in on with by from at as is are be we you our your "
    "this that these those it its their they them who whom what which when where why how "
    "if then so than more most all any every some no not up down out over under new "
    "using use used using site page home about services products contact"
    .split()
)

_limiter = Limiter(key_func=get_remote_address)


# ─── helpers ───────────────────────────────────────────────────────────
def _normalise_domain(raw: str) -> Optional[str]:
    """Accept 'example.com', 'https://example.com/path', 'linkedin.com/company/x'."""
    if not raw or len(raw) > 253:
        return None
    raw = raw.strip().lower()
    # Strip protocol + www + trailing path/qs/hash.
    raw = re.sub(r"^https?://", "", raw)
    raw = re.sub(r"^www\.", "", raw)
    raw = raw.split("/")[0].split("?")[0].split("#")[0]
    # domain regex — TLD >= 2 chars
    if not re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+", raw):
        return None
    return raw


def _is_public_host(host: str) -> bool:
    """SSRF guard — reject private/loopback/link-local/multicast targets."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
                return False
        except Exception:
            return False
    return True


def _title_case_from_domain(domain: str) -> str:
    """example-co.com → 'Example Co'"""
    root = domain.split(".")[0]
    words = re.split(r"[-_]+", root)
    return " ".join(w.capitalize() for w in words if w) or root.capitalize()


def _extract_meta(html: str) -> dict:
    """Very small, dependency-free HTML meta parser. Not a full parser —
    good enough for <title>, common <meta name=…>, and <meta property=og:…>."""
    def _first(pattern: str, flags: int = re.I | re.S) -> Optional[str]:
        m = re.search(pattern, html, flags)
        if not m:
            return None
        val = m.group(1).strip()
        # Strip HTML entities minimally
        val = val.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
        return val or None

    title = _first(r"<title[^>]*>(.*?)</title>")
    og_title = _first(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']')
    og_desc  = _first(r'<meta[^>]+property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']')
    og_image = _first(r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']')
    meta_desc = _first(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)["\']')
    meta_kw   = _first(r'<meta[^>]+name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']')

    return {
        "title":        og_title or title,
        "description":  og_desc  or meta_desc,
        "og_image":     og_image,
        "keywords_raw": meta_kw,
    }


def _derive_keywords(meta: dict, fallback_text: str) -> list[str]:
    """Prefer explicit meta keywords; otherwise mine title + description."""
    if meta.get("keywords_raw"):
        parts = [p.strip().lower() for p in meta["keywords_raw"].split(",")]
        parts = [p for p in parts if p and 2 < len(p) < 40]
        if parts:
            return parts[:12]
    text = " ".join(filter(None, [meta.get("title"), meta.get("description"), fallback_text]))
    if not text:
        return []
    words = re.findall(r"[A-Za-z][A-Za-z-]{2,}", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w in _KW_STOP or len(w) > 40:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:12]]


def _clean_tagline(desc: Optional[str], title: Optional[str]) -> Optional[str]:
    text = (desc or title or "").strip()
    if not text:
        return None
    # Trim brand suffix like "Foo – The best CRM" → "The best CRM"
    for sep in ("—", "–", " | ", " - "):
        if sep in text:
            parts = [p.strip() for p in text.split(sep) if p.strip()]
            if len(parts) >= 2 and 8 <= len(parts[-1]) <= 140:
                text = parts[-1]
                break
    return text[:140] or None


def _fallback(domain: str) -> dict:
    name = _title_case_from_domain(domain)
    return {
        "domain":       domain,
        "companyName":  name,
        "tagline":      None,
        "logoUrl":      f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
        "keywords":     [],
        "source":       "fallback",
        "cached":       False,
        "fetchedAt":    datetime.now(timezone.utc).isoformat(),
    }


# ─── endpoint ──────────────────────────────────────────────────────────
@router.get("/enrich")
def enrich(domain: str = Query(..., min_length=3, max_length=253)):
    """Return a personalisation payload for the demo dashboard.

    Never raises to the client — always returns a usable JSON dict.
    """
    norm = _normalise_domain(domain)
    if not norm:
        return _fallback(domain.strip().lower()[:64])

    # ── cache hit? ───────────────────────────────────────────────────
    try:
        cached = _enrich_col.find_one({"_id": norm})
        if cached:
            fetched = cached.get("fetchedAt")
            if fetched:
                try:
                    ts = datetime.fromisoformat(fetched.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - ts < timedelta(hours=_CACHE_HOURS):
                        out = {k: v for k, v in cached.items() if k != "_id"}
                        out["cached"] = True
                        return out
                except Exception:
                    pass
    except Exception:
        pass

    # ── fresh fetch (SSRF-guarded, capped, timed out) ────────────────
    if not _is_public_host(norm):
        return _fallback(norm)

    html = ""
    resolved_url = f"https://{norm}"
    try:
        resp = requests.get(
            resolved_url,
            headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
            timeout=_TIMEOUT,
            allow_redirects=True,
            stream=True,
        )
        # cap body to _MAX_BYTES
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=32 * 1024, decode_unicode=False):
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total >= _MAX_BYTES:
                break
        raw = b"".join(chunks)
        html = raw.decode(resp.encoding or "utf-8", errors="replace")
    except Exception:
        html = ""

    meta = _extract_meta(html) if html else {}
    company_name = None
    if meta.get("title"):
        # Strip common "Home | Foo" / "Foo — About" noise
        t = meta["title"]
        for sep in (" | ", " — ", " – ", " - ", " :: "):
            if sep in t:
                t = t.split(sep, 1)[0].strip()
                break
    if (2 <= len(t) <= 60 and t.lower() not in {"home", "welcome", "index"}
            and any(c.isalnum() for c in t) and len(re.sub(r'[^A-Za-z0-9]', '', t)) >= 3):
        company_name = t

    if not company_name:
        company_name = _title_case_from_domain(norm)

    tagline    = _clean_tagline(meta.get("description"), meta.get("title"))
    og_image   = meta.get("og_image")
    if og_image and og_image.startswith("//"):
        og_image = "https:" + og_image
    elif og_image and og_image.startswith("/"):
        og_image = f"https://{norm}{og_image}"
    logo_url   = og_image or f"https://www.google.com/s2/favicons?domain={norm}&sz=128"
    keywords   = _derive_keywords(meta, fallback_text=norm.replace(".", " "))

    payload = {
        "domain":       norm,
        "companyName":  company_name,
        "tagline":      tagline,
        "logoUrl":      logo_url,
        "keywords":     keywords,
        "source":       "live",
        "cached":       False,
        "fetchedAt":    datetime.now(timezone.utc).isoformat(),
    }

    # ── best-effort cache write ─────────────────────────────────────
    try:
        _enrich_col.update_one(
            {"_id": norm},
            {"$set": {**payload, "_id": norm}},
            upsert=True,
        )
    except Exception:
        pass

    return payload
