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
