"""Alembic revision-chain integrity tests.

The chain must form ONE linear sequence so `alembic upgrade head` works on a
fresh database. This is a regression test for the chain breaks at 011
(reference to a non-existent "010_create_schedules" revision) and 014
(reference to "013" while 013 is registered as "013_create_notifications"),
plus the duplicate-index and SQLite-incompatible constraint operations that
prevented an end-to-end upgrade.

The full upgrade/downgrade/re-upgrade cycle runs against an ephemeral SQLite
database (mirrors the SQLite divergence documented in P6-C11; Postgres-only
FK metadata is skipped for SQLite where SQLite cannot represent it inline).
"""

import tempfile
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_DIR = BACKEND_DIR / "alembic"
INI_PATH = BACKEND_DIR / "alembic.ini"


def _config_for(url: str) -> Config:
    cfg = Config(str(INI_PATH))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def _collect_revisions() -> list[object]:
    cfg = _config_for("sqlite+aiosqlite:///:memory:")
    script = ScriptDirectory.from_config(cfg)
    return list(script.walk_revisions())


def test_alembic_chain_is_single_linear_head() -> None:
    cfg = _config_for("sqlite+aiosqlite:///:memory:")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1
    assert heads[0] == "024"


def test_alembic_chain_linkages_resolve() -> None:
    """Every down_revision must resolve to a real revision; no orphans."""
    cfg = _config_for("sqlite+aiosqlite:///:memory:")
    script = ScriptDirectory.from_config(cfg)
    revisions = list(script.walk_revisions())
    assert len(revisions) >= 24
    ids = {r.revision for r in revisions}
    for rev in revisions:
        if rev.down_revision is not None:
            assert rev.down_revision in ids


def test_alembic_full_upgrade_downgrade_reupgrade_cycle() -> None:
    """The entire chain applies, reverses, and re-applies on SQLite."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        db_path = Path(tmp.name)
    try:
        url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
        cfg = _config_for(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
    finally:
        db_path.unlink(missing_ok=True)
