"""Pipeline orchestrator — runs collectors, stores results, triggers reports."""

import logging
from concurrent.futures import ThreadPoolExecutor

from .collectors.yfinance_news import YFinanceNewsCollector
from .collectors.stocktwits import StocktwitsCollector
from .collectors.reddit import RedditCollector
from .collectors.fred import FredCollector
from .collectors.prediction_markets import PredictionMarketsCollector
from .storage import init_db, create_run, finish_run, insert_raw, insert_report
from .reporter import generate_report
from .notifier import send_run_summary

logger = logging.getLogger(__name__)


def _get_collectors(run_type: str, config: dict) -> list:
    """Return the list of collector instances for the given run type."""
    if run_type == "breaking":
        return [
            YFinanceNewsCollector(config),
            StocktwitsCollector(config),
        ]
    # daily: all collectors
    return [
        YFinanceNewsCollector(config),
        StocktwitsCollector(config),
        RedditCollector(config),
        FredCollector(config),
        PredictionMarketsCollector(config),
    ]


def run_pipeline(run_type: str, config: dict) -> int:
    """Run the full data pipeline.

    Args:
        run_type: 'daily' or 'breaking'
        config: merged config dict from config.get_config()

    Returns:
        0 on success, 1 on fatal error (storage failure)
    """
    db_path = config["db_path"]
    init_db(db_path)

    llm_enabled = bool(config.get("llm_enabled") and config.get("openai_api_key"))
    run_id = create_run(db_path, run_type, llm_enabled=llm_enabled)
    logger.info("Starting %s run (id=%d)", run_type, run_id)

    collectors = _get_collectors(run_type, config)

    # Run collectors in parallel
    def _safe_run(collector):
        try:
            return collector.run()
        except Exception as e:
            logger.error("Collector %s crashed: %s", collector.name, e)
            return [{
                "source": collector.name,
                "ticker": None,
                "content": f"<collector crashed: {e}>",
                "fetched_at": "",
            }]

    with ThreadPoolExecutor(max_workers=len(collectors)) as executor:
        futures = list(executor.map(_safe_run, collectors))

    # Flatten and store
    for batch in futures:
        if batch:
            insert_raw(db_path, run_id, batch)

    # Optional LLM report
    if llm_enabled:
        report = generate_report(db_path, run_id, config)
        if report:
            insert_report(db_path, run_id, report)
            logger.info("LLM report generated for run %d — %s", run_id, report.get("sentiment_band", "?"))

    finish_run(db_path, run_id)

    # Feishu notification (best-effort, after everything else)
    send_run_summary(db_path, run_id, config)

    logger.info("Pipeline run %d complete", run_id)
    return 0
