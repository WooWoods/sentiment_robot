"""CLI entry point for sentiment_robot."""

import argparse
import logging
import sys

from .config import get_config
from .orchestrator import run_pipeline
from .storage import init_db
from .reporter import generate_report as do_report
from .storage import insert_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sentiment_robot")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="sentiment-robot",
        description="Daily multi-source market sentiment scanner",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("daily", help="Run full daily scan (all sources, all tickers)")
    sub.add_parser("breaking", help="Run fast breaking-news scan (StockTwits + global news only)")

    report_parser = sub.add_parser("report", help="Generate LLM report for a past run")
    report_parser.add_argument("run_id", type=int, help="Run ID to generate report for")

    sub.add_parser("setup-db", help="Initialize/reset the SQLite database")

    args = parser.parse_args()
    config = get_config()

    if args.command == "setup-db":
        init_db(config["db_path"])
        logger.info("Database initialized at %s", config["db_path"])
        return 0

    if args.command == "report":
        if not config.get("openai_api_key"):
            logger.error("OPENAI_API_KEY not set — cannot generate report")
            return 1
        report = do_report(config["db_path"], args.run_id, config)
        if report is None:
            logger.error("Report generation failed for run %d", args.run_id)
            return 1
        insert_report(config["db_path"], args.run_id, report)
        print(report["markdown_path"])
        return 0

    return run_pipeline(args.command, config)


if __name__ == "__main__":
    sys.exit(main())
