import os
import tempfile
from unittest.mock import patch, MagicMock
from sentiment_robot.storage import init_db, create_run, insert_raw
from sentiment_robot.reporter import generate_report


def _make_config(**overrides):
    base = {
        "llm_enabled": True,
        "llm_provider": "openai",
        "llm_model": "gpt-4o-mini",
        "openai_api_key": "sk-test",
        "output_dir": "./output",
    }
    base.update(overrides)
    return base


def _setup_run(db_path):
    init_db(db_path)
    run_id = create_run(db_path, "daily")
    items = [
        {"source": "stocktwits", "ticker": "AAPL", "content": "Bullish: 20 (67%) · Bearish: 10 (33%) ...",
         "fetched_at": "2026-06-24T09:00:00"},
        {"source": "fred", "ticker": None, "content": "CPI: 316.1, +0.3% MoM",
         "fetched_at": "2026-06-24T09:00:00"},
    ]
    insert_raw(db_path, run_id, items)
    return run_id


def test_returns_none_when_llm_disabled(tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    config = _make_config(llm_enabled=False)
    result = generate_report(tmp_db_path, run_id, config)
    assert result is None


def test_returns_none_when_no_api_key(tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    config = _make_config(openai_api_key=None)
    result = generate_report(tmp_db_path, run_id, config)
    assert result is None


@patch("openai.OpenAI")
def test_generates_report_with_llm(mock_openai, tmp_db_path):
    run_id = _setup_run(tmp_db_path)

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = """{
        "overall_band": "Mildly Bullish",
        "overall_score": 6.5,
        "confidence": "medium",
        "narrative": "Market sentiment is cautiously optimistic..."
    }"""
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    with tempfile.TemporaryDirectory() as tmpdir:
        config = _make_config(output_dir=tmpdir)
        result = generate_report(tmp_db_path, run_id, config)

        assert result is not None
        assert result["report_type"] == "daily_summary"
        assert result["sentiment_band"] == "Mildly Bullish"
        assert result["sentiment_score"] == 6.5
        assert result["confidence"] == "medium"
        assert result["summary"]
        assert result["markdown_path"] is not None
        assert os.path.exists(result["markdown_path"])


@patch("openai.OpenAI")
def test_graceful_llm_failure(mock_openai, tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    mock_openai.side_effect = Exception("API error")

    config = _make_config()
    result = generate_report(tmp_db_path, run_id, config)
    assert result is None
