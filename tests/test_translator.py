"""Tests for sentiment_robot.translator."""
from unittest.mock import patch, MagicMock
from sentiment_robot.translator import translate_for_feishu


def _make_config(**overrides):
    base = {
        "llm_enabled": True,
        "llm_model": "gpt-4o-mini",
        "openai_api_key": "sk-test",
        "openai_base_url": None,
    }
    base.update(overrides)
    return base


def _make_raw_rows():
    return [
        {
            "source": "yfinance_news", "ticker": None,
            "content": "### Fed holds rates steady (source: Reuters)\nThe Federal Reserve maintained rates...",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "yfinance_news", "ticker": "AAPL",
            "content": "### Apple beats earnings (source: CNBC)\nApple reported record revenue...",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "stocktwits", "ticker": "SPY",
            "content": "Bullish: 15 (60%) · Bearish: 5 (20%) · Unlabeled: 5 · Total: 25",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "reddit", "ticker": "SPY",
            "content": "r/wallstreetbets:\n  [2026-06-24 · 420↑ · 85c] SPY 500c yolo update",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "fred", "ticker": None,
            "content": "## FRED: CPI (CPIAUCSL)\n**Latest:** 316.1 (2026-06-01) | **Change:** +0.90 (+0.29%)",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "prediction_markets", "ticker": None,
            "content": "### Fed cuts rates by July 2026\n  Yes: 65.0%\n  No: 35.0%",
            "fetched_at": "2026-06-25T08:00:00",
        },
    ]


def test_returns_none_when_llm_disabled():
    config = _make_config(llm_enabled=False)
    result = translate_for_feishu(_make_raw_rows(), config)
    assert result is None


def test_returns_none_when_no_api_key():
    config = _make_config(openai_api_key=None)
    result = translate_for_feishu(_make_raw_rows(), config)
    assert result is None


def test_returns_none_when_empty_rows():
    config = _make_config()
    result = translate_for_feishu([], config)
    assert result is None


@patch("openai.OpenAI")
def test_translates_raw_rows_to_chinese(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = (
        "**\U0001f4f0 头条新闻**\n"
        "- 美联储维持利率不变\n"
        "- 苹果财报超预期，营收创纪录\n\n"
        "**\U0001f4ac StockTwits 情绪**\n"
        "- SPY: 看涨 60% · 看跌 20%\n\n"
        "**\U0001f426 Reddit 讨论**\n"
        "- SPY 500c yolo 更新\n\n"
        "**\U0001f3db️ 宏观指标**\n"
        "- CPI: 316.1，环比+0.29%\n\n"
        "**\U0001f3b2 预测市场**\n"
        "- 美联储7月前降息: 是 65.0%"
    )
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    result = translate_for_feishu(_make_raw_rows(), _make_config())
    assert result is not None
    assert "美联储维持利率不变" in result
    assert "苹果财报超预期" in result
    assert "SPY" in result
    assert "CPI" in result
    assert "降息" in result
    # Verify the prompt was called with raw content
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    assert "Fed holds rates steady" in messages[0]["content"]
    assert "Apple beats earnings" in messages[0]["content"]


@patch("openai.OpenAI")
def test_graceful_llm_failure(mock_openai):
    mock_openai.side_effect = Exception("API error")
    result = translate_for_feishu(_make_raw_rows(), _make_config())
    assert result is None
