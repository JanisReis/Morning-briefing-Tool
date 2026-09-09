"""
summarizer.py
-------------
Baut aus Marktdaten + Nachrichten einen Prompt und laesst ein LLM daraus
ein strukturiertes Morning Briefing formulieren.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from src.calendar_events import CalendarEvent
from src.market_data import IndexSnapshot
from src.news_feeds import NewsItem

OPENAI_COMPATIBLE_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
    "openai": None,
}

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-20241022",
}


class SummarizerConfigError(RuntimeError):
    pass


@dataclass
class BriefInputs:
    indices: list[IndexSnapshot]
    news: list[NewsItem]
    calendar_events: list[CalendarEvent] | None = None
    language: str = "de"


def _format_indices(indices: list[IndexSnapshot]) -> str:
    lines = []
    for snap in indices:
        if snap.error:
            lines.append(f"- {snap.name}: Daten nicht verfuegbar ({snap.error})")
            continue
        lines.append(
            f"- {snap.name} ({snap.ticker}): Schlusskurs {snap.last_close} "
            f"({snap.change_pct:+.2f}% zum Vortag, {snap.five_day_change_pct:+.2f}% "
            f"ueber 5 Handelstage, Stand {snap.as_of})"
        )
    return "\n".join(lines) if lines else "Keine Marktdaten verfuegbar."


def _format_news(news: list[NewsItem]) -> str:
    if not news:
        return "Keine neuen EZB-/Fed-Meldungen im Betrachtungszeitraum."
    lines = []
    for item in news:
        when = item.published.strftime("%Y-%m-%d %H:%M UTC") if item.published else "Datum unbekannt"
        lines.append(f"- [{item.source} | {when}] {item.title}\n  {item.summary[:400]}")
    return "\n".join(lines)


def _format_calendar(events: list[CalendarEvent]) -> str:
    if not events:
        return "Keine anstehenden Termine im Betrachtungszeitraum."
    lines = []
    for ev in events:
        lines.append(f"- {ev.event_date.isoformat()} [{ev.region}/{ev.category}] {ev.title}")
    return "\n".join(lines)


SYSTEM_PROMPTS = {
    "de": (
        "Du bist Analyst auf einem Markets-Desk und schreibst ein knappes, "
        "praezises Morning Briefing fuer Kolleginnen und Kollegen im Handel. "
        "Stil: sachlich, kurze Saetze, keine Floskeln, keine Anlageempfehlungen. "
        "Gliedere IMMER in genau diese Abschnitte mit Markdown-Ueberschriften: "
        "'## Marktueberblick' (DAX & S&P 500, je 1-2 Saetze), "
        "'## Notenbanken' (EZB & Fed, was ist neu und warum relevant), "
        "'## Einzuordnen fuer heute' (2-3 Stichpunkte, worauf der Desk heute achten sollte - "
        "beziehe hier relevante Termine aus dem Wirtschaftskalender mit ein, wenn vorhanden). "
        "Erfinde keine Zahlen, Fakten oder Termine, die nicht in den Rohdaten bzw. dem "
        "Kalenderabschnitt stehen. Wenn Daten fehlen, sag das explizit statt zu raten."
    ),
    "en": (
        "You are an analyst on a markets desk writing a concise, precise morning "
        "briefing for trading colleagues. Style: factual, short sentences, no filler, "
        "no investment advice. ALWAYS structure the output into exactly these "
        "Markdown sections: '## Market Overview' (DAX & S&P 500, 1-2 sentences each), "
        "'## Central Banks' (ECB & Fed, what's new and why it matters), "
        "'## Watch today' (2-3 bullet points on what the desk should watch today - "
        "reference relevant upcoming calendar events where applicable). "
        "Never invent numbers, facts or dates that are not in the raw data or calendar "
        "section provided. If data is missing, say so explicitly instead of guessing."
    ),
}


def build_prompt(inputs: BriefInputs) -> tuple[str, str]:
    lang = inputs.language if inputs.language in SYSTEM_PROMPTS else "de"
    system_prompt = SYSTEM_PROMPTS[lang]

    user_prompt = (
        f"MARKTDATEN (Stand heute):\n{_format_indices(inputs.indices)}\n\n"
        f"EZB-/FED-MELDUNGEN (letzte Stunden):\n{_format_news(inputs.news)}\n\n"
        f"WIRTSCHAFTSKALENDER (kommende Termine):\n{_format_calendar(inputs.calendar_events or [])}\n\n"
        "Schreibe daraus jetzt das Morning Briefing gemaess der vorgegebenen Struktur."
    )
    return system_prompt, user_prompt


def _call_openai_compatible(provider: str, api_key: str, model: str,
                             system_prompt: str, user_prompt: str) -> str:
    from openai import OpenAI

    base_url = OPENAI_COMPATIBLE_BASE_URLS[provider]
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=700,
    )
    return response.choices[0].message.content.strip()


def _call_anthropic(api_key: str, model: str, system_prompt: str, user_prompt: str) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=700,
        temperature=0.3,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if hasattr(block, "text")).strip()


def generate_brief(inputs: BriefInputs) -> str:
    provider = os.getenv("LLM_PROVIDER", "groq").lower().strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip() or DEFAULT_MODELS.get(provider, "")

    if not api_key:
        raise SummarizerConfigError(
            "LLM_API_KEY ist nicht gesetzt. Trage in der .env-Datei einen API-Key ein "
            "(siehe .env.example fuer kostenlose Optionen wie Groq oder Gemini)."
        )

    system_prompt, user_prompt = build_prompt(inputs)

    if provider in OPENAI_COMPATIBLE_BASE_URLS:
        return _call_openai_compatible(provider, api_key, model, system_prompt, user_prompt)
    if provider == "anthropic":
        return _call_anthropic(api_key, model, system_prompt, user_prompt)

    raise SummarizerConfigError(
        f"Unbekannter LLM_PROVIDER '{provider}'. Erlaubt: "
        f"{', '.join(list(OPENAI_COMPATIBLE_BASE_URLS) + ['anthropic'])}."
    )
