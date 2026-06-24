import sys
from unittest.mock import patch, MagicMock
from sentiment_robot.cli import main


@patch("sentiment_robot.cli.run_pipeline")
@patch("sentiment_robot.cli.get_config")
def test_daily_subcommand(mock_config, mock_pipeline, tmp_db_path):
    mock_config.return_value = {"db_path": tmp_db_path, "output_dir": "/tmp"}
    mock_pipeline.return_value = 0

    sys.argv = ["sentiment_robot", "daily"]
    exit_code = main()
    assert exit_code == 0
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args[0][0] == "daily"


@patch("sentiment_robot.cli.run_pipeline")
@patch("sentiment_robot.cli.get_config")
def test_breaking_subcommand(mock_config, mock_pipeline, tmp_db_path):
    mock_config.return_value = {"db_path": tmp_db_path, "output_dir": "/tmp"}
    mock_pipeline.return_value = 0

    sys.argv = ["sentiment_robot", "breaking"]
    exit_code = main()
    assert exit_code == 0
    mock_pipeline.assert_called_once()
    assert mock_pipeline.call_args[0][0] == "breaking"


@patch("sentiment_robot.cli.do_report")
@patch("sentiment_robot.cli.insert_report")
@patch("sentiment_robot.cli.get_config")
def test_report_subcommand(mock_config, mock_insert, mock_generate, tmp_db_path):
    mock_config.return_value = {
        "db_path": tmp_db_path,
        "output_dir": "/tmp",
        "llm_enabled": True,
        "openai_api_key": "sk-test",
        "llm_model": "gpt-4o-mini",
        "llm_provider": "openai",
    }
    mock_generate.return_value = {
        "report_type": "daily_summary",
        "markdown_path": "/tmp/2026-06-24-report.md",
        "sentiment_band": "Neutral",
        "sentiment_score": 5.0,
        "confidence": "low",
        "summary": "Report content",
        "generated_at": "2026-06-24T09:00:00",
    }

    sys.argv = ["sentiment_robot", "report", "1"]
    exit_code = main()
    assert exit_code == 0
    mock_generate.assert_called_once()
    mock_insert.assert_called_once()


@patch("sentiment_robot.cli.get_config")
def test_setup_db_subcommand(mock_config, tmp_db_path):
    mock_config.return_value = {"db_path": tmp_db_path}
    sys.argv = ["sentiment_robot", "setup-db"]
    exit_code = main()
    assert exit_code == 0
    import sqlite3
    conn = sqlite3.connect(tmp_db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    conn.close()
    assert len(tables) == 3
