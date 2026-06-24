"""Feishu/Lark webhook notification sender."""

import logging
from datetime import datetime, timezone

import requests

from .storage import get_raw_for_run, get_recent_runs

logger = logging.getLogger(__name__)

FEISHU_TIMEOUT = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def send_run_summary(db_path: str, run_id: int, config: dict) -> bool:
    """Send a Feishu interactive card summarizing a pipeline run.

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

    # Count by source
    sources = {}
    tickers_seen = set()
    for row in raw_rows:
        src = row["source"]
        sources[src] = sources.get(src, 0) + 1
        if row.get("ticker"):
            tickers_seen.add(row["ticker"])

    # Determine run type
    runs = get_recent_runs(db_path, limit=1)
    run_type = runs[0]["run_type"] if runs else "daily"

    is_breaking = run_type == "breaking"
    color = "red" if is_breaking else "blue"
    title = "🚨 Breaking Market Alert" if is_breaking else "📊 Daily Market Sentiment"

    source_lines = "\n".join(f"- {src}: {count} items" for src, count in sorted(sources.items()))
    ticker_text = ", ".join(sorted(tickers_seen)) if tickers_seen else "macro only"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color,
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**Time:** {now} (UTC)\n**Run ID:** {run_id}\n**Type:** {run_type}\n**Tickers scanned:** {ticker_text}"
                },
                {"tag": "hr"},
                {
                    "tag": "markdown",
                    "content": f"**Data collected:**\n{source_lines}"
                },
                {"tag": "hr"},
                {
                    "tag": "markdown",
                    "content": f"💡 Use `python -m sentiment_robot report {run_id}` to generate an LLM summary report."
                },
            ],
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
