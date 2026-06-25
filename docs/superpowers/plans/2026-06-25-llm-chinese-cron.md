# LLM Chinese Translation & Scheduling Refinements

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make LLM usage required (not optional), produce Chinese-language reports and notifications, add `llm_model` env var for custom endpoints, and fix the crontab schedule to every-2-hours for breaking news.

**Architecture:** Three independent changes across the config/reporter/notifier layers. Config gains a `SENTIMENT_ROBOT_LLM_MODEL` env var and flips `llm_enabled` default to `True`. The reporter prompt switches to Chinese output. The Feishu notifier labels switch to Chinese. Crontab example gets corrected to `*/2` hours for breaking scans.

**Tech Stack:** Python 3.10+, OpenAI SDK, requests, pytest with monkeypatch/unittest.mock

## Global Constraints

- Python >=3.10 (existing pyproject.toml requirement)
- Match existing code style: double quotes, 4-space indent, no type annotations on test helpers
- All 53 existing tests must continue to pass
- JSON keys in LLM output (`overall_band`, `overall_score`, etc.) remain English — only human-readable content switches to Chinese

---

### Task 1: Config — llm_model env var + llm_enabled default True

**Files:**
- Modify: `sentiment_robot/config.py:21-46`
- Modify: `tests/test_config.py:11-13` (update existing test) + add new test
- Modify: `.env.example:6-7`

**Interfaces:**
- Produces: `config["llm_model"]` now overridable via `SENTIMENT_ROBOT_LLM_MODEL` env var; `config["llm_enabled"]` defaults to `True`

- [ ] **Step 1: Write the failing tests**

In `tests/test_config.py`, update the existing `test_default_llm_disabled` to expect `True`, and add a new test for the model env var:

```python
def test_default_llm_enabled():
    """llm_enabled now defaults to True — LLM is required for Chinese translation."""
    config = get_config()
    assert config["llm_enabled"] is True


def test_env_overrides_llm_model(monkeypatch):
    monkeypatch.setenv("SENTIMENT_ROBOT_LLM_MODEL", "qwen2.5:7b")
    config = get_config()
    assert config["llm_model"] == "qwen2.5:7b"
```

Note: the old `test_default_llm_disabled` function must be deleted (or renamed and assertion flipped). The replacement is `test_default_llm_enabled`.

Also verify the `test_bool_coercion_false_values` test still works — it already tests that `"false"` env var returns `False`, which is correct. No change needed there.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config.py::test_default_llm_enabled tests/test_config.py::test_env_overrides_llm_model -v`
Expected: `test_default_llm_enabled` FAILS (assert False is True), `test_env_overrides_llm_model` FAILS with "test_env_overrides_llm_model not found" (if renamed) or KeyError if not yet in env map.

- [ ] **Step 3: Implement config changes**

In `sentiment_robot/config.py`, make these two edits:

**Change 1 — flip default (line 21):**
```python
# Before:
"llm_enabled": False,
# After:
"llm_enabled": True,
```

**Change 2 — add env var mapping (after line 40, inside _ENV_MAP dict):**
```python
_ENV_MAP = {
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_BASE_URL": "openai_base_url",
    "SENTIMENT_ROBOT_LLM_MODEL": "llm_model",   # <-- add this line
    "FRED_API_KEY": "fred_api_key",
    ...
}
```

- [ ] **Step 4: Run config tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: All 6 tests PASS (5 existing + 1 new; `test_default_llm_disabled` replaced by `test_default_llm_enabled`).

- [ ] **Step 5: Update .env.example**

In `.env.example`, change lines 6-7:

```bash
# Before:
export OPENAI_BASE_URL=   # Optional: use OpenAI-compatible APIs (e.g. Azure, local LLM)
export FEISHU_WEBHOOK_URL=
export SENTIMENT_ROBOT_LLM_ENABLED=false

