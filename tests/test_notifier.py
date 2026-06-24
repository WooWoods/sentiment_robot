from unittest.mock import patch, MagicMock
from sentiment_robot.storage import init_db, create_run, insert_raw
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
        {"source": "yfinance_news", "ticker": None, "content": "Global news content...", "fetched_at": "2026-06-24T09:00:00"},
        {"source": "stocktwits", "ticker": "AAPL", "content": "Bullish: 15 Bearish: 5", "fetched_at": "2026-06-24T09:00:00"},
        {"source": "fred", "ticker": None, "content": "CPI 316.1", "fetched_at": "2026-06-24T09:00:00"},
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
    assert "daily" in str(payload["card"]).lower()


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
    assert "red" in str(payload["card"]).lower()


@patch("sentiment_robot.notifier.requests.post")
def test_handles_webhook_failure(mock_post, tmp_db_path):
    run_id = _setup_run(tmp_db_path)
    mock_post.side_effect = Exception("Connection refused")
    result = send_run_summary(tmp_db_path, run_id, _make_config())
    assert result is False
