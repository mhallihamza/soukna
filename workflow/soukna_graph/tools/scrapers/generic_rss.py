# =====================================================================
# Scraper générique RSS / Atom — couvre la plupart des sources
# institutionnelles sans écrire de code spécifique : on ajoute la source
# dans la console admin (kind='rss'), le flux est lu ici.
# =====================================================================
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime

import requests

from .base import normalize_item

UA = {"User-Agent": "Mozilla/5.0 (compatible; SouknaBot/1.0; +https://soukna.ma)"}
# horizons d'échéance plausibles : une date de publication très ancienne
# n'est PAS une échéance (même garde-fou que le portail).
MAX_PUBLISHED_AGE_DAYS = 400


def _text(node: ET.Element | None) -> str:
    return (node.text or "").strip() if node is not None and node.text else ""


def _parse_date(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    dt: datetime | None = None
    try:
        dt = parsedate_to_datetime(raw)          # RFC 822 (RSS 2.0)
    except (TypeError, ValueError):
        pass
    if dt is None:
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        return None
    try:
        if (date.today() - dt.date()).days > MAX_PUBLISHED_AGE_DAYS:
            return None
        return dt.date().isoformat()
    except ValueError:
        return None


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", text).strip()


def _parse_feed(xml: str, source_name: str, source_url: str) -> list[dict]:
    root = ET.fromstring(re.sub(r"^<\?xml[^>]*\?>", "", xml).strip() or "<rss/>")
    items: list[dict] = []
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1]
        if tag != "item" and tag != "entry":
            continue
        title, link, summary, published = "", "", "", ""
        for child in node.iter():
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag == "title" and not title:
                title = _text(child)
            elif child_tag == "link" and not link:
                link = _text(child) or (child.get("href") or "")
            elif child_tag in {"description", "summary", "content"} and not summary:
                summary = _strip_html(_text(child))
            elif child_tag in {"pubDate", "published", "updated", "date"} and not published:
                published = _text(child)
        if not title:
            continue
        guid = ""
        for child in node.iter():
            if child.tag.rsplit("}", 1)[-1] in {"guid", "id"}:
                guid = _text(child)
                break
        ref = guid or link or title
        items.append(normalize_item({
            "source_ref": f"{ref}"[:200],
            "source": source_name,
            "title": title[:250],
            "buyer": "",
            "city": "",
            "region": "",
            "sector": "",
            "domain_code": "",
            "deadline": _parse_date(published),
            "amount": "",
            "url": link or source_url,
            "raw": {"summary": summary[:500], "published": published},
        }, source_name))
    return items


def fetch(source: dict) -> list[dict]:
    """Lit le flux RSS/Atom de la source (base_url) et retourne les items."""
    url = (source.get("base_url") or "").strip()
    if not url:
        raise RuntimeError("rss : base_url vide")
    r = requests.get(url, headers=UA, timeout=30)
    r.raise_for_status()
    name = source.get("name") or "rss"
    items = _parse_feed(r.text, name, url)
    if not items:
        raise RuntimeError(f"rss : flux vide ({url})")
    return items
