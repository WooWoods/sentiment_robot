"""Yahoo Finance news collector — global + per-ticker."""

import contextlib
import logging
from datetime import datetime, timedelta, timezone

import yfinance as yf

from .base import BaseCollector

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_article(article: dict) -> dict | None:
    """Extract title/summary/publisher/date from yfinance article (nested or flat)."""
    if "content" in article:
        c = article["content"]
        title = c.get("title", "No title")
        summary = c.get("summary", "")
        publisher = (c.get("provider") or {}).get("displayName", "Unknown")
        link = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url", "")
        pub_str = c.get("pubDate", "")
    else:
        title = article.get("title", "No title")
        summary = article.get("summary", "")
        publisher = article.get("publisher", "Unknown")
        link = article.get("link", "")
        pub_str = ""

    pub_date = None
    if pub_str:
        with contextlib.suppress(ValueError):
            pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))

    return {"title": title, "summary": summary, "publisher": publisher, "link": link, "pub_date": pub_date}


def _in_window(pub_date, start_dt: datetime, end_dt: datetime) -> bool:
    if pub_date is not None:
        naive = pub_date.replace(tzinfo=None)
        return start_dt <= naive <= end_dt
    return True


def _format_article(a: dict) -> str:
    lines = [f"### {a['title']} (source: {a['publisher']})"]
    if a["summary"]:
        lines.append(a["summary"])
    if a["link"]:
        lines.append(f"Link: {a['link']}")
    return "\n".join(lines)


class YFinanceNewsCollector(BaseCollector):
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "yfinance_news"

    def run(self) -> list[dict]:
        results = []
        now = _now_iso()
        lookback = self._config["global_news_lookback_days"]
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=lookback)

        # 1. Global news
        results.extend(self._fetch_global(start_dt, end_dt, now))

        # 2. Per-ticker news
        for ticker in self._config["watchlist"]:
            results.extend(self._fetch_ticker_news(ticker, start_dt, end_dt, now))

        return results

    def _fetch_global(self, start_dt, end_dt, now: str) -> list[dict]:
        results = []
        limit = self._config["global_news_limit"]
        seen = set()
        try:
            for query in self._config["global_news_queries"]:
                search = yf.Search(query=query, news_count=limit, enable_fuzzy_query=True)
                if not search.news:
                    continue
                for article in search.news:
                    a = _extract_article(article)
                    if a is None or a["title"] in seen:
                        continue
                    if not _in_window(a["pub_date"], start_dt, end_dt):
                        continue
                    seen.add(a["title"])
                    results.append({
                        "source": self.name,
                        "ticker": None,
                        "content": _format_article(a),
                        "fetched_at": now,
                    })
                    if len(results) >= limit:
                        break
                if len(results) >= limit:
                    break

            if not results:
                results.append({
                    "source": self.name,
                    "ticker": None,
                    "content": f"<no global news found between {start_dt:%Y-%m-%d} and {end_dt:%Y-%m-%d}>",
                    "fetched_at": now,
                })
        except Exception as e:
            logger.warning("Global news fetch failed: %s", e)
            results.append({
                "source": self.name,
                "ticker": None,
                "content": f"<global news unavailable: {e}>",
                "fetched_at": now,
            })
        return results

    def _fetch_ticker_news(self, ticker: str, start_dt, end_dt, now: str) -> list[dict]:
        results = []
        limit = self._config["news_per_ticker"]
        try:
            stock = yf.Ticker(ticker)
            news = stock.get_news(count=limit)
            if not news:
                results.append({
                    "source": self.name,
                    "ticker": ticker,
                    "content": f"<no news found for {ticker}>",
                    "fetched_at": now,
                })
                return results

            kept = []
            for article in news:
                a = _extract_article(article)
                if a is None or not _in_window(a["pub_date"], start_dt, end_dt):
                    continue
                kept.append(a)
                if len(kept) >= limit:
                    break

            if kept:
                content = f"## {ticker} News (last {self._config['global_news_lookback_days']}d)\n\n"
                content += "\n\n".join(_format_article(a) for a in kept)
            else:
                content = f"<no dated news for {ticker} in window>"

            results.append({
                "source": self.name,
                "ticker": ticker,
                "content": content,
                "fetched_at": now,
            })
        except Exception as e:
            logger.warning("News fetch failed for %s: %s", ticker, e)
            results.append({
                "source": self.name,
                "ticker": ticker,
                "content": f"<news unavailable for {ticker}: {e}>",
                "fetched_at": now,
            })
        return results
