# Sentiment Robot

Daily multi-source market sentiment scanner. Runs as a cron job to fetch global and ticker-specific sentiment data from Yahoo Finance, StockTwits, Reddit, FRED, and Polymarket, stores it in SQLite, optionally generates LLM summaries, and sends Feishu webhook notifications.

## Quick Start

```bash
pip install -e .
# Set up the database
python -m sentiment_robot setup-db
# Run a daily scan
python -m sentiment_robot daily
# Run a breaking-news scan
python -m sentiment_robot breaking
# Generate an LLM report for run #1
python -m sentiment_robot report 1
```

Or use the convenience script:

```bash
cp .env.example .env  # Edit with your keys
bash run.sh daily
bash run.sh breaking
```

## Configuration

All settings are in `sentiment_robot/config.py` (defaults). Override via environment variables:

| Env Var | Config Key | Default |
|---------|-----------|---------|
| `FRED_API_KEY` | `fred_api_key` | None |
| `OPENAI_API_KEY` | `openai_api_key` | None |
| `OPENAI_BASE_URL` | `openai_base_url` | None |
| `FEISHU_WEBHOOK_URL` | `feishu_webhook_url` | None |
| `SENTIMENT_ROBOT_LLM_ENABLED` | `llm_enabled` | true |
| `SENTIMENT_ROBOT_LLM_MODEL` | `llm_model` | gpt-4o-mini |
| `SENTIMENT_ROBOT_DB_PATH` | `db_path` | ./sentiment_robot.db |
| `SENTIMENT_ROBOT_OUTPUT_DIR` | `output_dir` | ./output |

## Data Sources

| Source | Type | Auth |
|--------|------|------|
| Yahoo Finance | News (global + per-ticker) | None |
| StockTwits | Retail sentiment per ticker | None |
| Reddit | r/wallstreetbets, r/stocks, etc. | None |
| FRED | Macro indicators (CPI, GDP, etc.) | Free API key |
| Polymarket | Prediction market probabilities | None |

## Deployment

Add to crontab:

```
0 8 * * * cd /path/to/sentiment_robot && bash run.sh daily
17 */2 * * * cd /path/to/sentiment_robot && bash run.sh breaking
```

See `crontab.example` for Windows Task Scheduler schedules.

> **Note:** Feishu cards will show Chinese content only when `OPENAI_API_KEY` is configured. Without it, cards show raw English data with Chinese section headers as a fallback.

## Project Structure

```
sentiment_robot/
├── __init__.py, __main__.py
├── cli.py, config.py, orchestrator.py
├── storage.py, reporter.py, notifier.py
└── collectors/
    ├── base.py
    ├── yfinance_news.py, stocktwits.py, reddit.py
    ├── fred.py, prediction_markets.py
```
