"""
calendar_events.py
-------------------
Wirtschaftskalender: kommende Veroeffentlichungen zu Inflation und
Arbeitsmarkt (USA & Eurozone) sowie EZB-/Fed-Sitzungstermine.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import requests

FRED_BASE_URL = "https://api.stlouisfed.org/fred/release/dates"

FRED_RELEASES = {
    "US-CPI (Inflation)": 10,
    "US-Arbeitsmarktbericht (NFP)": 50,
    "US-PCE-Inflation": 54,
}

# Quelle: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm
FOMC_MEETINGS_2026 = [
    ("2026-01-27", "2026-01-28", False),
    ("2026-03-17", "2026-03-18", True),
    ("2026-04-28", "2026-04-29", False),
    ("2026-06-16", "2026-06-17", True),
    ("2026-07-28", "2026-07-29", False),
    ("2026-09-15", "2026-09-16", True),
    ("2026-10-27", "2026-10-28", False),
    ("2026-12-08", "2026-12-09", True),
]

# Quelle: https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html
ECB_MEETINGS_2026 = [
    ("2026-09-09", "2026-09-10"),
    ("2026-10-28", "2026-10-29"),
    ("2026-12-16", "2026-12-17"),
]

ECB_STATS_CALENDAR_URL = "https://www.ecb.europa.eu/press/calendars/statscal/html/index.en.html"


@dataclass
class CalendarEvent:
    event_date: date
    region: str
    category: str
    title: str
    source: str


def _parse_iso(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def fetch_fred_events(api_key: str, today: date, lookahead_days: int) -> list[CalendarEvent]:
    if not api_key:
        return []

    horizon = today + timedelta(days=lookahead_days)
    events: list[CalendarEvent] = []

    for label, release_id in FRED_RELEASES.items():
        category = "inflation" if "Inflation" in label or "CPI" in label else "arbeitsmarkt"
        try:
            resp = requests.get(
                FRED_BASE_URL,
                params={
                    "release_id": release_id,
                    "include_release_dates_with_no_data": "true",
                    "realtime_start": today.isoformat(),
                    "realtime_end": horizon.isoformat(),
                    "sort_order": "asc",
                    "api_key": api_key,
                    "file_type": "json",
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            for entry in data.get("release_dates", []):
                event_date = _parse_iso(entry["date"])
                if today <= event_date <= horizon:
                    events.append(
                        CalendarEvent(
                            event_date=event_date, region="US", category=category,
                            title=label, source="FRED (St. Louis Fed)",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            events.append(
                CalendarEvent(
                    event_date=today, region="US", category=category,
                    title=f"[Fehler beim Abruf von '{label}': {exc}]",
                    source="FRED (St. Louis Fed)",
                )
            )
    return events


def central_bank_meetings(today: date, lookahead_days: int) -> list[CalendarEvent]:
    horizon = today + timedelta(days=lookahead_days)
    events: list[CalendarEvent] = []

    for start_s, end_s, has_projections in FOMC_MEETINGS_2026:
        start = _parse_iso(start_s)
        if today <= start <= horizon:
            suffix = " (inkl. Wirtschaftsprognosen)" if has_projections else ""
            events.append(
                CalendarEvent(
                    event_date=start, region="US", category="notenbank",
                    title=f"FOMC-Sitzung ({start_s} bis {end_s}){suffix}",
                    source="Federal Reserve",
                )
            )

    for start_s, end_s in ECB_MEETINGS_2026:
        start = _parse_iso(start_s)
        if today <= start <= horizon:
            events.append(
                CalendarEvent(
                    event_date=start, region="EU", category="notenbank",
                    title=f"EZB-Ratssitzung ({start_s} bis {end_s})",
                    source="Europäische Zentralbank",
                )
            )

    return events


def fetch_ecb_hicp_events(today: date, lookahead_days: int) -> list[CalendarEvent]:
    horizon = today + timedelta(days=lookahead_days)
    try:
        from bs4 import BeautifulSoup

        resp = requests.get(ECB_STATS_CALENDAR_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[CalendarEvent] = []
        text_blocks = soup.find_all(["tr", "li", "dd", "p"])
        for block in text_blocks:
            text = block.get_text(" ", strip=True)
            if "HICP" not in text:
                continue
            event_date = _extract_date_from_text(text, today.year)
            if event_date and today <= event_date <= horizon:
                events.append(
                    CalendarEvent(
                        event_date=event_date, region="EU", category="inflation",
                        title=text[:120], source="EZB Statistical Calendar",
                    )
                )
        return events
    except Exception as exc:  # noqa: BLE001
        return [
            CalendarEvent(
                event_date=today, region="EU", category="inflation",
                title=f"[EZB-HICP-Kalender nicht abrufbar: {exc}]",
                source="EZB Statistical Calendar",
            )
        ]


_MONTHS_DE_EN = {
    "january": 1, "jan": 1, "februar": 2, "february": 2, "feb": 2,
    "märz": 3, "march": 3, "mar": 3, "april": 4, "apr": 4,
    "mai": 5, "may": 5, "juni": 6, "june": 6, "jun": 6,
    "juli": 7, "july": 7, "jul": 7, "august": 8, "aug": 8,
    "september": 9, "sep": 9, "oktober": 10, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "dezember": 12, "december": 12, "dec": 12,
}


def _extract_date_from_text(text: str, default_year: int) -> Optional[date]:
    import re

    iso_match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso_match:
        y, m, d = map(int, iso_match.groups())
        try:
            return date(y, m, d)
        except ValueError:
            return None

    dm_match = re.search(r"(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]+)\.?\s+(\d{4})", text)
    if dm_match:
        day_s, month_s, year_s = dm_match.groups()
        month = _MONTHS_DE_EN.get(month_s.lower())
        if month:
            try:
                return date(int(year_s), month, int(day_s))
            except ValueError:
                return None
    return None


def fetch_calendar(today: Optional[date] = None, lookahead_days: int = 14) -> list[CalendarEvent]:
    today = today or date.today()
    fred_api_key = os.getenv("FRED_API_KEY", "").strip()

    events: list[CalendarEvent] = []
    events += fetch_fred_events(fred_api_key, today, lookahead_days)
    events += central_bank_meetings(today, lookahead_days)
    events += fetch_ecb_hicp_events(today, lookahead_days)

    events.sort(key=lambda e: e.event_date)
    return events


if __name__ == "__main__":
    for ev in fetch_calendar(lookahead_days=30):
        print(f"{ev.event_date} | {ev.region:2s} | {ev.category:12s} | {ev.title} ({ev.source})")
