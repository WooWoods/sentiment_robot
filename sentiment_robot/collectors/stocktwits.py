"""StockTwits collector — per-ticker retail sentiment."""

import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from .base import BaseCollector

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "sentiment-robot/0.1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StocktwitsCollector(BaseCollector):
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "stocktwits"

    def run(self) -> list[dict]:
        results = []
        limit = self._config["stocktwits_per_ticker"]
        for ticker in self._config["watchlist"]:
            results.append(self._fetch_one(ticker, limit))
        return results

    def _fetch_one(self, ticker: str, limit: int) -> dict:
        now = _now_iso()
        url = _API.format(ticker=ticker.upper())
        req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=10.0) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            logger.warning("StockTwits fetch failed for %s: %s", ticker, e)
            return {
                "source": self.name,
                "ticker": ticker,
                "content": f"<stocktwits unavailable for {ticker}: {e}>",
                "fetched_at": now,
            }

        messages = data.get("messages", []) if isinstance(data, dict) else []
        if not messages:
            return {
                "source": self.name,
                "ticker": ticker,
                "content": f"<no StockTwits messages found for ${ticker.upper()}>",
                "fetched_at": now,
            }

        bullish = bearish = unlabeled = 0
        lines = []
        for m in messages[:limit]:
            created = m.get("created_at", "")
            user = (m.get("user") or {}).get("username", "?")
            sentiment_obj = (m.get("entities") or {}).get("sentiment") or {}
            sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
            body = (m.get("body") or "").replace("\n", " ").strip()
            if len(body) > 280:
                body = body[:280] + "…"

            if sentiment == "Bullish":
                bullish += 1
                tag = "Bullish"
            elif sentiment == "Bearish":
                bearish += 1
                tag = "Bearish"
            else:
                unlabeled += 1
                tag = "no-label"
            lines.append(f"[{created} · @{user} · {tag}] {body}")

        total = bullish + bearish + unlabeled
        bull_pct = round(100 * bullish / total) if total else 0
        bear_pct = round(100 * bearish / total) if total else 0
        summary = (
            f"Bullish: {bullish} ({bull_pct}%) · "
            f"Bearish: {bearish} ({bear_pct}%) · "
            f"Unlabeled: {unlabeled} · "
            f"Total: {total} most-recent messages"
        )
        content = summary + "\n\n" + "\n".join(lines)

        return {
            "source": self.name,
            "ticker": ticker,
            "content": content,
            "fetched_at": now,
        }
