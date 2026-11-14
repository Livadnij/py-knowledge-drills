from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from db.models import Base


def test_upgrade_head_creates_all_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    cfg = Config("alembic.ini")
    cfg.cmd_opts = type("O", (), {"x": [f"url={url}"]})()
    command.upgrade(cfg, "head")
    tables = set(inspect(create_engine(url)).get_table_names())
    assert set(Base.metadata.tables) <= tables
