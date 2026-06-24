"""Reddit collector — per-ticker posts across finance subreddits."""

import html
import http.client
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .base import BaseCollector

logger = logging.getLogger(__name__)

_RSS = "https://www.reddit.com/r/{sub}/search.rss?q={ticker}&restrict_sr=on&sort=new&t=week&limit={limit}"
_UA = "sentiment-robot/0.1 (+https://github.com/TauricResearch/TradingAgents)"
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strip_html(content: str) -> str:
    if not content:
        return ""
    if "<!-- SC_OFF -->" in content and "<!-- SC_ON -->" in content:
        content = content.split("<!-- SC_OFF -->")[1].split("<!-- SC_ON -->")[0]
    text = re.sub(r"<[^>]+>", " ", content)
    return " ".join(html.unescape(text).split())


class RedditCollector(BaseCollector):
    def __init__(self, config: dict):
        self._config = config

    @property
    def name(self) -> str:
        return "reddit"

    def run(self) -> list[dict]:
        results = []
        per_sub = self._config["reddit_per_sub"]
        subs = self._config["reddit_subs"]

        for ticker in self._config["watchlist"]:
            blocks = []
            total = 0
            for i, sub in enumerate(subs):
                if i > 0:
                    time.sleep(2.0)  # stay under Reddit's ~10 req/min public rate limit
                posts = self._fetch_sub(ticker, sub, per_sub)
                total += len(posts)
                if not posts:
                    blocks.append(f"r/{sub}: <no posts mentioning {ticker.upper()} in past 7 days>")
                    continue
                header = f"r/{sub} — {len(posts)} recent posts mentioning {ticker.upper()}:"
                lines = [header]
                for p in posts:
                    title = (p.get("title") or "").replace("\n", " ").strip()
                    lines.append(f"  [{p.get('date', '?')}] {title}")
                    if p.get("selftext"):
                        st = p["selftext"].replace("\n", " ").strip()
                        if len(st) > 240:
                            st = st[:240] + "…"
                        lines.append(f"    body excerpt: {st}")
                blocks.append("\n".join(lines))

            if total == 0:
                content = f"<no Reddit posts found mentioning {ticker.upper()}>"
            else:
                content = "\n\n".join(blocks)

            results.append({
                "source": self.name,
                "ticker": ticker,
                "content": content,
                "fetched_at": _now_iso(),
            })
        return results

    def _fetch_sub(self, ticker: str, sub: str, limit: int, retry: bool = True) -> list[dict]:
        url = _RSS.format(sub=sub, ticker=ticker, limit=limit)
        req = Request(url, headers={"User-Agent": _UA, "Accept": "application/atom+xml"})
        try:
            with urlopen(req, timeout=10.0) as resp:
                root = ET.fromstring(resp.read())
        except HTTPError as e:
            if e.code == 429 and retry:
                # Honor Reddit's Retry-After header, default to 5s if absent
                try:
                    wait = min(float(e.headers.get("Retry-After", 5)), 30.0)
                except (ValueError, TypeError, AttributeError):
                    wait = 5.0
                logger.warning(
                    "Reddit RSS 429 for r/%s · %s — backing off %.1fs then retrying once",
                    sub, ticker, wait,
                )
                time.sleep(wait)
                return self._fetch_sub(ticker, sub, limit, retry=False)
            logger.warning("Reddit RSS failed for r/%s · %s: HTTP %s", sub, ticker, e.code)
            return []
        except (OSError, http.client.HTTPException, ET.ParseError) as e:
            logger.warning("Reddit RSS failed for r/%s · %s: %s", sub, ticker, e)
            return []

        posts = []
        for entry in root.findall("atom:entry", _ATOM_NS)[:limit]:
            title_el = entry.find("atom:title", _ATOM_NS)
            published_el = entry.find("atom:published", _ATOM_NS)
            content_el = entry.find("atom:content", _ATOM_NS)
            pub = published_el.text if published_el is not None else ""
            posts.append({
                "title": title_el.text if title_el is not None else "",
                "date": pub.replace("T", " ")[:16] if pub else "?",
                "selftext": _strip_html(content_el.text if content_el is not None else ""),
            })
        return posts
