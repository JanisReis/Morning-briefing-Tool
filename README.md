# Morning Briefing Tool

Automatisiertes Morning Briefing für Global Markets / Fixed Income: fasst
DAX- und S&P-500-Entwicklung, EZB- und Fed-Ankündigungen sowie einen
Wirtschaftskalender (Inflation, Arbeitsmarkt, Notenbank-Sitzungen) jeden
Werktagmorgen automatisch zu einem strukturierten Briefing zusammen —
generiert per LLM, ganz ohne manuelles Zutun.

**Live-Beispiel:** `output/latest.html` (nach dem ersten Lauf) ·
Archiv aller bisherigen Briefings: `output/index.html`

---

## Warum dieses Projekt


**Das Problem:** Auf einem Trading- oder Sales-Desk verschafft man sich
morgens einen Überblick über die wichtigsten Indizes und Notenbank-News,
bevor der Handel beginnt. Manuell bedeutet das: mehrere Kurse nachschlagen,
Veränderungen selbst berechnen, ecb.europa.eu und federalreserve.gov nach
neuen Meldungen durchsuchen, das Ganze zu einer kurzen, lesbaren Notiz
zusammenfassen.

**Die Lösung:** Ein Python-Pipeline, die Marktdaten und Notenbank-Feeds
automatisch abruft, per LLM zu einem strukturierten Briefing verdichtet
und per GitHub Actions jeden Werktag ganz ohne menschliches Zutun neu
erzeugt.

### Effizienz-Nachweis

| | Manuell | Mit diesem Tool |
|---|---|---|
| Kurse nachschlagen & Veränderung berechnen | ~5 Min | automatisch |
| EZB- & Fed-Website nach neuen Meldungen durchsuchen | ~10–15 Min | automatisch |
| Wirtschaftskalender (FRED, ECB/Fed-Kalenderseiten) pruefen | ~5–10 Min | automatisch |
| Zusammenfassung formulieren | ~10 Min | automatisch |
| **Gesamt** | **~30–40 Min/Tag** | **< 30 Sek., läuft unbeaufsichtigt** |

Hochgerechnet auf einen 6-monatigen Praktikumszeitraum (≈130 Handelstage)
entspricht das einer Zeitersparnis von grob **65–85 Stunden**, wenn diese
Routineaufgabe manuell erledigt würde. Das ist die Art von Zahl, die sich
in Bewerbung und Interview konkret verwenden lässt (siehe unten).

---

## Architektur

```
                 ┌─────────────────┐
                 │  main.py (CLI)   │
                 └────────┬─────────┘
                          │
    ┌─────────────────┬─────────────────┬─────────────────────┐
    ▼                 ▼                 ▼                     ▼
┌───────────────┐ ┌───────────────┐ ┌───────────────────┐ ┌──────────────────┐
│ market_data.py │ │ news_feeds.py │ │ calendar_events.py │ │  summarizer.py    │
│ yfinance:      │ │ RSS-Feeds:    │ │ FRED-API (Inflation│ │  LLM (Groq/Gemini/│
│ DAX, S&P 500   │ │ EZB, Fed      │ │ /Arbeitsmarkt) +   │ │  OpenAI/Anthropic)│
│                │ │               │ │ EZB-/Fed-Termine   │ │                   │
└───────┬────────┘ └───────┬───────┘ └──────────┬─────────┘ └─────────┬─────────┘
        └─────────────────┴──────────────────────┴─────────────────────┘
                          │
                          ▼
                  ┌───────────────┐
                  │   render.py    │  -> Markdown + HTML
                  └───────┬────────┘
                          │
                          ▼
              output/briefs/YYYY-MM-DD.{md,html}
              output/latest.html · output/index.html
```

