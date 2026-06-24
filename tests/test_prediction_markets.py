from unittest.mock import patch, MagicMock
from sentiment_robot.collectors.prediction_markets import PredictionMarketsCollector


def _make_config(**overrides):
    base = {"prediction_topics": ["Fed rate cut", "recession"]}
    base.update(overrides)
    return base


def _mock_polymarket_response():
    return [
        {
            "id": "1",
            "title": "Fed cuts rates by July 2026",
            "outcomes": '[{"outcome": "Yes", "price": 0.65}, {"outcome": "No", "price": 0.35}]',
            "volume": "250000.50",
            "endDate": "2026-07-31T00:00:00Z",
        }
    ]


def test_collector_name():
    collector = PredictionMarketsCollector(_make_config())
    assert collector.name == "prediction_markets"


@patch("sentiment_robot.collectors.prediction_markets.requests.get")
def test_returns_list_of_dicts(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = _mock_polymarket_response()
    mock_get.return_value = mock_resp

    collector = PredictionMarketsCollector(_make_config(prediction_topics=["Fed rate cut"]))
    results = collector.run()

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["source"] == "prediction_markets"
    assert results[0]["ticker"] is None
    assert "Fed cuts rates" in results[0]["content"]


@patch("sentiment_robot.collectors.prediction_markets.requests.get")
def test_graceful_degradation(mock_get):
    mock_get.side_effect = Exception("Network error")
    collector = PredictionMarketsCollector(_make_config())
    results = collector.run()
    assert isinstance(results, list)
    assert "unavailable" in results[0]["content"].lower()
