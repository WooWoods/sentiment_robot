"""Polymarket prediction markets collector."""

import json
import logging
from datetime import datetime, timezone

import requests

from .base import BaseCollector

logger = logging.getLogger(__name__)

POLYMARKET_API = "https://gamma-api.polymarket.com/events"
_UA = "sentiment-robot/0.1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PredictionMarketsCollector(BaseCollector):
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "prediction_markets"

    def run(self) -> list[dict]:
        topics = self._config["prediction_topics"]
        now = _now_iso()
        results = []

        for topic in topics:
            try:
                resp = requests.get(
                    POLYMARKET_API,
                    params={"search": topic, "limit": 5, "active": "true"},
                    headers={"User-Agent": _UA},
                    timeout=15,
                )
                resp.raise_for_status()
                markets = resp.json()

                if not markets:
                    results.append({
                        "source": self.name,
                        "ticker": None,
                        "content": f"<no Polymarket events found for '{topic}'>",
                        "fetched_at": now,
                    })
                    continue

                lines = [f"## Prediction Markets: '{topic}'", ""]
                for m in markets[:5]:
                    title = m.get("title", "Unknown")
                    volume = float(m.get("volume", 0) or 0)
                    end_date = m.get("endDate", "?")
                    outcomes_str = m.get("outcomes", "[]")
                    try:
                        outcomes = json.loads(outcomes_str) if isinstance(outcomes_str, str) else outcomes_str
                    except json.JSONDecodeError:
                        outcomes = []
                    outcome_lines = []
                    for o in outcomes:
                        name = o.get("outcome", o.get("option", "?"))
                        price = o.get("price", 0)
                        outcome_lines.append(f"    {name}: {float(price)*100:.1f}%")
                    lines.append(f"### {title}")
                    lines.append(f"  Volume: ${volume:,.0f} | Ends: {end_date}")
                    lines.extend(outcome_lines)
                    lines.append("")

                results.append({
                    "source": self.name,
                    "ticker": None,
                    "content": "\n".join(lines),
                    "fetched_at": now,
                })
            except Exception as e:
                logger.warning("Polymarket fetch failed for '%s': %s", topic, e)
                results.append({
                    "source": self.name,
                    "ticker": None,
                    "content": f"<prediction markets unavailable for '{topic}': {e}>",
                    "fetched_at": now,
                })
        return results
