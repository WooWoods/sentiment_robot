from sentiment_robot.storage import (
    init_db,
    create_run,
    insert_raw,
    insert_report,
    get_raw_for_run,
    get_recent_runs,
    finish_run,
)


def test_init_db_creates_tables(tmp_db_path):
    init_db(tmp_db_path)
    import sqlite3
    conn = sqlite3.connect(tmp_db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "runs" in table_names
    assert "raw_data" in table_names
    assert "reports" in table_names
    conn.close()


def test_create_run_returns_id(tmp_db_path):
    init_db(tmp_db_path)
    run_id = create_run(tmp_db_path, "daily", llm_enabled=True)
    assert isinstance(run_id, int)
    assert run_id > 0


def test_insert_raw_and_retrieve(tmp_db_path):
    init_db(tmp_db_path)
    run_id = create_run(tmp_db_path, "daily")
    items = [
        {"source": "stocktwits", "ticker": "AAPL", "content": "Bullish messages...", "fetched_at": "2026-06-24T09:00:00"},
        {"source": "fred", "ticker": None, "content": "CPI data...", "fetched_at": "2026-06-24T09:00:00"},
    ]
    insert_raw(tmp_db_path, run_id, items)

    results = get_raw_for_run(tmp_db_path, run_id)
    assert len(results) == 2
    assert results[0]["source"] == "stocktwits"
    assert results[0]["ticker"] == "AAPL"
    assert results[1]["source"] == "fred"
    assert results[1]["ticker"] is None


def test_insert_empty_list_is_noop(tmp_db_path):
    init_db(tmp_db_path)
    run_id = create_run(tmp_db_path, "daily")
    insert_raw(tmp_db_path, run_id, [])
    results = get_raw_for_run(tmp_db_path, run_id)
    assert len(results) == 0


def test_insert_report(tmp_db_path):
    init_db(tmp_db_path)
    run_id = create_run(tmp_db_path, "daily")
    report = {
        "report_type": "daily_summary",
        "markdown_path": "./output/2026-06-24-report.md",
        "sentiment_band": "Mildly Bullish",
        "sentiment_score": 6.5,
        "confidence": "medium",
        "summary": "Market sentiment leans positive...",
        "generated_at": "2026-06-24T09:05:00",
    }
    insert_report(tmp_db_path, run_id, report)
    import sqlite3
    conn = sqlite3.connect(tmp_db_path)
    row = conn.execute("SELECT * FROM reports WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    assert row is not None
    assert row[2] == "daily_summary"
    assert row[4] == "Mildly Bullish"


def test_get_recent_runs(tmp_db_path):
    init_db(tmp_db_path)
    r1 = create_run(tmp_db_path, "daily")
    r2 = create_run(tmp_db_path, "breaking")
    finish_run(tmp_db_path, r1)
    runs = get_recent_runs(tmp_db_path, limit=5)
    assert len(runs) == 2
    assert runs[0]["run_type"] == "breaking"  # most recent first
    assert runs[1]["finished_at"] is not None  # r1 was finished
    assert runs[0]["finished_at"] is None       # r2 not finished


def test_finish_run_sets_timestamp(tmp_db_path):
    init_db(tmp_db_path)
    run_id = create_run(tmp_db_path, "daily")
    finish_run(tmp_db_path, run_id)
    import sqlite3
    conn = sqlite3.connect(tmp_db_path)
    finished = conn.execute(
        "SELECT finished_at FROM runs WHERE id = ?", (run_id,)
    ).fetchone()[0]
    conn.close()
    assert finished is not None
