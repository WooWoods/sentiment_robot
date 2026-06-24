import json
from unittest.mock import patch, MagicMock
from sentiment_robot.collectors.stocktwits import StocktwitsCollector


def _make_config(**overrides):
    base = {"watchlist": ["AAPL"], "stocktwits_per_ticker": 30}
    base.update(overrides)
    return base


def _mock_response(messages=None):
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = json.dumps({"messages": messages or []}).encode()
    return resp


def test_collector_name():
    collector = StocktwitsCollector(_make_config())
    assert collector.name == "stocktwits"


@patch("sentiment_robot.collectors.stocktwits.urlopen")
def test_returns_list_of_dicts(mock_urlopen):
    mock_urlopen.return_value = _mock_response([
        {
            "created_at": "2026-06-24T08:00:00Z",
            "user": {"username": "trader1"},
            "entities": {"sentiment": {"basic": "Bullish"}},
            "body": "AAPL looking strong!",
        }
    ])
    collector = StocktwitsCollector(_make_config())
    results = collector.run()

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["source"] == "stocktwits"
    assert results[0]["ticker"] == "AAPL"
    assert "Bullish" in results[0]["content"]


@patch("sentiment_robot.collectors.stocktwits.urlopen")
def test_graceful_degradation(mock_urlopen):
    mock_urlopen.side_effect = OSError("Connection refused")
    collector = StocktwitsCollector(_make_config())
    results = collector.run()
    assert isinstance(results, list)
    assert "unavailable" in results[0]["content"].lower()


@patch("sentiment_robot.collectors.stocktwits.urlopen")
def test_no_messages_placeholder(mock_urlopen):
    mock_urlopen.return_value = _mock_response([])
    collector = StocktwitsCollector(_make_config())
    results = collector.run()
    assert any("no stocktwits messages" in r["content"].lower() for r in results)


@patch("sentiment_robot.collectors.stocktwits.urlopen")
def test_bullish_bearish_counts(mock_urlopen):
    msgs = [
        {"created_at": "2026-06-24T08:00:00Z", "user": {"username": "u1"},
         "entities": {"sentiment": {"basic": "Bullish"}}, "body": "up!"},
        {"created_at": "2026-06-24T08:01:00Z", "user": {"username": "u2"},
         "entities": {"sentiment": {"basic": "Bearish"}}, "body": "down!"},
        {"created_at": "2026-06-24T08:02:00Z", "user": {"username": "u3"},
         "entities": {"sentiment": {}}, "body": "meh"},
    ]
    mock_urlopen.return_value = _mock_response(msgs)
    collector = StocktwitsCollector(_make_config())
    results = collector.run()
    content = results[0]["content"]
    assert "Bullish: 1" in content
    assert "Bearish: 1" in content
    assert "Unlabeled: 1" in content
