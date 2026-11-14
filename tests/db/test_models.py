import pytest
from sqlalchemy.exc import IntegrityError

from db.models import Area, Card, Question


def _area(session, key="databases"):
    area = Area(key=key, name=key.title(), description="")
    session.add(area)
    session.flush()
    return area


def test_question_roundtrip_with_facts(session):
    area = _area(session)
    q = Question(area_id=area.id, text="Q?", facts=[{"text": "a", "major": True}])
    session.add(q)
    session.commit()
    session.expire_all()
    loaded = session.get(Question, q.id)
    assert loaded.facts == [{"text": "a", "major": True}]
    assert loaded.flagged is False


def test_card_belongs_to_question(session):
    area = _area(session)
    q = Question(area_id=area.id, text="Q?", facts=[])
    session.add(q)
    session.flush()
    from datetime import datetime
    session.add(Card(question_id=q.id, state={"x": 1}, due=datetime(2026, 1, 1)))
    session.commit()
    assert session.get(Card, q.id).state == {"x": 1}


def test_area_key_unique(session):
    _area(session, "dup")
    with pytest.raises(IntegrityError):
        _area(session, "dup")
