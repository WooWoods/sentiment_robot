"""Tests for sentiment_robot.filter."""
from unittest.mock import patch, MagicMock
from sentiment_robot.filter import filter_stock_related


def _make_config(**overrides):
    base = {
        "llm_filter_enabled": True,
        "llm_model": "gpt-4o-mini",
        "openai_api_key": "sk-test",
        "openai_base_url": None,
    }
    base.update(overrides)
    return base


def _make_raw_rows():
    return [
        {
            "source": "yfinance_news", "ticker": None,
            "content": "### Fed holds rates steady\nFederal Reserve maintained rates...",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "yfinance_news", "ticker": "AAPL",
            "content": "### Apple beats earnings\nApple reported record revenue...",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "stocktwits", "ticker": "SPY",
            "content": "Bullish: 15 (60%) · Bearish: 5 (20%)",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "reddit", "ticker": "SPY",
            "content": "SPY 500c yolo update — 420 upvotes",
            "fetched_at": "2026-06-25T08:00:00",
        },
        {
            "source": "fred", "ticker": None,
            "content": "## FRED: CPI\n**Latest:** 316.1 | **Change:** +0.29%",
            "fetched_at": "2026-06-25T08:00:00",
        },
    ]


def test_returns_all_when_filter_disabled():
    rows = _make_raw_rows()
    config = _make_config(llm_filter_enabled=False)
    result = filter_stock_related(rows, config)
    assert result is rows  # same list object, no filtering


def test_returns_all_when_empty_rows():
    config = _make_config()
    result = filter_stock_related([], config)
    assert result == []


def test_returns_all_when_no_api_key():
    rows = _make_raw_rows()
    config = _make_config(openai_api_key=None)
    result = filter_stock_related(rows, config)
    assert result is rows


@patch("openai.OpenAI")
def test_filters_correctly(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    # LLM says items 0, 1, 2, 4 are stock-related (item 3 is dropped)
    mock_response.choices[0].message.content = "[0, 1, 2, 4]"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())

    assert len(result) == 4
    sources = [r["source"] for r in result]
    assert "reddit" not in sources  # item 3 was dropped
    assert "yfinance_news" in sources
    assert "stocktwits" in sources
    assert "fred" in sources

    # Verify prompt contains item content
    call_args = mock_client.chat.completions.create.call_args
    messages = call_args[1]["messages"]
    prompt_text = messages[0]["content"]
    assert "Fed holds rates steady" in prompt_text
    assert "Apple beats earnings" in prompt_text
    assert "### Item 0" in prompt_text
    assert "### Item 4" in prompt_text


@patch("openai.OpenAI")
def test_handles_markdown_fence_response(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "```json\n[0, 1, 4]\n```"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())
    assert len(result) == 3


@patch("openai.OpenAI")
def test_fail_open_on_llm_error(mock_openai):
    mock_openai.side_effect = Exception("API error")
    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())
    assert result is rows  # unchanged on failure


@patch("openai.OpenAI")
def test_fail_open_on_bad_response(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "not a json array"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())
    assert result is rows  # unchanged on parse failure


@patch("openai.OpenAI")
def test_all_items_kept_when_all_relevant(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "[0, 1, 2, 3, 4]"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())
    assert len(result) == 5


@patch("openai.OpenAI")
def test_out_of_range_indices_ignored(mock_openai):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "[0, 99, 2]"
    mock_client.chat.completions.create.return_value = mock_response
    mock_openai.return_value = mock_client

    rows = _make_raw_rows()
    result = filter_stock_related(rows, _make_config())
    assert len(result) == 2  # 99 ignored, keeps 0 and 2
