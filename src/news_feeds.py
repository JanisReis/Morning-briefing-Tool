"""
news_feeds.py
--------------
Holt aktuelle Ankuendigungen der EZB und der US-Notenbank (Fed) ueber deren
oeffentliche, kostenlose RSS-Feeds. Kein API-Key noetig.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import mktime
from typing import Optional

import feedparser

FEEDS = {
    "EZB": "https://www.ecb.europa.eu/rss/press.html",
    "Fed": "https://www.federalreserve.gov/feeds/press_monetary.xml",
}


@dataclass
class NewsItem:
    source: str
    title: str
    summary: str
    link: str
    published: Optional[datetime]


def _parse_published(entry) -> Optional[datetime]:
    for field in ("published_parsed", "updated_parsed"):
        value = getattr(entry, field, None)
        if value:
            return datetime.fromtimestamp(mktime(value), tz=timezone.utc)
    return None


def fetch_recent_news(lookback_hours: int = 48) -> list[NewsItem]:
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=lookback_hours)
    items: list[NewsItem] = []

    for source, url in FEEDS.items():
        try:
            parsed = feedparser.parse(url)
            if parsed.bozo and not parsed.entries:
                raise RuntimeError(str(getattr(parsed, "bozo_exception", "unbekannter Fehler")))
            for entry in parsed.entries:
                published = _parse_published(entry)
                if published is not None and published < cutoff:
                    continue
                items.append(
                    NewsItem(
                        source=source,
                        title=getattr(entry, "title", "(ohne Titel)").strip(),
                        summary=getattr(entry, "summary", "").strip(),
                        link=getattr(entry, "link", ""),
                        published=published,
                    )
                )
        except Exception as exc:  # noqa: BLE001
            items.append(
                NewsItem(
                    source=source,
                    title=f"[Fehler beim Abruf von {source}]",
                    summary=str(exc),
                    link=url,
                    published=None,
                )
            )

    items.sort(key=lambda i: i.published or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


if __name__ == "__main__":
    for item in fetch_recent_news(lookback_hours=24 * 14):
        when = item.published.strftime("%Y-%m-%d %H:%M") if item.published else "?"
        print(f"[{item.source}] {when} - {item.title}")
