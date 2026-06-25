"""LLM-powered translation of raw market data into Chinese for Feishu cards."""

import logging

logger = logging.getLogger(__name__)


def translate_for_feishu(raw_rows: list[dict], config: dict) -> str | None:
    """Translate raw market data into a Chinese markdown summary for Feishu.

    Groups rows by source, builds a structured prompt, and calls the LLM to
    produce per-item Chinese translations with section headers.

    Returns a markdown string ready for Feishu card display, or None on failure.
    """
    if not config.get("llm_enabled"):
        return None

    api_key = config.get("openai_api_key")
    if not api_key:
        logger.info("LLM enabled but no OPENAI_API_KEY -- skipping translation")
        return None

    if not raw_rows:
        return None

    # Build a structured data block for the prompt
    blocks = []
    for row in raw_rows:
        source = row["source"]
        ticker = row.get("ticker")
        content = row.get("content", "")

        tag = f"[{source}]"
        if ticker:
            tag += f" [{ticker}]"
        blocks.append(f"{tag}\n{content}")

    data_text = "\n\n---\n\n".join(blocks)

    prompt = f"""你是一位财经新闻编辑。请阅读以下每条市场数据的完整内容（包括标题和正文），将每条内容归纳为50-100字的中文摘要，用于飞书消息推送。

## 规则
- 阅读每条数据的完整内容（标题 + 正文），理解其核心信息，不要只翻译标题
- 每条摘要50-100个中文字符：简洁但信息完整，包含关键数据（数字、百分比、趋势方向）
- 按数据源分组展示，使用以下 Markdown 格式：
  - **📰 头条新闻** — yfinance_news 的内容
  - **💬 StockTwits 情绪** — stocktwits 的内容
  - **🐦 Reddit 讨论** — reddit 的内容
  - **🏛️ 宏观指标** — fred 的内容
  - **🎲 预测市场** — prediction_markets 的内容
- 如果某个数据源没有内容，跳过该分组
- 每条摘要一行，以 "- " 开头
- 直接返回 Markdown 文本，不要 JSON，不要代码块包裹

## 数据

{data_text}"""

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
        return raw.strip()
    except Exception as e:
        logger.warning("LLM translation failed: %s", e)
        return None
