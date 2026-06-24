"""SQLite storage layer for sentiment_robot."""

import sqlite3
from datetime import datetime, timezone


SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    run_type TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    llm_enabled INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS raw_data (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES runs(id),
    source TEXT NOT NULL,
    ticker TEXT,
    content TEXT NOT NULL,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY,
    run_id INTEGER REFERENCES runs(id),
    report_type TEXT NOT NULL,
    markdown_path TEXT,
    sentiment_band TEXT,
    sentiment_score REAL,
    confidence TEXT,
    summary TEXT,
    generated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()


def create_run(db_path: str, run_type: str, llm_enabled: bool = False) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        "INSERT INTO runs (run_type, started_at, llm_enabled) VALUES (?, ?, ?)",
        (run_type, _now(), int(llm_enabled)),
    )
    conn.commit()
    run_id = cur.lastrowid
    conn.close()
    return run_id


def finish_run(db_path: str, run_id: int) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE runs SET finished_at = ? WHERE id = ?", (_now(), run_id))
    conn.commit()
    conn.close()


def insert_raw(db_path: str, run_id: int, items: list[dict]) -> None:
    if not items:
        return
    conn = sqlite3.connect(db_path)
    rows = [
        (run_id, item["source"], item["ticker"], item["content"], item["fetched_at"])
        for item in items
    ]
    conn.executemany(
        "INSERT INTO raw_data (run_id, source, ticker, content, fetched_at) "
        "VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def insert_report(db_path: str, run_id: int, report: dict) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO reports "
        "(run_id, report_type, markdown_path, sentiment_band, sentiment_score, "
        "confidence, summary, generated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run_id,
            report["report_type"],
            report["markdown_path"],
            report.get("sentiment_band"),
            report.get("sentiment_score"),
            report.get("confidence"),
            report.get("summary"),
            report["generated_at"],
        ),
    )
    conn.commit()
    conn.close()


def get_raw_for_run(db_path: str, run_id: int) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM raw_data WHERE run_id = ? ORDER BY id", (run_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_runs(db_path: str, limit: int = 10) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
