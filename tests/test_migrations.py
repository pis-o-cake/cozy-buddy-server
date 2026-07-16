"""Alembic 초기 리비전 검증 — SQLite 방언으로 upgrade head 실행 (설계서 §6-2)."""

import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command

_ROOT = Path(__file__).resolve().parent.parent

_EXPECTED_TABLES = {
    "users",
    "rooms",
    "hubs",
    "devices",
    "scenarios",
    "scenario_actions",
    "chat_sessions",
    "messages",
    "timers",
}


def test_upgrade_head_creates_all_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")

    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "alembic"))
    command.upgrade(config, "head")

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert _EXPECTED_TABLES <= tables
