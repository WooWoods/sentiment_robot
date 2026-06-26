from unittest.mock import patch, MagicMock
from sentiment_robot.orchestrator import run_pipeline


def _make_config(**overrides):
    base = {
        "watchlist": ["AAPL"],
        "db_path": ":memory:",
        "output_dir": "/tmp/output",
        "llm_enabled": False,
        "feishu_webhook_url": None,
        "global_news_queries": ["test"],
        "fred_indicators": ["cpi"],
        "fred_api_key": None,
        "prediction_topics": ["test"],
        "reddit_subs": ["stocks"],
        "news_per_ticker": 5,
        "global_news_limit": 5,
        "stocktwits_per_ticker": 10,
        "reddit_per_sub": 3,
        "global_news_lookback_days": 7,
        "openai_api_key": None,
        "feishu_enabled": True,
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
    }
    base.update(overrides)
    return base


@patch("sentiment_robot.orchestrator.translate_for_feishu")
@patch("sentiment_robot.orchestrator.filter_stock_related")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
@patch("sentiment_robot.orchestrator.RedditCollector")
@patch("sentiment_robot.orchestrator.PredictionMarketsCollector")
@patch("sentiment_robot.orchestrator.FredCollector")
def test_daily_runs_all_collectors(mock_fred, mock_poly, mock_reddit, mock_st, mock_yf, mock_filter, mock_translate, tmp_db_path):
    mock_translate.return_value = None
    mock_filter.side_effect = lambda rows, config: rows
    for mock_cls in [mock_fred, mock_poly, mock_reddit, mock_st, mock_yf]:
        instance = MagicMock()
        instance.run.return_value = [
            {"source": "test", "ticker": None, "content": "data", "fetched_at": "2026-06-24T09:00:00"}
        ]
        mock_cls.return_value = instance

    config = _make_config(db_path=tmp_db_path)
    exit_code = run_pipeline("daily", config)
    assert exit_code == 0


@patch("sentiment_robot.orchestrator.translate_for_feishu")
@patch("sentiment_robot.orchestrator.filter_stock_related")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
def test_breaking_runs_only_two_collectors(mock_st, mock_yf, mock_filter, mock_translate, tmp_db_path):
    mock_translate.return_value = None
    mock_filter.side_effect = lambda rows, config: rows
    for mock_cls in [mock_st, mock_yf]:
        instance = MagicMock()
        instance.run.return_value = [
            {"source": "test", "ticker": None, "content": "data", "fetched_at": "2026-06-24T09:00:00"}
        ]
        mock_cls.return_value = instance

    config = _make_config(db_path=tmp_db_path)
    exit_code = run_pipeline("breaking", config)
    assert exit_code == 0
    mock_st.assert_called_once()
    mock_yf.assert_called_once()


@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
def test_continues_on_collector_failure(mock_st, mock_yf, tmp_db_path):
    mock_yf_instance = MagicMock()
    mock_yf_instance.name = "yfinance_news"
    mock_yf_instance.run.side_effect = Exception("Boom")
    mock_yf.return_value = mock_yf_instance

    mock_st_instance = MagicMock()
    mock_st_instance.run.return_value = [
        {"source": "stocktwits", "ticker": "AAPL", "content": "ok", "fetched_at": "2026-06-24T09:00:00"}
    ]
    mock_st.return_value = mock_st_instance

    config = _make_config(db_path=tmp_db_path)
    exit_code = run_pipeline("breaking", config)
    assert exit_code == 0  # still succeeds


@patch("sentiment_robot.orchestrator.translate_for_feishu")
@patch("sentiment_robot.orchestrator.filter_stock_related")
@patch("sentiment_robot.orchestrator.generate_report")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
def test_llm_called_when_enabled(mock_st, mock_yf, mock_reporter, mock_filter, mock_translate, tmp_db_path):
    mock_translate.return_value = None
    mock_filter.side_effect = lambda rows, config: rows
    for mock_cls in [mock_st, mock_yf]:
        instance = MagicMock()
        instance.run.return_value = [
            {"source": "test", "ticker": None, "content": "data", "fetched_at": "2026-06-24T09:00:00"}
        ]
        mock_cls.return_value = instance

    mock_reporter.return_value = {"report_type": "daily_summary", "sentiment_band": "Neutral",
                                   "sentiment_score": 5.0, "confidence": "low",
                                   "summary": "...", "markdown_path": "/tmp/out.md",
                                   "generated_at": "2026-06-24T09:05:00"}

    config = _make_config(db_path=tmp_db_path, llm_enabled=True, openai_api_key="sk-test")
    exit_code = run_pipeline("daily", config)
    assert exit_code == 0
    mock_reporter.assert_called_once()
    mock_filter.assert_called()


@patch("sentiment_robot.orchestrator.send_run_summary")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
def test_notifier_called_when_configured(mock_st, mock_yf, mock_notifier, tmp_db_path):
    for mock_cls in [mock_st, mock_yf]:
        instance = MagicMock()
        instance.run.return_value = [
            {"source": "test", "ticker": None, "content": "data", "fetched_at": "2026-06-24T09:00:00"}
        ]
        mock_cls.return_value = instance

    mock_notifier.return_value = True

    config = _make_config(db_path=tmp_db_path, feishu_webhook_url="https://hook.test")
    exit_code = run_pipeline("daily", config)
    assert exit_code == 0
    mock_notifier.assert_called_once()
