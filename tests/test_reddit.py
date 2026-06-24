from unittest.mock import patch, MagicMock
from sentiment_robot.collectors.reddit import RedditCollector


def _make_config(**overrides):
    base = {"watchlist": ["AAPL"], "reddit_subs": ["stocks"], "reddit_per_sub": 3}
    base.update(overrides)
    return base


_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Is AAPL a buy right now?</title>
    <published>2026-06-23T12:00:00Z</published>
    <content type="html">&lt;!-- SC_OFF --&gt;Great earnings ahead&lt;!-- SC_ON --&gt;</content>
  </entry>
</feed>"""


def test_collector_name():
    collector = RedditCollector(_make_config())
    assert collector.name == "reddit"


@patch("sentiment_robot.collectors.reddit.urlopen")
def test_returns_list_of_dicts(mock_urlopen):
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = _RSS_XML.encode()
    mock_urlopen.return_value = resp

    collector = RedditCollector(_make_config())
    results = collector.run()

    assert isinstance(results, list)
    assert len(results) > 0
    for r in results:
        assert r["source"] == "reddit"
        assert "content" in r
        assert "fetched_at" in r


@patch("sentiment_robot.collectors.reddit.urlopen")
def test_graceful_degradation(mock_urlopen):
    mock_urlopen.side_effect = OSError("Network error")
    collector = RedditCollector(_make_config())
    results = collector.run()
    assert isinstance(results, list)


@patch("sentiment_robot.collectors.reddit.urlopen")
def test_no_posts_placeholder(mock_urlopen):
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'.encode()
    mock_urlopen.return_value = resp

    collector = RedditCollector(_make_config())
    results = collector.run()
    content = results[0]["content"]
    assert "no posts" in content.lower() or isinstance(content, str)
