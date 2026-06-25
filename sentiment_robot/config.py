"""Configuration with environment variable overrides."""

import os
from copy import deepcopy

DEFAULT_CONFIG = {
    "watchlist": ["SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL"],
    "global_news_queries": [
        "Federal Reserve interest rates inflation",
        "S&P 500 earnings GDP economic outlook",
        "geopolitical risk trade war sanctions",
        "ECB Bank of England BOJ central bank policy",
        "oil commodities supply chain energy",
    ],
    "fred_indicators": [
        "fed_funds_rate", "10y_treasury", "cpi", "core_pce",
        "unemployment", "vix", "yield_curve", "real_gdp",
    ],
    "prediction_topics": ["Fed rate cut", "recession", "US election", "oil prices"],
    "reddit_subs": ["wallstreetbets", "stocks", "investing", "StockMarket"],
    "llm_enabled": True,
    "llm_provider": "openai",
    "llm_model": "gpt-4o-mini",
    "openai_api_key": None,
    "openai_base_url": None,
    "fred_api_key": None,
    "news_per_ticker": 10,
    "global_news_limit": 15,
    "stocktwits_per_ticker": 30,
    "reddit_per_sub": 5,
    "global_news_lookback_days": 7,
    "output_dir": "./output",
    "db_path": "./sentiment_robot.db",
    "feishu_webhook_url": None,
    "feishu_enabled": True,
}

_ENV_MAP = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "SENTIMENT_ROBOT_LLM_MODEL": "llm_model",
    "FRED_API_KEY": "fred_api_key",
    "FEISHU_WEBHOOK_URL": "feishu_webhook_url",
    "SENTIMENT_ROBOT_LLM_ENABLED": "llm_enabled",
    "SENTIMENT_ROBOT_DB_PATH": "db_path",
    "SENTIMENT_ROBOT_OUTPUT_DIR": "output_dir",
}

_BOOL_TRUE = frozenset({"true", "1", "yes", "on"})
_BOOL_FALSE = frozenset({"false", "0", "no", "off"})


def _coerce_bool(value: str) -> bool:
    v = value.strip().lower()
    if v in _BOOL_TRUE:
        return True
    if v in _BOOL_FALSE:
        return False
    raise ValueError(f"Cannot coerce {value!r} to bool")


def get_config() -> dict:
    """Return merged config: defaults + env var overrides."""
    config = deepcopy(DEFAULT_CONFIG)
    for env_var, key in _ENV_MAP.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        default_val = config[key]
        if isinstance(default_val, bool):
            config[key] = _coerce_bool(raw)
        elif isinstance(default_val, int) and not isinstance(default_val, bool):
            config[key] = int(raw)
        elif isinstance(default_val, float):
            config[key] = float(raw)
        else:
            config[key] = raw
    return config
