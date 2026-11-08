"""Optional live-reference enrichment (free, no API key required).

IMPORTANT / honesty boundary: this retrieves *leads* from the public web at
request time. It is not a guarantee of completeness or correctness, and no
automated system can promise "100% match with real life data". Every reference
is attached with its URL, retrieval timestamp and an explicit review notice,
and Createlee still requires human approval before any document is finalised.
"""
from __future__ import annotations

import datetime as dt

import requests
from bs4 import BeautifulSoup

import config

DDG_IA = "https://api.duckduckgo.com/"
CROSSREF = "https://api.crossref.org/works"
UA = {"User-Agent": "Createlee/1.0 (local operational documentation tool)"}


def iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ddg(query: str) -> list[dict]:
    out: list[dict] = []
    try:
        r = requests.get(DDG_IA, params={"q": query, "format": "json",
                                          "no_html": 1, "skip_disambig": 1},
                         headers=UA, timeout=config.WEB_TIMEOUT)
        r.raise_for_status()
        d = r.json()
        if d.get("AbstractText") and d.get("AbstractURL"):
            out.append({"title": d.get("Heading") or query,
                        "url": d["AbstractURL"],
                        "snippet": d["AbstractText"][:400],
                        "source": d.get("AbstractSource") or "DuckDuckGo Instant Answer",
                        "query_used": query})
        for topic in d.get("RelatedTopics", []):
            items = topic.get("Topics", []) if isinstance(topic, dict) and "Topics" in topic else [topic]
            for sub in items:
                if isinstance(sub, dict) and sub.get("FirstURL"):
                    out.append({"title": (sub.get("Text") or "")[:120].split(" - ")[0],
                                "url": sub["FirstURL"],
                                "snippet": (sub.get("Text") or "")[:400],
                                "source": "DuckDuckGo RelatedTopics", "query_used": query})
    except Exception:  # noqa: BLE001 - web is optional, never fatal
        pass
    return out


def _crossref(query: str, limit: int = 3) -> list[dict]:
    """Free scholarly/standards literature leads. Supplementary only."""
    out: list[dict] = []
    try:
        r = requests.get(CROSSREF, params={"query": query, "rows": limit,
                                            "select": "title,URL,DOI,publisher,published"},
                         headers=UA, timeout=config.WEB_TIMEOUT)
        r.raise_for_status()
        for item in r.json().get("message", {}).get("items", []):
            title = (item.get("title") or [""])[0]
            url = item.get("URL") or ""
            if not url:
                continue
            out.append({"title": title[:160] or url, "url": url,
                        "snippet": f"Publisher: {item.get('publisher','n/a')} | DOI: {item.get('DOI','n/a')}",
                        "source": "Crossref (bibliographic lead)", "query_used": query})
    except Exception:  # noqa: BLE001
        pass
    return out


def search(query: str, limit: int = 6) -> list[dict]:
    """Try the full query, then progressively shorter variants (DDG IA is
    entity-oriented and returns nothing for long natural-language queries)."""
    if not config.WEB_ENRICH:
        return []
    found: list[dict] = []
    words = query.split()
    variants = [query]
    for n in (4, 3, 2, 1):
        if len(words) > n:
            v = " ".join(words[:n])
            if v not in variants:
                variants.append(v)
    for v in variants:
        found.extend(_ddg(v))
        if len(found) >= limit:
            break
    if len(found) < 3:
        found.extend(_crossref(query, limit=3))

    seen, out = set(), []
    for item in found:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        item["retrieved_at_iso8601"] = iso_now()
        out.append(item)
        if len(out) >= limit:
            break
    return out


def fetch_page(url: str, max_chars: int = 1200) -> dict | None:
    """Fetch a readable excerpt from a specific public URL."""
    if not url.startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(url, headers=UA, timeout=config.WEB_TIMEOUT)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(" ", strip=True).split())
        return {"url": url,
                "title": (soup.title.string.strip() if soup.title and soup.title.string else url),
                "excerpt": text[:max_chars], "retrieved_at_iso8601": iso_now(),
                "http_status": r.status_code, "source": "direct fetch"}
    except Exception:  # noqa: BLE001
        return None


def reference_pack(query: str, extra_urls: list[str] | None = None) -> dict:
    q = query.strip()
    refs: list[dict] = []
    # A bare URL means "fetch exactly this page".
    if q.startswith(("http://", "https://")):
        page = fetch_page(q)
        if page:
            refs.append(page)
    else:
        refs = search(q)
    for url in (extra_urls or [])[:3]:
        page = fetch_page(url)
        if page:
            refs.append(page)
    return {
        "query": q,
        "retrieved_at_iso8601": iso_now(),
        "count": len(refs),
        "references": refs,
        "notice": ("Live public-web leads retrieved at the timestamp above. These are supplementary "
                   "references, NOT verified ground truth. Web content changes continuously; no system "
                   "can guarantee a 100% match with real-world data. Verify each source and rely on your "
                   "own uploaded CSVs as the authoritative input. Human review/approval is mandatory."),
    }
