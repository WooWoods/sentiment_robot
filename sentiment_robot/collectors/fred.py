"""FRED macro indicator collector."""

import logging
from datetime import datetime, timedelta, timezone

import requests

from .base import BaseCollector

logger = logging.getLogger(__name__)

FRED_API_BASE = "https://api.stlouisfed.org/fred"

MACRO_SERIES = {
    "fed_funds_rate": "FEDFUNDS",
    "10y_treasury": "DGS10",
    "30y_treasury": "DGS30",
    "yield_curve": "T10Y2Y",
    "cpi": "CPIAUCSL",
    "core_cpi": "CPILFESL",
    "pce": "PCEPI",
    "core_pce": "PCEPILFE",
    "real_gdp": "GDPC1",
    "unemployment": "UNRATE",
    "vix": "VIXCLS",
    "consumer_sentiment": "UMCSENT",
    "nonfarm_payrolls": "PAYEMS",
    "initial_claims": "ICSA",
}

MAX_ROWS = 30
DEFAULT_LOOKBACK_DAYS = 365


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_series(indicator: str) -> str:
    key = indicator.strip().lower().replace(" ", "_")
    return MACRO_SERIES.get(key, indicator.strip().upper())


class FredCollector(BaseCollector):
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "fred"

    def run(self) -> list[dict]:
        api_key = self._config["fred_api_key"]
        if not api_key:
            return [{
                "source": self.name,
                "ticker": None,
                "content": "<FRED not configured: set FRED_API_KEY env var>",
                "fetched_at": _now_iso(),
            }]

        indicators = self._config["fred_indicators"]
        now = _now_iso()
        end_dt = datetime.now()
        start_date = (end_dt - timedelta(days=DEFAULT_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
        end_date = end_dt.strftime("%Y-%m-%d")

        results = []
        for indicator in indicators:
            try:
                series_id = _resolve_series(indicator)
                results.append(self._fetch_one(api_key, series_id, indicator, start_date, end_date, now))
            except Exception as e:
                logger.warning("FRED fetch failed for %s: %s", indicator, e)
                results.append({
                    "source": self.name,
                    "ticker": None,
                    "content": f"<FRED {indicator} unavailable: {e}>",
                    "fetched_at": now,
                })
        return results

    def _fetch_one(self, api_key, series_id, label, start_date, end_date, now):
        # Get series metadata
        meta = requests.get(
            f"{FRED_API_BASE}/series",
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=30,
        )
        meta.raise_for_status()
        seriess = meta.json().get("seriess") or []
        if not seriess:
            raise ValueError(f"Series {series_id} not found")
        info = seriess[0]
        title = info.get("title", series_id)
        units = info.get("units_short", "")

        # Get observations
        obs = requests.get(
            f"{FRED_API_BASE}/series/observations",
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start_date,
                "observation_end": end_date,
                "sort_order": "asc",
            },
            timeout=30,
        )
        obs.raise_for_status()
        observations = obs.json().get("observations", [])

        points = [(o["date"], o["value"]) for o in observations if o.get("value") not in (".", None, "")]

        lines = [f"## FRED: {title} ({series_id})", f"- Units: {units}", f"- Window: {start_date} to {end_date}"]

        if points:
            first_date, first_val = points[0]
            last_date, last_val = points[-1]
            try:
                delta = float(last_val) - float(first_val)
                base = float(first_val)
                pct = f" ({delta / base * 100:+.2f}%)" if base != 0 else ""
                lines.append(f"\n**Latest:** {last_val} ({last_date}) | **Change:** {delta:+.2f}{pct} from {first_val} ({first_date})")
            except ValueError:
                lines.append(f"\n**Latest:** {last_val} ({last_date})")

            shown = points[-MAX_ROWS:] if len(points) > MAX_ROWS else points
            lines.append("\n| Date | Value |\n| --- | --- |")
            lines.extend(f"| {d} | {v} |" for d, v in shown)
        else:
            lines.append("\n<no observations in window>")

        return {
            "source": self.name,
            "ticker": None,
            "content": "\n".join(lines),
            "fetched_at": now,
        }
