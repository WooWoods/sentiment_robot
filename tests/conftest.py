import os
import tempfile
import pytest


@pytest.fixture
def tmp_db_path():
    """Yield a temporary SQLite database path, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass
