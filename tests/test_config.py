import os
from sentiment_robot.config import get_config


def test_default_watchlist():
    config = get_config()
    assert "SPY" in config["watchlist"]
    assert "QQQ" in config["watchlist"]


def test_default_llm_disabled():
    config = get_config()
    assert config["llm_enabled"] is False


def test_env_overrides_llm_enabled(monkeypatch):
    monkeypatch.setenv("SENTIMENT_ROBOT_LLM_ENABLED", "true")
    config = get_config()
    assert config["llm_enabled"] is True


def test_env_overrides_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setenv("FRED_API_KEY", "fred-test-456")
    monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://open.feishu.cn/test")
    config = get_config()
    assert config["openai_api_key"] == "sk-test-123"
    assert config["openai_base_url"] == "https://api.openai.com/v1"
    assert config["fred_api_key"] == "fred-test-456"
    assert config["feishu_webhook_url"] == "https://open.feishu.cn/test"


def test_env_overrides_db_path(monkeypatch):
    monkeypatch.setenv("SENTIMENT_ROBOT_DB_PATH", "/tmp/test.db")
    config = get_config()
    assert config["db_path"] == "/tmp/test.db"


def test_bool_coercion_false_values(monkeypatch):
    for val in ("false", "0", "no", "off"):
        monkeypatch.setenv("SENTIMENT_ROBOT_LLM_ENABLED", val)
        config = get_config()
        assert config["llm_enabled"] is False, f"failed for {val}"