# After:
export OPENAI_BASE_URL=   # Optional: use OpenAI-compatible APIs (e.g. Azure, local LLM)
export SENTIMENT_ROBOT_LLM_MODEL=   # Required when OPENAI_BASE_URL is set (e.g. qwen2.5:7b, gpt-4o-mini)
export FEISHU_WEBHOOK_URL=
export SENTIMENT_ROBOT_LLM_ENABLED=true
```

- [ ] **Step 6: Commit**

```bash
git add sentiment_robot/config.py tests/test_config.py .env.example
git commit -m "feat: add SENTIMENT_ROBOT_LLM_MODEL env var, default llm_enabled to true"
```

---

### Task 2: Reporter — Chinese output prompt

**Files:**
- Modify: `sentiment_robot/reporter.py:45-59` (prompt), `sentiment_robot/reporter.py:88-93` (markdown header)
- Modify: `tests/test_reporter.py:54-58` (mock LLM response)

**Interfaces:**
- Consumes: `config["llm_model"]` from Task 1 (env-overridable model name already used on line 69)
- Produces: Same `dict | None` return type; report content now in Chinese, `overall_band` values stay English for programmatic keys

- [ ] **Step 1: Update the reporter prompt to request Chinese**

In `sentiment_robot/reporter.py`, replace the prompt (lines 45-59):

```python
    prompt = f"""你是一位金融市场情绪分析师。请分析以下多源数据，生成一份结构化的市场情绪报告。

## 数据

{data_text}

## 指令

返回一个 JSON 对象，包含以下键（键名必须为英文）：
- overall_band: 以下之一 "Bullish"（看涨）, "Mildly Bullish"（温和看涨）, "Neutral"（中性）, "Mixed"（混合）, "Mildly Bearish"（温和看跌）, "Bearish"（看跌）
- overall_score: 数字 0-10（0=极度看跌, 5=中性, 10=极度看涨）
- confidence: "low"（低）, "medium"（中）, 或 "high"（高）
- narrative: 用中文 Markdown 格式撰写摘要，包含：各数据源逐一分析、主导主题、催化剂与风险、总结表格

只返回 JSON 对象，不要包含其他文字。"""
```

- [ ] **Step 2: Update the markdown file header to Chinese**

In `sentiment_robot/reporter.py`, replace lines 88-93 (inside the `with open(...)` block):

```python
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(f"# 市场情绪报告 — {date_str}\n\n")
            f.write(f"**整体判断：** {parsed['overall_band']} | ")
            f.write(f"**评分：** {parsed['overall_score']}/10 | ")
            f.write(f"**置信度：** {parsed['confidence']}\n\n")
            f.write(parsed["narrative"])
```

- [ ] **Step 3: Update the test mock response to match Chinese prompt expectations**

In `tests/test_reporter.py`, the `test_generates_report_with_llm` test (line 54) has a mock response with English content. The test doesn't assert on language — it checks that `sentiment_band`, `sentiment_score`, and `confidence` are extracted correctly from JSON. The test checks `result["summary"]` is truthy and the markdown file exists. These assertions are language-neutral, so they should still pass.

However, the test at line 73 checks `assert result["summary"]` which will be Chinese text — this is fine, it's a truthiness check. No test changes needed here.

Verify by running:

```bash
pytest tests/test_reporter.py -v
```

Expected: All 4 tests PASS (no assertion depends on English content).

- [ ] **Step 4: Commit**

```bash
git add sentiment_robot/reporter.py
git commit -m "feat: switch reporter prompt and output to Chinese"
```

---

### Task 3: Notifier — Chinese labels in Feishu cards

**Files:**
- Modify: `sentiment_robot/notifier.py:192-243` (card title, section labels, footer)
- Modify: `tests/test_notifier.py:68-91` (test_sends_card_on_success — check Chinese content instead of English)
- Modify: `tests/test_notifier.py:94-105` (test_breaking_mode_uses_red_color — check Chinese title)

**Interfaces:**
- Consumes: Nothing from prior tasks (notifier operates on raw DB rows independently)
- Produces: Same `bool` return type; Feishu card content is now Chinese

- [ ] **Step 1: Update notifier labels to Chinese**

In `sentiment_robot/notifier.py`, make these replacements:

**Line 196-197 — card title:**
```python
    # Before:
    title = "🚨 Breaking Market Alert" if is_breaking else "📊 Daily Market Sentiment"
    # After:
    title = "🚨 突发市场警报" if is_breaking else "📊 每日市场情绪"
```

**Line 201-205 — timestamp line:**
```python
    # Before:
    elements = [
        {
            "tag": "markdown",
            "content": f"**{now} UTC** · Run #{run_id} · {run_type.upper()}",
        },
    ]
    # After:
    elements = [
        {
            "tag": "markdown",
            "content": f"**{now} UTC** · 运行 #{run_id} · {run_type.upper()}",
        },
    ]
```

**Line 209 — news section header (inside `_build_news_section`, line 53):**
```python
    # Before:
    lines = ["**📰 Top Headlines**"]
    # After:
    lines = ["**📰 头条新闻**"]
```

**Line 76 — StockTwits section header (inside `_build_stocktwits_section`):**
```python
    # Before:
    lines = ["**💬 StockTwits Sentiment**"]
    # After:
    lines = ["**💬 StockTwits 情绪**"]
```

**Line 95 — Reddit section header (inside `_build_reddit_section`):**
```python
    # Before:
    lines = ["**🐦 Reddit Discussion**"]
    # After:
    lines = ["**🐦 Reddit 讨论**"]
```

**Line 116 — FRED section header (inside `_build_fred_section`):**
```python
    # Before:
    lines = ["**🏛️ Macro Indicators (FRED)**"]
    # After:
    lines = ["**🏛️ 宏观指标 (FRED)**"]
