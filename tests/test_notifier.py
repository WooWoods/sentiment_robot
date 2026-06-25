from unittest.mock import patch, MagicMock
from sentiment_robot.storage import init_db, create_run, insert_raw, insert_report
from sentiment_robot.notifier import send_run_summary


def _make_config(**overrides):
    base = {
        "feishu_webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
        "feishu_enabled": True,
    }
    base.update(overrides)
    return base


def _setup_run(db_path, run_type="daily"):
    init_db(db_path)
    run_id = create_run(db_path, run_type)
    items = [
        {
            "source": "yfinance_news", "ticker": None,
            "content": "### Fed holds rates steady (source: Reuters)\nThe Federal Reserve maintained interest rates...\n### S&P 500 reaches new high (source: Bloomberg)\nMarkets rallied on tech earnings...",
            "fetched_at": "2026-06-24T09:00:00",
        },
        {
            "source": "yfinance_news", "ticker": "AAPL",
            "content": "## AAPL News (last 7d)\n\n### Apple beats earnings estimates (source: CNBC)\nApple reported record revenue...",
            "fetched_at": "2026-06-24T09:00:00",
        },
        {
            "source": "stocktwits", "ticker": "AAPL",
            "content": "Bullish: 15 (60%) · Bearish: 5 (20%) · Unlabeled: 5 · Total: 25 most-recent messages\n\n[2026-06-24T08:00:00Z · @trader1 · Bullish] AAPL looking strong!",
            "fetched_at": "2026-06-24T09:00:00",
        },
        {
            "source": "reddit", "ticker": "SPY",
            "content": "r/wallstreetbets — 3 recent posts mentioning SPY:\n  [2026-06-23 · 420↑ · 85c] SPY 500c yolo update\n  [2026-06-22 · 180↑ · 42c] Anyone else buying SPY dips?",
            "fetched_at": "2026-06-24T09:00:00",
        },
        {
            "source": "fred", "ticker": None,
            "content": "## FRED: Consumer Price Index (CPIAUCSL)\n- Units: Index 1982-84=100\n- Window: 2025-06-24 to 2026-06-24\n\n**Latest:** 316.1 (2026-06-01) | **Change:** +0.90 (+0.29%) from 315.2 (2026-05-01)\n\n| Date | Value |\n| --- | --- |\n| 2026-05-01 | 315.2 |\n| 2026-06-01 | 316.1 |",
            "fetched_at": "2026-06-24T09:00:00",
        },
        {
            "source": "prediction_markets", "ticker": None,
            "content": "## Prediction Markets: 'Fed rate cut'\n\n### Fed cuts rates by July 2026\n  Volume: $250,001 | Ends: 2026-07-31T00:00:00Z\n    Yes: 65.0%\n    No: 35.0%\n",
            "fetched_at": "2026-06-24T09:00:00",
        },
    ]
    insert_raw(db_path, run_id, items)
    return run_id


def test_returns_false_when_no_url(tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    config = _make_config(feishu_webhook_url=None)
    result = send_run_summary(tmp_db_path, run_id, config)
    assert result is False


def test_returns_false_when_disabled(tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    config = _make_config(feishu_enabled=False)
    result = send_run_summary(tmp_db_path, run_id, config)
    assert result is False


@patch("sentiment_robot.notifier.requests.post")
def test_sends_card_on_success(mock_post, tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "success"}
    mock_post.return_value = mock_resp

    result = send_run_summary(tmp_db_path, run_id, _make_config())
    assert result is True
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args[0][0] == "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    payload = call_args[1]["json"]
    assert payload["msg_type"] == "interactive"
    card_text = str(payload["card"])
    # Chinese card title for daily mode
    assert "每日市场情绪" in card_text
    # Verify actual content is still included (titles now in Chinese)
    assert "fed holds rates steady" in card_text.lower()
    assert "apple beats earnings" in card_text.lower()
    assert "AAPL" in card_text
    assert "spy 500c yolo" in card_text.lower()
    assert "CPI" in card_text or "consumer price index" in card_text.lower()
    assert "fed cuts rates" in card_text.lower()
    # Verify StockTwits content makes it into the card
    assert "Bullish:" in card_text


@patch("sentiment_robot.notifier.requests.post")
def test_breaking_mode_uses_red_color(mock_post, tmp_db_path):
    run_id = _setup_run(tmp_db_path, run_type="breaking")
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "success"}
    mock_post.return_value = mock_resp

    result = send_run_summary(tmp_db_path, run_id, _make_config())
    assert result is True
    payload = mock_post.call_args[1]["json"]
    card_text = str(payload["card"])
    assert "red" in card_text.lower()
    assert "突发市场警报" in card_text


@patch("sentiment_robot.notifier.requests.post")
def test_handles_webhook_failure(mock_post, tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    mock_post.side_effect = Exception("Connection refused")
    result = send_run_summary(tmp_db_path, run_id, _make_config())
    assert result is False


@patch("sentiment_robot.notifier.requests.post")
def test_sends_card_with_llm_report(mock_post, tmp_db_path):
    """When LLM report exists, card shows Chinese summary as primary content."""
    run_id = _setup_run(tmp_db_path)
    # Insert a mock LLM report with Chinese content
    insert_report(tmp_db_path, run_id, {
        "report_type": "daily_summary",
        "markdown_path": "/tmp/test.md",
        "sentiment_band": "Mildly Bullish",
        "sentiment_score": 6.5,
        "confidence": "medium",
        "summary": "市场情绪温和看涨，科技股表现强劲，但宏观指标显示通胀压力仍在...",
        "generated_at": "2026-06-25T08:00:00",
    })

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"code": 0, "msg": "success"}
    mock_post.return_value = mock_resp

    result = send_run_summary(tmp_db_path, run_id, _make_config())
    assert result is True

    payload = mock_post.call_args[1]["json"]
    card_text = str(payload["card"])
    # Should contain Chinese LLM summary
    assert "市场情绪温和看涨" in card_text
    assert "科技股表现强劲" in card_text
    assert "Mildly Bullish" in card_text
    assert "6.5" in card_text
    # Should have LLM footer, not the fallback footer
    assert "LLM 自动生成" in card_text
    # Should NOT contain raw data sections (LLM summary replaces them)
    assert "头条新闻" not in card_text
    assert "StockTwits 情绪" not in card_text
