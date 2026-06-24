"""End-to-end pipeline test with mocked external calls."""
from unittest.mock import patch, MagicMock

from sentiment_robot.config import get_config
from sentiment_robot.orchestrator import run_pipeline
from sentiment_robot.storage import init_db, get_recent_runs, get_raw_for_run


def _make_mock_collector(name="test"):
    instance = MagicMock()
    instance.name = name
    instance.run.return_value = [
        {
            "source": name,
            "ticker": "AAPL",
            "content": f"Mocked {name} data for testing",
            "fetched_at": "2026-06-24T09:00:00",
        }
    ]
    return instance


@patch("sentiment_robot.orchestrator.PredictionMarketsCollector")
@patch("sentiment_robot.orchestrator.FredCollector")
@patch("sentiment_robot.orchestrator.RedditCollector")
@patch("sentiment_robot.orchestrator.StocktwitsCollector")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
def test_full_daily_pipeline(mock_yf, mock_st, mock_reddit, mock_fred, mock_poly, tmp_db_path):
    """Daily pipeline: all 5 collectors run, data stored, run tracked."""
    mock_yf.return_value = _make_mock_collector("yfinance_news")
    mock_st.return_value = _make_mock_collector("stocktwits")
    mock_reddit.return_value = _make_mock_collector("reddit")
    mock_fred.return_value = _make_mock_collector("fred")
    mock_poly.return_value = _make_mock_collector("prediction_markets")

    config = get_config()
    config["db_path"] = tmp_db_path

    exit_code = run_pipeline("daily", config)
    assert exit_code == 0

    # Verify run was recorded
    runs = get_recent_runs(tmp_db_path, limit=1)
    assert len(runs) == 1
    assert runs[0]["run_type"] == "daily"
    assert runs[0]["finished_at"] is not None

    # Verify data was stored
    raw = get_raw_for_run(tmp_db_path, runs[0]["id"])
    sources = {r["source"] for r in raw}
    assert sources == {"yfinance_news", "stocktwits", "reddit", "fred", "prediction_markets"}


@patch("sentiment_robot.orchestrator.StocktwitsCollector")
@patch("sentiment_robot.orchestrator.YFinanceNewsCollector")
def test_full_breaking_pipeline(mock_yf, mock_st, tmp_db_path):
    """Breaking pipeline: only 2 collectors run, data stored."""
    mock_yf.return_value = _make_mock_collector("yfinance_news")
    mock_st.return_value = _make_mock_collector("stocktwits")

    config = get_config()
    config["db_path"] = tmp_db_path

    exit_code = run_pipeline("breaking", config)
    assert exit_code == 0

    runs = get_recent_runs(tmp_db_path, limit=1)
    assert runs[0]["run_type"] == "breaking"

    raw = get_raw_for_run(tmp_db_path, runs[0]["id"])
    sources = {r["source"] for r in raw}
    assert sources == {"yfinance_news", "stocktwits"}
