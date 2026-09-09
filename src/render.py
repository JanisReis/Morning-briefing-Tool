"""
render.py
---------
Rendert das vom LLM erzeugte Morning Briefing (Markdown) in Markdown + HTML.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import markdown as md
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.calendar_events import CalendarEvent
from src.market_data import IndexSnapshot

TEMPLATE_DIR = Path(__file__).parent / "templates"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
BRIEFS_DIR = OUTPUT_DIR / "briefs"

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _slugify_date(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def render_brief(
    brief_markdown: str,
    indices: list[IndexSnapshot],
    calendar_events: list[CalendarEvent] | None = None,
    lookahead_days: int = 14,
    language: str = "de",
    now: datetime | None = None,
) -> dict[str, Path]:
    now = now or datetime.now(timezone.utc)
    date_slug = _slugify_date(now)

    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)

    md_path = BRIEFS_DIR / f"{date_slug}.md"
    md_header = f"# Morning Briefing — {date_slug}\n\n"
    md_path.write_text(md_header + brief_markdown.strip() + "\n", encoding="utf-8")

    brief_html = md.markdown(brief_markdown, extensions=["extra"])
    template = _env.get_template("brief.html.j2")
    html_out = template.render(
        language=language,
        date_display=date_slug,
        indices=indices,
        calendar_events=calendar_events or [],
        lookahead_days=lookahead_days,
        brief_html=brief_html,
        generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
    )

    html_path = BRIEFS_DIR / f"{date_slug}.html"
    html_path.write_text(html_out, encoding="utf-8")

    latest_path = OUTPUT_DIR / "latest.html"
    latest_path.write_text(html_out, encoding="utf-8")

    entries = sorted((p.stem for p in BRIEFS_DIR.glob("*.html")), reverse=True)
    index_template = _env.get_template("index.html.j2")
    index_html = index_template.render(entries=entries)
    index_path = OUTPUT_DIR / "index.html"
    index_path.write_text(index_html, encoding="utf-8")

    return {
        "markdown": md_path,
        "html": html_path,
        "latest": latest_path,
        "index": index_path,
    }
