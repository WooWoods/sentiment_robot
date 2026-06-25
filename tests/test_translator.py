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
        "- 美联储在最新会议上决定维持基准利率不变，鲍威尔强调需看到更多通胀降温证据才会考虑降息，市场对年内降息预期有所回落。\n"
        "- 苹果公司最新季度财报超出华尔街预期，iPhone和服务业务收入均创历史新高，大中华区表现尤其强劲，推动股价盘后上涨5%。\n\n"
        "**\U0001f4ac StockTwits 情绪**\n"
        "- SPY: 看涨情绪占60%（15条），看跌仅20%（5条），整体偏向乐观，散户对大盘短期走势信心较强。\n\n"
        "**\U0001f426 Reddit 讨论**\n"
        "- 用户在r/wallstreetbets发帖讨论SPY 500c期权策略，获得420点赞和85条评论，市场关注大盘指数看涨期权的风险收益比。\n\n"
        "**\U0001f3db️ 宏观指标**\n"
        "- 消费者价格指数CPI最新读数为316.1，环比上涨0.29%，同比涨幅虽有放缓但仍高于美联储2%目标水平。\n\n"
        "**\U0001f3b2 预测市场**\n"
        "- 预测市场显示美联储在7月会议前降息的概率为65%，市场对宽松政策启动时点的博弈持续升温。"
    )
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    result = translate_for_feishu(_make_raw_rows(), _make_config())
    assert result is not None
    assert "美联储" in result
    assert "苹果" in result
    assert "SPY" in result
    assert "CPI" in result
    assert "降息" in result
    # Verify the prompt was called with raw content
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    assert "Fed holds rates steady" in messages[0]["content"]
    assert "Apple beats earnings" in messages[0]["content"]
    # Verify new prompt instructions are present
    assert "50-100" in messages[0]["content"]
    assert "完整内容" in messages[0]["content"]
    assert "不要只翻译标题" in messages[0]["content"]


@patch("openai.OpenAI")
def test_graceful_llm_failure(mock_openai):
    mock_openai.side_effect = Exception("API error")
    result = translate_for_feishu(_make_raw_rows(), _make_config())
    assert result is None
