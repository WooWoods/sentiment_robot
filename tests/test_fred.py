from unittest.mock import patch, MagicMock
from sentiment_robot.collectors.fred import FredCollector


def _make_config(**overrides):
    base = {"fred_api_key": "test-key", "fred_indicators": ["cpi", "vix"]}
    base.update(overrides)
    return base


_META_RESP = {
    "seriess": [{"id": "CPIAUCSL", "title": "Consumer Price Index", "units_short": "Index 1982-84=100",
                  "frequency": "Monthly", "seasonal_adjustment_short": "Seasonally Adjusted"}]
}
_OBS_RESP = {
    "observations": [
        {"date": "2026-05-01", "value": "315.2"},
        {"date": "2026-06-01", "value": "316.1"},
    ]
}


def test_collector_name():
    collector = FredCollector(_make_config())
    assert collector.name == "fred"


@patch("sentiment_robot.collectors.fred.requests.get")
def test_returns_list_of_dicts(mock_get):
    mock_meta = MagicMock()
    mock_meta.json.return_value = _META_RESP
    mock_meta.status_code = 200
    mock_obs = MagicMock()
    mock_obs.json.return_value = _OBS_RESP
    mock_obs.status_code = 200
    mock_get.side_effect = [mock_meta, mock_obs, mock_meta, mock_obs]

    collector = FredCollector(_make_config())
    results = collector.run()

    assert isinstance(results, list)
    assert len(results) == 2
    for r in results:
        assert r["source"] == "fred"
        assert r["ticker"] is None
        assert "content" in r


@patch("sentiment_robot.collectors.fred.requests.get")
def test_graceful_degradation_no_api_key(mock_get):
    collector = FredCollector(_make_config(fred_api_key=None))
    results = collector.run()
    assert len(results) == 1
    assert "not configured" in results[0]["content"].lower()


@patch("sentiment_robot.collectors.fred.requests.get")
def test_http_error_handling(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = Exception("Server error")
    mock_get.return_value = mock_resp

    collector = FredCollector(_make_config())
    results = collector.run()
    assert len(results) > 0
    for r in results:
        assert "error" in r["content"].lower() or "unavailable" in r["content"].lower()
