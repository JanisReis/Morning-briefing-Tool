#!/usr/bin/env python3
"""
Morning Briefing Tool
======================
Automatisiertes Morning Briefing fuer Global Markets / Fixed Income:
DAX, S&P 500, EZB- und Fed-Ankuendigungen -> ein LLM fasst sie taeglich in
einem strukturierten Briefing zusammen.

Aufruf:
    python main.py                  # normaler Lauf
    python main.py --dry-run        # ohne LLM-Aufruf (nur Rohdaten testen)
    python main.py --lang en        # Briefing auf Englisch
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, datetime, timezone

from dotenv import load_dotenv

from src.calendar_events import fetch_calendar
from src.market_data import fetch_all_indices
from src.news_feeds import fetch_recent_news
from src.render import render_brief
from src.summarizer import BriefInputs, SummarizerConfigError, generate_brief


def _fallback_brief(inputs: BriefInputs) -> str:
    """Deterministisches Ersatz-Briefing ohne LLM.

    Wird genutzt, wenn kein API-Key gesetzt ist oder der LLM-Aufruf
    fehlschlaegt (z. B. Rate Limit) - damit die taegliche Automatisierung
    trotzdem ein nutzbares Ergebnis liefert statt komplett abzubrechen.
    Das ist bewusst simpel/regelbasiert, nicht generativ.
    """
    lines = ["## Marktueberblick"]
    for snap in inputs.indices:
        if snap.error:
            lines.append(f"- {snap.name}: keine Daten ({snap.error})")
        else:
            lines.append(
                f"- {snap.name}: {snap.last_close} ({snap.change_pct:+.2f}% zum Vortag)"
            )

    lines.append("\n## Notenbanken")
    if not inputs.news:
        lines.append("- Keine neuen EZB-/Fed-Meldungen im Betrachtungszeitraum.")
    else:
        for item in inputs.news[:6]:
            lines.append(f"- [{item.source}] {item.title}")

    lines.append("\n## Einzuordnen fuer heute")
    if inputs.calendar_events:
        for ev in inputs.calendar_events[:5]:
            lines.append(f"- {ev.event_date.isoformat()} [{ev.region}] {ev.title}")
    else:
        lines.append("- Keine anstehenden Kalender-Termine im Betrachtungszeitraum.")
    lines.append("- Hinweis: automatisch generierte Rohdaten-Zusammenfassung (LLM nicht verfuegbar).")
    return "\n".join(lines)


def run(language: str = "de", lookback_hours: int = 72, lookahead_days: int = 14,
        dry_run: bool = False) -> int:
    started = time.monotonic()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starte Morning Briefing Lauf...")

    print("-> Lade Marktdaten (DAX, S&P 500) ueber yfinance...")
    indices = fetch_all_indices()
    for snap in indices:
        status = "OK" if not snap.error else f"FEHLER: {snap.error}"
        print(f"   {snap.name}: {status}")

    print(f"-> Lade EZB-/Fed-Meldungen der letzten {lookback_hours}h...")
    news = fetch_recent_news(lookback_hours=lookback_hours)
    print(f"   {len(news)} Meldung(en) gefunden.")

    print(f"-> Lade Wirtschaftskalender (naechste {lookahead_days} Tage)...")
    calendar_events = fetch_calendar(today=date.today(), lookahead_days=lookahead_days)
    print(f"   {len(calendar_events)} Termin(e) gefunden.")

    inputs = BriefInputs(indices=indices, news=news, calendar_events=calendar_events, language=language)

    if dry_run:
        print("-> --dry-run gesetzt: ueberspringe LLM-Aufruf, nutze Fallback-Text.")
        brief_text = _fallback_brief(inputs)
    else:
        print("-> Generiere Briefing per LLM...")
        try:
            brief_text = generate_brief(inputs)
        except SummarizerConfigError as exc:
            print(f"   Konfigurationsfehler: {exc}")
            print("   Nutze regelbasiertes Fallback-Briefing statt Abbruch.")
            brief_text = _fallback_brief(inputs)
        except Exception as exc:  # noqa: BLE001 - Automatisierung soll robust bleiben
            print(f"   LLM-Aufruf fehlgeschlagen: {exc}")
            print("   Nutze regelbasiertes Fallback-Briefing statt Abbruch.")
            brief_text = _fallback_brief(inputs)

    print("-> Rendere Markdown + HTML...")
    paths = render_brief(brief_text, indices, calendar_events=calendar_events,
                          lookahead_days=lookahead_days, language=language)
    for label, path in paths.items():
        print(f"   {label}: {path}")

    elapsed = time.monotonic() - started
    print(f"Fertig in {elapsed:.1f}s.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatisiertes Morning Briefing")
    parser.add_argument("--lang", default=None, choices=["de", "en"], help="Sprache des Briefings")
    parser.add_argument("--lookback-hours", type=int, default=72,
                         help="Zeitfenster fuer EZB-/Fed-Meldungen in Stunden (Default: 72)")
    parser.add_argument("--lookahead-days", type=int, default=None,
                         help="Zeitfenster fuer den Wirtschaftskalender in Tagen (Default: 14)")
    parser.add_argument("--dry-run", action="store_true",
                         help="Kein LLM-Aufruf, nur Rohdaten-Fallback (zum Testen ohne API-Key)")
    args = parser.parse_args()

    load_dotenv()

    language = args.lang or os.getenv("BRIEF_LANGUAGE", "de")
    lookahead_days = args.lookahead_days or int(os.getenv("CALENDAR_LOOKAHEAD_DAYS", "14"))

    exit_code = run(language=language, lookback_hours=args.lookback_hours,
                     lookahead_days=lookahead_days, dry_run=args.dry_run)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
