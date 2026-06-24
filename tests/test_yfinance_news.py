from unittest.mock import MagicMock, patch
from sentiment_robot.collectors.yfinance_news import YFinanceNewsCollector


def _make_config(**overrides):
    base = {
        "watchlist": ["AAPL", "MSFT"],
        "global_news_queries": ["Federal Reserve rates"],
        "news_per_ticker": 3,
        "global_news_limit": 2,
        "global_news_lookback_days": 7,
    }
    base.update(overrides)
    return base


@patch("sentiment_robot.collectors.yfinance_news.yf")
def test_collector_name(mock_yf):
    collector = YFinanceNewsCollector(_make_config())
    assert collector.name == "yfinance_news"


@patch("sentiment_robot.collectors.yfinance_news.yf")
def test_returns_list_of_dicts(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.get_news.return_value = [
        {"content": {"title": "AAPL up", "summary": "Apple rises", "pubDate": "2026-06-23T12:00:00Z",
                     "provider": {"displayName": "Bloomberg"},
                     "canonicalUrl": {"url": "https://example.com/aapl"}}}
    ]
    mock_yf.Ticker.return_value = mock_ticker

    mock_search = MagicMock()
    mock_search.news = [
        {"content": {"title": "Fed holds rates", "summary": "No change", "pubDate": "2026-06-23T12:00:00Z",
                     "provider": {"displayName": "Reuters"},
                     "canonicalUrl": {"url": "https://example.com/fed"}}}
    ]
    mock_yf.Search.return_value = mock_search

    config = _make_config()
    collector = YFinanceNewsCollector(config)
    results = collector.run()

    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert r["source"] == "yfinance_news"
        assert "content" in r
        assert "fetched_at" in r


@patch("sentiment_robot.collectors.yfinance_news.yf")
def test_graceful_degradation_on_error(mock_yf):
    mock_yf.Ticker.side_effect = Exception("Network error")
    mock_yf.Search.side_effect = Exception("Search failed")

    config = _make_config()
    collector = YFinanceNewsCollector(config)
    results = collector.run()

    assert isinstance(results, list)


@patch("sentiment_robot.collectors.yfinance_news.yf")
def test_per_ticker_news_structure(mock_yf):
    mock_ticker = MagicMock()
    mock_ticker.get_news.return_value = [
        {"content": {"title": "MSFT earnings", "summary": "Beat estimates", "pubDate": "2026-06-23T12:00:00Z",
                     "provider": {"displayName": "CNBC"},
                     "canonicalUrl": {"url": "https://example.com/msft"}}}
    ]
    mock_yf.Ticker.return_value = mock_ticker
    mock_search = MagicMock()
    mock_search.news = []
    mock_yf.Search.return_value = mock_search

    config = _make_config()
    collector = YFinanceNewsCollector(config)
    results = collector.run()

    msft_results = [r for r in results if r["ticker"] == "MSFT"]
    assert len(msft_results) > 0
    assert "MSFT earnings" in msft_results[0]["content"]
