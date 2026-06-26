"""LLM-powered stock-relevance filter for news items."""

import json
import logging

logger = logging.getLogger(__name__)


def filter_stock_related(raw_rows: list[dict], config: dict) -> list[dict]:
    """Filter raw rows using LLM to keep only stock/market-related items.

    Sends all items in a single batch call, asking the LLM to return
    indices of stock-related items as a JSON array.

    Returns filtered list. On any failure, returns the original list
    unchanged (fail-open).
    """
    if not config.get("llm_filter_enabled", True):
        return raw_rows

    if not raw_rows:
        return raw_rows

    api_key = config.get("openai_api_key")
    if not api_key:
        logger.info("LLM filter enabled but no OPENAI_API_KEY -- keeping all items")
        return raw_rows

    # Build numbered items for the prompt
    items_text = []
    for i, row in enumerate(raw_rows):
        source = row["source"]
        ticker = row.get("ticker") or ""
        content = row.get("content", "")

        tag = f"[{source}]"
        if ticker:
            tag += f" [{ticker}]"
        items_text.append(f"### Item {i}\n{tag}\n{content}")

    data_text = "\n\n".join(items_text)

    prompt = f"""You are a financial news filter. Review each item below and determine if it is related to stocks, financial markets, or the economy. Return a JSON array of item indices that ARE stock/market-related.

## Criteria
An item is stock-related if it discusses:
- Individual stocks, ETFs, funds, or company earnings/results
- Market trends, indices (S&P 500, Nasdaq, Dow, etc.)
- Central bank policy, interest rates, inflation, monetary policy
- Commodities that affect financial markets (oil, gold, copper, etc.)
- Economic indicators (GDP, employment, CPI, PCE, PMI, etc.)
- Prediction markets about economic/financial topics
- Trader/investor sentiment, discussion, or strategy
- Geopolitical events with clear market/economic impact
- Corporate developments: M&A, IPOs, bankruptcies, restructuring

An item is NOT stock-related if it is primarily about:
- Entertainment, celebrities, sports (non-business)
- General technology or product news with no investment/market angle
- Random social media posts with no financial relevance
- Pure politics with no economic/financial dimension
- Lifestyle, health, or consumer tips unrelated to investing

Return ONLY a JSON array of integers, e.g. [0, 2, 5, 7]. No other text.

## Items

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
            temperature=0.0,
        )
        raw = response.choices[0].message.content or ""
        raw = raw.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.rstrip().endswith("```"):
                raw = raw.rstrip()[:-3]
            raw = raw.strip()

        indices = json.loads(raw)
        if not isinstance(indices, list):
            logger.warning("LLM filter returned non-list: %s", type(indices))
            return raw_rows

        kept = [raw_rows[i] for i in indices if 0 <= i < len(raw_rows)]
        dropped = len(raw_rows) - len(kept)
        if dropped > 0:
            logger.info(
                "LLM filter dropped %d/%d non-stock items, kept %d",
                dropped, len(raw_rows), len(kept),
            )
        return kept

    except Exception as e:
        logger.warning("LLM filter failed, keeping all %d items: %s", len(raw_rows), e)
        return raw_rows
