"""
market_data.py
---------------
Holt aktuelle Marktdaten (DAX, S&P 500) ueber die kostenlose yfinance-API.

Kein API-Key noetig. yfinance liest oeffentliche Yahoo-Finance-Daten aus.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yfinance as yf


@dataclass
class IndexSnapshot:
    name: str
    ticker: str
    last_close: Optional[float]
    prev_close: Optional[float]
    change_pct: Optional[float]
    five_day_change_pct: Optional[float]
    as_of: Optional[str]
    error: Optional[str] = None

    @property
    def direction(self) -> str:
        if self.change_pct is None:
            return "n/a"
        if self.change_pct > 0:
            return "up"
        if self.change_pct < 0:
            return "down"
        return "flat"


INDEX_UNIVERSE = {
    "DAX": "^GDAXI",
    "S&P 500": "^GSPC",
}


def _safe_pct(new: float, old: float) -> Optional[float]:
    if old in (None, 0):
        return None
    return round((new - old) / old * 100, 2)


def fetch_index_snapshot(name: str, ticker: str) -> IndexSnapshot:
    try:
        hist = yf.Ticker(ticker).history(period="10d", interval="1d")
        hist = hist.dropna(subset=["Close"])

        if hist.empty or len(hist) < 2:
            return IndexSnapshot(
                name=name, ticker=ticker, last_close=None, prev_close=None,
                change_pct=None, five_day_change_pct=None, as_of=None,
                error="Keine ausreichenden Kursdaten verfuegbar.",
            )

        last_close = float(hist["Close"].iloc[-1])
        prev_close = float(hist["Close"].iloc[-2])
        as_of = hist.index[-1].strftime("%Y-%m-%d")

        five_day_ref = float(hist["Close"].iloc[0])
        change_pct = _safe_pct(last_close, prev_close)
        five_day_change_pct = _safe_pct(last_close, five_day_ref)

        return IndexSnapshot(
            name=name, ticker=ticker, last_close=round(last_close, 2),
            prev_close=round(prev_close, 2), change_pct=change_pct,
            five_day_change_pct=five_day_change_pct, as_of=as_of,
        )
    except Exception as exc:  # noqa: BLE001
        return IndexSnapshot(
            name=name, ticker=ticker, last_close=None, prev_close=None,
            change_pct=None, five_day_change_pct=None, as_of=None,
            error=f"Fehler beim Abruf: {exc}",
        )


def fetch_all_indices() -> list[IndexSnapshot]:
    return [fetch_index_snapshot(name, ticker) for name, ticker in INDEX_UNIVERSE.items()]


if __name__ == "__main__":
    for snap in fetch_all_indices():
        print(f"{snap.name:10s} | Close: {snap.last_close} | Change: {snap.change_pct}% "
              f"| 5T: {snap.five_day_change_pct}% | Stand: {snap.as_of} | Error: {snap.error}")