```

**Line 141 — Prediction markets section header (inside `_build_prediction_section`):**
```python
    # Before:
    lines = ["**🎲 Prediction Markets**"]
    # After:
    lines = ["**🎲 预测市场**"]
```

**Line 240-243 — footer:**
```python
    # Before:
    elements.append({
        "tag": "markdown",
        "content": f"💡 `python -m sentiment_robot report {run_id}` for LLM summary",
    })
    # After:
    elements.append({
        "tag": "markdown",
        "content": f"💡 `python -m sentiment_robot report {run_id}` 查看 LLM 中文摘要",
    })
```

- [ ] **Step 2: Update notifier tests to check Chinese content**

In `tests/test_notifier.py`, `test_sends_card_on_success` (line 68), replace the English content assertions:

```python
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
    card_text = str(payload["card"])
    # Chinese card title for daily mode
    assert "每日市场情绪" in card_text
    # Verify actual content is still included (titles now in Chinese)
    assert "fed holds rates steady" in card_text.lower()
    assert "apple beats earnings" in card_text.lower()
    assert "AAPL" in card_text
    assert "spy 500c yolo" in card_text.lower()
    assert "CPI" in card_text or "consumer price index" in card_text.lower()
    assert "fed cuts rates" in card_text.lower()
```

The `test_breaking_mode_uses_red_color` test (line 94) checks `"red" in str(payload["card"]).lower()` — this assertion is color-based, not language-based, so it still passes. But update the test name's context and add a Chinese title check:

```python
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
    card_text = str(payload["card"])
    assert "red" in card_text.lower()
    assert "突发市场警报" in card_text
```

- [ ] **Step 3: Run notifier tests to verify they pass**

Run: `pytest tests/test_notifier.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add sentiment_robot/notifier.py tests/test_notifier.py
git commit -m "feat: switch Feishu card labels to Chinese"
```

---

### Task 4: Crontab — every 2 hours for breaking news

**Files:**
- Modify: `crontab.example:1-16`
- Modify: `README.md:53-58`

**Interfaces:**
- No code interfaces — documentation-only changes

- [ ] **Step 1: Update crontab.example**

Replace the entire content of `crontab.example`:

```
# Sentiment Robot — example crontab entries
#
# Daily full scan at 8:00 AM, every day
0 8 * * * cd /path/to/sentiment_robot && bash run.sh daily
#
# Breaking news scan every 2 hours, all day
0 */2 * * * cd /path/to/sentiment_robot && bash run.sh breaking
#
# Windows Task Scheduler:
# Daily scan:
#   Program: python
#   Arguments: -m sentiment_robot daily
#   Start in: C:\path\to\sentiment_robot
#   Trigger: Daily at 8:00 AM
#
# Breaking scan (every 2 hours):
#   Program: python
#   Arguments: -m sentiment_robot breaking
#   Start in: C:\path\to\sentiment_robot
#   Trigger: Repeat every 2 hours
```

The key change: replace the 4 separate market-hours entries for breaking news with a single `0 */2 * * *` entry that runs every 2 hours all day. Also widened daily from weekdays to every day (removed `1-5`).

- [ ] **Step 2: Update README deployment section**

In `README.md`, replace lines 53-58:

```markdown
## Deployment

Add to crontab:

```
0 8 * * * cd /path/to/sentiment_robot && bash run.sh daily
0 */2 * * * cd /path/to/sentiment_robot && bash run.sh breaking
```

See `crontab.example` for more schedules including Windows Task Scheduler.
```

- [ ] **Step 3: Commit**

```bash
git add crontab.example README.md
git commit -m "docs: daily at 8am, breaking every 2 hours in crontab"
```

---

### Task 5: Integration verification — full test suite

**Files:**
- No file changes. Verification only.

**Interfaces:**
- Verifies all prior tasks integrate without regressions

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS (was 53, now ~55 with new tests).

- [ ] **Step 2: Verify no regressions in specific areas**

Run the most change-sensitive test files individually:
```bash
pytest tests/test_config.py tests/test_reporter.py tests/test_notifier.py tests/test_integration.py tests/test_orchestrator.py -v
```
Expected: All PASS.

- [ ] **Step 3: Spot-check: config defaults make sense**

```bash
python -c "from sentiment_robot.config import get_config; c = get_config(); print('llm_enabled:', c['llm_enabled']); print('llm_model:', c['llm_model'])"
```
Expected output:
```
llm_enabled: True
llm_model: gpt-4o-mini
```

- [ ] **Step 4: Commit (if any final tweaks needed)**

```bash
git add -A
git commit -m "chore: final integration verification after Chinese/LLM/cron changes"
```