Jeder Baustein ist bewusst isoliert und einzeln testbar (siehe
`if __name__ == "__main__"` in jedem Modul). Schlägt ein Datenabruf fehl
(Netzwerkfehler, geänderte Feed-URL, LLM-Rate-Limit), bricht der Lauf nicht
ab, sondern nutzt ein regelbasiertes Fallback-Briefing — Robustheit vor
Vollständigkeit, weil das Tool täglich unbeaufsichtigt laufen soll.

---

## Wirtschaftskalender: Datenquellen & bewusste Grenzen

Für den Kalender-Abschnitt ("Diese X Tage wichtig", farblich EU/US
unterschieden) wurden bewusst unterschiedliche Techniken je nach
Datenverfügbarkeit gewählt — das ist selbst ein Punkt, der sich in einem
Interview gut erklären lässt: nicht jede Datenquelle hat eine saubere API,
und zu wissen, wann man scraped, wann man eine offizielle API nutzt und
wann man ehrlich "nicht verfügbar" sagt, ist Teil der Ingenieursarbeit.

| Termin-Typ | Region | Methode | Quelle |
|---|---|---|---|
| CPI, PCE (Inflation) | 🇺🇸 US | Live via FRED-API | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/fred/release_dates.html) |
| Employment Situation (Arbeitsmarkt/NFP) | 🇺🇸 US | Live via FRED-API | fred.stlouisfed.org |
| FOMC-Sitzungen | 🇺🇸 US | Fest hinterlegt (offiziell 1×/Jahr veröffentlicht) | [federalreserve.gov](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) |
| EZB-Ratssitzungen | 🇪🇺 EU | Fest hinterlegt (offiziell veröffentlicht) | [ecb.europa.eu](https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html) |
| HICP (Eurozone-Inflation) | 🇪🇺 EU | Best-effort-Scrape, mit Fallback | [EZB-Statistikkalender](https://www.ecb.europa.eu/press/calendars/statscal/html/index.en.html) |
| Eurozone-Arbeitsmarkt | 🇪🇺 EU | **Bewusst nicht automatisiert** | — |

**Warum kein automatischer EU-Arbeitsmarkt-Termin?** Eurostat bietet für
seinen Release-Kalender nur ICS-/E-Mail-Abo an, keine saubere öffentliche
API für Veröffentlichungstermine. Statt ein Datum zu schätzen oder zu
erfinden, lässt das Tool diesen Punkt bewusst weg — im Sinne der
Prompt-Instruktion "keine Fakten erfinden", die auch für den Code selbst
gilt. Eine mögliche Erweiterung (siehe unten) wäre ein Eurostat-ICS-Parser.

Die FOMC-/EZB-Sitzungstermine sind fest im Code hinterlegt
(`src/calendar_events.py`), weil beide Notenbanken ihren Kalender nur
einmal jährlich im Voraus veröffentlichen — eine tägliche Live-Abfrage
wäre hier unnötiger Overhead. Muss künftig 1×/Jahr manuell aktualisiert
werden (Quelle jeweils im Code kommentiert).

**Kostenlosen FRED-Key besorgen:** [fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
— Registrierung dauert unter 2 Minuten, keine Kreditkarte nötig.

---

## Setup

### 1. Repository lokal einrichten

```bash
git clone <dein-fork-url>
cd morning-briefing-tool
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. Kostenlosen LLM-API-Key besorgen

Kein Kreditkarte nötig für die empfohlenen Optionen:

- **Groq** (empfohlen, sehr schnell, großzügiger Free-Tier):
  [console.groq.com/keys](https://console.groq.com/keys) → Account anlegen
  → "Create API Key" → Key in `.env` bei `LLM_API_KEY` eintragen,
  `LLM_PROVIDER=groq` lassen.
- **Google Gemini** (Alternative, ebenfalls kostenlos):
  [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → Key
  erstellen → in `.env` eintragen, `LLM_PROVIDER=gemini` setzen.

Bereits einen OpenAI- oder Anthropic-Key? Einfach `LLM_PROVIDER` auf
`openai` bzw. `anthropic` setzen — der Code unterstützt beide zusätzlich.

### 3. Kostenlosen FRED-API-Key besorgen (für den Wirtschaftskalender)

[fred.stlouisfed.org/docs/api/api_key.html](https://fred.stlouisfed.org/docs/api/api_key.html)
→ kostenloser Account → Key in `.env` bei `FRED_API_KEY` eintragen. Ohne
diesen Key funktioniert das Tool trotzdem, zeigt im Kalender dann aber nur
die fest hinterlegten EZB-/Fed-Sitzungstermine, keine US-Inflations-/
Arbeitsmarkt-Daten.

### 4. Lokal testen

```bash
# Ohne LLM-Aufruf, nur Rohdaten/Formatierung pruefen:
python main.py --dry-run

# Vollstaendiger Lauf inkl. LLM:
python main.py
```

Ergebnis liegt danach in `output/latest.html` (im Browser öffnen) und
`output/briefs/`.

---

## Automatisierung (GitHub Actions)

Die Datei [`.github/workflows/daily_brief.yml`](.github/workflows/daily_brief.yml)
lässt das Tool jeden Werktag automatisch laufen, committet das Ergebnis
zurück ins Repo und veröffentlicht es über GitHub Pages.

**Einrichtung nach dem Forken/Pushen:**

1. Repo-Settings → **Secrets and variables → Actions**:
   - Secret `LLM_API_KEY` = dein LLM-API-Key
   - Secret `FRED_API_KEY` = dein kostenloser FRED-API-Key (für den
     Wirtschaftskalender; ohne diesen Key laufen nur die EZB-/Fed-
     Sitzungstermine, die US-Inflations-/Arbeitsmarkt-Termine bleiben leer)
   - (optional) Variable `LLM_PROVIDER` (Default: `groq`), `LLM_MODEL`,
     `BRIEF_LANGUAGE` (`de`/`en`), `CALENDAR_LOOKAHEAD_DAYS` (Default: `14`)
2. Repo-Settings → **Pages** → Source: **GitHub Actions**
3. Tab **Actions** → Workflow "Daily Morning Briefing" → **Run workflow**
   (einmal manuell testen)

Danach läuft die Pipeline jeden Werktag um 05:30 UTC automatisch — der
Commit-Verlauf des Repos wird damit selbst zum Nachweis, dass die
Automatisierung tatsächlich produktiv läuft, nicht nur lokal funktioniert.

---

## Projektstruktur

```
main.py                       Orchestrierung / CLI
src/market_data.py             DAX & S&P 500 via yfinance
src/news_feeds.py               EZB- & Fed-RSS-Feeds
src/calendar_events.py          Wirtschaftskalender (FRED-API + EZB-/Fed-Termine)
src/summarizer.py               Prompt-Bau + LLM-Aufruf (provider-agnostisch)
src/render.py                   Markdown -> HTML, Archiv-Verwaltung
src/templates/                  Jinja2-HTML-Templates
.github/workflows/daily_brief.yml   Taegliche Automatisierung
output/                         Generierte Briefings (Markdown + HTML)
```

---

---

## Mögliche Erweiterungen

- Weitere Indizes (Euro Stoxx 50, Bund-Future, Investment-Grade-Spreads)
- Versand des Briefings per E-Mail (z. B. via Resend/SMTP) statt/zusätzlich
  zu GitHub Pages
- Kreditrisiko-Variante für Corporate Banking: automatisierte
  Zusammenfassung von 10-K/Geschäftsbericht-Kennzahlen (RAG-Ansatz)
- Backtesting-Modul, das prüft, ob die im Briefing genannten "Watch"-Punkte
  tatsächlich Marktbewegungen vorausgesagt haben
- Eurostat-ICS-Kalender parsen, um auch den Eurozone-Arbeitsmarkt-Termin
  automatisch abzudecken (siehe Limitation oben)
- Weitere Frühindikatoren im Kalender: Ifo-Geschäftsklima, ZEW-Index,
  ISM/PMI-Daten


