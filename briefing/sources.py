"""Fetchers for recent startup launches. Each fetcher returns a list of Launch objects."""

from __future__ import annotations

import html
import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
TIMEOUT = 20
DETAILS_CHARS = 2500


@dataclass
class Launch:
    id: str
    source: str
    name: str
    tagline: str
    url: str
    published: str
    details: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _get(url: str, **kwargs) -> requests.Response:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, **kwargs)
    r.raise_for_status()
    return r


def _text(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)\b.*?</\1>", " ", fragment, flags=re.S | re.I)
    fragment = re.sub(r"<[^>]+>", " ", fragment)
    return re.sub(r"\s+", " ", html.unescape(fragment)).strip()


def _meta(page: str, key: str) -> str:
    m = re.search(rf'<meta[^>]*(?:property|name)="{re.escape(key)}"[^>]*content="([^"]*)"', page)
    return html.unescape(m.group(1)).strip() if m else ""


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fetch_launch_hn(since: datetime) -> list[Launch]:
    """YC company launches, via 'Launch HN' posts on Hacker News (Algolia API)."""
    r = _get(
        "https://hn.algolia.com/api/v1/search_by_date",
        params={
            "query": '"Launch HN"',
            "tags": "story",
            "numericFilters": f"created_at_i>{int(since.timestamp())}",
            "hitsPerPage": 50,
        },
    )
    out = []
    for h in r.json().get("hits", []):
        title = h.get("title") or ""
        if not title.startswith("Launch HN:"):
            continue
        m = re.match(r"Launch HN:\s*(.+?)\s*(?:\((YC [A-Z]+\d+)\))?\s*[–—-]\s*(.+)", title)
        name, batch, tagline = (m.group(1), m.group(2), m.group(3)) if m else (title[10:].strip(), None, "")
        out.append(
            Launch(
                id=f"hn:{h['objectID']}",
                source=f"Y Combinator {batch[3:]} (Launch HN)" if batch else "Y Combinator (Launch HN)",
                name=name,
                tagline=tagline,
                url=h.get("url") or f"https://news.ycombinator.com/item?id={h['objectID']}",
                published=h["created_at"][:10],
                details=f"[HN points: {h.get('points', 0)}] " + _text(h.get("story_text") or "")[:DETAILS_CHARS],
            )
        )
    return out


def fetch_product_hunt(since: datetime, limit: int = 30) -> list[Launch]:
    """Product Hunt launches from the public Atom feed, enriched with each product's description."""
    feed = _get("https://www.producthunt.com/feed").text
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", feed, re.S)[:limit]:
        published = re.search(r"<published>(.*?)</published>", entry)
        if not published or _parse_iso(published.group(1)) < since:
            continue
        title = html.unescape(re.search(r"<title>(.*?)</title>", entry, re.S).group(1)).strip()
        link = re.search(r'<link[^>]*href="([^"]+)"', entry).group(1)
        content = re.search(r"<content[^>]*>(.*?)</content>", entry, re.S)
        tagline = _text(html.unescape(content.group(1))) if content else ""
        tagline = re.sub(r"\s*Discussion\s*\|\s*Link\s*$", "", tagline)
        details = ""
        time.sleep(1)  # Product Hunt returns 403 on rapid page fetches
        try:
            details = _meta(_get(link).text, "og:description")
        except requests.RequestException as e:
            log.warning("Product Hunt details failed for %s: %s", link, e)
        out.append(
            Launch(
                id=f"ph:{link.rstrip('/').rsplit('/', 1)[-1]}",
                source="Product Hunt",
                name=title,
                tagline=tagline,
                url=link,
                published=published.group(1)[:10],
                details=details[:DETAILS_CHARS],
            )
        )
    return out


def fetch_devpost(since: datetime, limit: int = 15) -> list[Launch]:
    """Newest Devpost hackathon projects, enriched with the project write-up."""
    page = _get("https://devpost.com/software/newest").text
    cards = re.findall(
        r'<a class="block-wrapper-link fade link-to-software" href="([^"]+)".*?<h5>\s*(.*?)\s*</h5>'
        r'.*?<p class="small tagline">\s*(.*?)\s*</p>',
        page,
        re.S,
    )
    out = []
    for url, name, tagline in cards[:limit]:
        try:
            detail = _get(url).text
        except requests.RequestException as e:
            log.warning("Devpost details failed for %s: %s", url, e)
            continue
        t = re.search(r'<time class="timeago" datetime="([^"]+)"', detail)
        if t and _parse_iso(t.group(1)) < since:
            continue
        body = re.search(r'id="app-details-left"(.*?)id="built-with"', detail, re.S)
        built = re.search(r'id="built-with"(.*?)</ul>', detail, re.S)
        submitted = re.search(r"Submitted to(.*?)</ul>", detail, re.S)
        hackathon = _text(submitted.group(1)) if submitted else ""
        parts = [
            f"Hackathon: {hackathon}" if hackathon else "",
            f"Built with: {_text(built.group(1)).replace('Built With', '').strip()}" if built else "",
            _text(body.group(1)) if body else "",
        ]
        out.append(
            Launch(
                id=f"devpost:{url.rstrip('/').rsplit('/', 1)[-1]}",
                source=f"Devpost ({hackathon})" if hackathon else "Devpost",
                name=_text(name),
                tagline=_text(tagline),
                url=url,
                published=t.group(1)[:10] if t else datetime.now(timezone.utc).date().isoformat(),
                details=" | ".join(p for p in parts if p)[:DETAILS_CHARS],
            )
        )
    return out


def _collect_articles(node, found: list[dict]) -> None:
    if isinstance(node, dict):
        if node.get("@type") == "NewsArticle" and node.get("url") and node.get("datePublished"):
            found.append(node)
            return
        for value in node.values():
            _collect_articles(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_articles(value, found)


def fetch_uzcombinator(since: datetime) -> list[Launch]:
    """UzCombinator news posts (Uzbek); many are startup spotlights, the LLM skips the rest."""
    page = _get("https://uzcombinator.uz/news").text
    articles: list[dict] = []
    for block in re.findall(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', page, re.S):
        try:
            _collect_articles(json.loads(block), articles)
        except json.JSONDecodeError:
            continue
    out = []
    for art in articles:
        if _parse_iso(art["datePublished"]) < since:
            continue
        url = art["url"]
        details = art.get("description", "")
        try:
            body = _text(_get(url).text)
            start = body.find(art["headline"])
            details = body[start : start + DETAILS_CHARS] if start >= 0 else details
            details = details.split("O‘xshash yangiliklar")[0]
        except requests.RequestException as e:
            log.warning("UzCombinator details failed for %s: %s", url, e)
        out.append(
            Launch(
                id=f"uzc:{url.rstrip('/').rsplit('/', 1)[-1]}",
                source="UzCombinator",
                name=html.unescape(art["headline"]),
                tagline="",
                url=url,
                published=art["datePublished"][:10],
                details=details,
            )
        )
    return out


FETCHERS = {
    "launch_hn": fetch_launch_hn,
    "product_hunt": fetch_product_hunt,
    "devpost": fetch_devpost,
    "uzcombinator": fetch_uzcombinator,
}


def fetch_all(days: int) -> list[Launch]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    launches: list[Launch] = []
    for name, fetch in FETCHERS.items():
        try:
            found = fetch(since)
            log.info("%s: %d launches", name, len(found))
            launches.extend(found)
        except Exception as e:  # one broken source must not stop the briefing
            log.error("%s failed: %s", name, e)
    return launches
