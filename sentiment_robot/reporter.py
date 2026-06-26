"""LLM-powered report generator (config-gated)."""

import json
import logging
import os
from datetime import datetime, timezone

from .storage import get_raw_for_run

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_report(db_path: str, run_id: int, config: dict, raw_rows: list[dict] | None = None) -> dict | None:
    """Generate an LLM sentiment report for a pipeline run.

    Args:
        db_path: Path to SQLite database.
        run_id: Pipeline run ID.
        config: Merged config dict.
        raw_rows: Optional pre-fetched filtered rows. If None, fetches from DB.

    Returns None if LLM is disabled, not configured, or fails.
    Returns a report dict on success, ready for storage.insert_report().
    """
    if not config.get("llm_enabled"):
        return None

    api_key = config.get("openai_api_key")
    if not api_key:
        logger.info("LLM enabled but no OPENAI_API_KEY set — skipping report")
        return None

    if raw_rows is None:
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

    prompt = f"""你是一位金融市场情绪分析师。请分析以下多源数据，生成一份结构化的市场情绪报告。

## 数据

{data_text}

## 指令

返回一个 JSON 对象，包含以下键（键名必须为英文）：
- overall_band: 以下之一 "Bullish"（看涨）, "Mildly Bullish"（温和看涨）, "Neutral"（中性）, "Mixed"（混合）, "Mildly Bearish"（温和看跌）, "Bearish"（看跌）
- overall_score: 数字 0-10（0=极度看跌, 5=中性, 10=极度看涨）
- confidence: "low"（低）, "medium"（中）, 或 "high"（高）
- narrative: 用中文 Markdown 格式撰写摘要，包含：各数据源逐一分析、主导主题、催化剂与风险、总结表格

只返回 JSON 对象，不要包含其他文字。"""

    try:
        from openai import OpenAI
        base_url = config.get("openai_base_url")
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)
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
            f.write(f"# 市场情绪报告 — {date_str}\n\n")
            f.write(f"**整体判断：** {parsed['overall_band']} | ")
            f.write(f"**评分：** {parsed['overall_score']}/10 | ")
            f.write(f"**置信度：** {parsed['confidence']}\n\n")
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
