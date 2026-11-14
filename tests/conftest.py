import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from sqlalchemy.orm import Session

from db.models import Base
from db.session import make_engine, make_session_factory


@pytest.fixture
def session():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    with factory() as s:
        yield s


@pytest.fixture
def factory(tmp_path):
    """A file-backed session factory, shared across threads like the real app."""
    engine = make_engine(f"sqlite:///{tmp_path / 'ui.db'}")
    Base.metadata.create_all(engine)
    return make_session_factory(engine)
