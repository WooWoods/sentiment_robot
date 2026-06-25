"""Feishu/Lark webhook notification sender."""

import logging
import re
from datetime import datetime, timezone

import requests

from .storage import get_raw_for_run, get_recent_runs

logger = logging.getLogger(__name__)

FEISHU_TIMEOUT = 10
# Feishu card markdown elements have a practical ~4KB content limit per element
MAX_SECTION_CHARS = 3000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_headlines(rows: list[dict], source: str, ticker: str | None = None) -> list[str]:
    """Extract key lines from raw content for a given source."""
    headlines = []
    for row in rows:
        if row["source"] != source:
            continue
        if ticker is not None and row.get("ticker") != ticker:
            continue
        content = row.get("content", "")
        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue
            # Skip markdown headers, hr, table rows, and placeholder messages
            if line.startswith("## ") or line.startswith("|") or line.startswith("<"):
                continue
            if line.startswith("### "):
                headlines.append(line[4:])
            elif line.startswith("[") and "]" in line[:30]:
                # StockTwits: [timestamp · @user · tag] body
                headlines.append(line)
            elif line.startswith("Bullish:") or line.startswith("Bearish:"):
                headlines.append(line)
            elif re.match(r"^\d", line):
                continue  # skip pure numbers
        if headlines:
            break  # first non-empty match per row
    return headlines


def _build_news_section(rows: list[dict], max_items: int = 6) -> str:
    """Extract top news headlines from yfinance_news rows."""
    lines = ["**📰 头条新闻**"]
    count = 0
    for row in rows:
        if row["source"] != "yfinance_news":
            continue
        content = row.get("content", "")
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("### "):
                headline = line[4:]
                ticker_tag = f" [{row.get('ticker', '')}]" if row.get("ticker") else ""
                lines.append(f"- {headline}{ticker_tag}")
                count += 1
                if count >= max_items:
                    break
        if count >= max_items:
            break
    return "\n".join(lines) if count > 0 else ""


def _build_stocktwits_section(rows: list[dict], max_tickers: int = 5) -> str:
    """Extract bullish/bearish ratios per ticker from StockTwits."""
    lines = ["**💬 StockTwits 情绪**"]
    count = 0
    for row in rows:
        if row["source"] != "stocktwits":
            continue
        content = row.get("content", "")
        ticker = row.get("ticker", "?")
        # First line is the summary: "Bullish: N (X%) · Bearish: N (Y%) · Unlabeled: N · Total: N"
        summary_line = content.split("\n")[0] if content else ""
        if summary_line and "Bullish:" in summary_line:
            lines.append(f"- **{ticker}**: {summary_line}")
            count += 1
            if count >= max_tickers:
                break
    return "\n".join(lines) if count > 0 else ""


def _build_reddit_section(rows: list[dict], max_posts: int = 5) -> str:
    """Extract top Reddit post titles."""
    lines = ["**🐦 Reddit 讨论**"]
    count = 0
    for row in rows:
        if row["source"] != "reddit":
            continue
        content = row.get("content", "")
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[") and "] " in stripped[:30]:
                # Format: "  [2026-06-23 · 42↑ · 15c] Post title here"
                lines.append(f"- {stripped.lstrip()}")
                count += 1
                if count >= max_posts:
                    break
        if count >= max_posts:
            break
    return "\n".join(lines) if count > 0 else ""


def _build_fred_section(rows: list[dict], max_indicators: int = 6) -> str:
    """Extract key macro indicator values from FRED."""
    lines = ["**🏛️ 宏观指标 (FRED)**"]
    count = 0
    for row in rows:
        if row["source"] != "fred":
            continue
        content = row.get("content", "")
        indicator_name = ""
        for line in content.split("\n"):
            stripped = line.strip()
            # Capture series title from header
            if stripped.startswith("## FRED: "):
                indicator_name = stripped[8:].split("(")[0].strip()
            elif stripped.startswith("**Latest:**") and indicator_name:
                lines.append(f"- **{indicator_name}**: {stripped}")
                count += 1
                indicator_name = ""
                if count >= max_indicators:
                    break
        if count >= max_indicators:
            break
    return "\n".join(lines) if count > 0 else ""


def _build_prediction_section(rows: list[dict], max_markets: int = 6) -> str:
    """Extract top prediction market probabilities."""
    lines = ["**🎲 预测市场**"]
    count = 0
    for row in rows:
        if row["source"] != "prediction_markets":
            continue
        content = row.get("content", "")
        in_market = False
        current_title = ""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("### "):
                current_title = stripped[4:]
                in_market = True
            elif in_market and "%" in stripped:
                lines.append(f"- {current_title}: {stripped.strip()}")
                count += 1
                in_market = False
                if count >= max_markets:
                    break
        if count >= max_markets:
            break
    return "\n".join(lines) if count > 0 else ""


def _truncate(text: str, max_chars: int = MAX_SECTION_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…(truncated)"


def send_run_summary(db_path: str, run_id: int, config: dict) -> bool:
    """Send a Feishu interactive card with actual news and sentiment highlights.

    Returns True if the message was sent successfully.
    """
    webhook_url = config.get("feishu_webhook_url")
    if not webhook_url:
        logger.info("No FEISHU_WEBHOOK_URL configured — skipping notification")
        return False

    if not config.get("feishu_enabled", True):
        logger.info("Feishu notifications disabled in config")
        return False

    raw_rows = get_raw_for_run(db_path, run_id)
    if not raw_rows:
        logger.warning("No raw data for run %d — skipping notification", run_id)
        return False

    # Determine run type
    runs = get_recent_runs(db_path, limit=1)
    run_type = runs[0]["run_type"] if runs else "daily"

    is_breaking = run_type == "breaking"
    color = "red" if is_breaking else "blue"
    title = "🚨 突发市场警报" if is_breaking else "📊 每日市场情绪"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build card elements with actual content
    elements = [
        {
            "tag": "markdown",
            "content": f"**{now} UTC** · 运行 #{run_id} · {run_type.upper()}",
        },
    ]

    # News headlines (most important — show first)
    news_section = _build_news_section(raw_rows)
    if news_section:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": _truncate(news_section)})

    # StockTwits sentiment ratios
    st_section = _build_stocktwits_section(raw_rows)
    if st_section:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": _truncate(st_section)})

    # Reddit hot posts
    reddit_section = _build_reddit_section(raw_rows)
    if reddit_section:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": _truncate(reddit_section)})

    # Macro indicators
    fred_section = _build_fred_section(raw_rows)
    if fred_section:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": _truncate(fred_section)})

    # Prediction markets
    pred_section = _build_prediction_section(raw_rows)
    if pred_section:
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": _truncate(pred_section)})

    # Footer
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": f"💡 `python -m sentiment_robot report {run_id}` 查看 LLM 中文摘要",
    })

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color,
            },
            "elements": elements,
        },
    }

    try:
        resp = requests.post(webhook_url, json=card, timeout=FEISHU_TIMEOUT)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            logger.warning("Feishu webhook returned error: %s", body)
            return False
        logger.info("Feishu notification sent for run %d", run_id)
        return True
    except Exception as e:
        logger.warning("Failed to send Feishu notification: %s", e)
        return False
