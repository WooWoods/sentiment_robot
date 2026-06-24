"""LLM-powered report generator (optional, config-gated)."""

import json
import logging
import os
from datetime import datetime, timezone

from .storage import get_raw_for_run

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_report(db_path: str, run_id: int, config: dict) -> dict | None:
    """Generate an LLM sentiment report for a pipeline run.

    Returns None if LLM is disabled, not configured, or fails.
    Returns a report dict on success, ready for storage.insert_report().
    """
    if not config.get("llm_enabled"):
        return None

    api_key = config.get("openai_api_key")
    if not api_key:
        logger.info("LLM enabled but no OPENAI_API_KEY set — skipping report")
        return None

    raw_rows = get_raw_for_run(db_path, run_id)
    if not raw_rows:
        logger.warning("No raw data for run %d — skipping report", run_id)
        return None

    # Build prompt
    blocks = []
    for row in raw_rows:
        source = row["source"]
        ticker = row.get("ticker") or "macro"
        blocks.append(f"### {source} / {ticker}\n{row['content']}")

    data_text = "\n\n".join(blocks)

    prompt = f"""You are a financial market sentiment analyst. Analyze the following multi-source data and produce a structured market sentiment report.

## Data

{data_text}

## Instructions

Return a JSON object with these exact keys:
- overall_band: one of "Bullish", "Mildly Bullish", "Neutral", "Mixed", "Mildly Bearish", "Bearish"
- overall_score: number 0-10 (0=max bearish, 5=neutral, 10=max bullish)
- confidence: "low", "medium", or "high"
- narrative: markdown-formatted summary with source-by-source breakdown, dominant themes, catalysts and risks, and a summary table

Return ONLY the JSON object, no other text."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=config["llm_model"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        parsed = json.loads(raw)

        # Write markdown file
        output_dir = config["output_dir"]
        os.makedirs(output_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        md_path = os.path.join(output_dir, f"{date_str}-report.md")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# Market Sentiment Report — {date_str}\n\n")
            f.write(f"**Overall:** {parsed['overall_band']} | ")
            f.write(f"**Score:** {parsed['overall_score']}/10 | ")
            f.write(f"**Confidence:** {parsed['confidence']}\n\n")
            f.write(parsed["narrative"])

        return {
            "report_type": "daily_summary",
            "markdown_path": md_path,
            "sentiment_band": parsed["overall_band"],
            "sentiment_score": parsed["overall_score"],
            "confidence": parsed["confidence"],
            "summary": parsed["narrative"],
            "generated_at": _now_iso(),
        }
    except Exception as e:
        logger.warning("LLM report generation failed: %s", e)
        return None
