from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Area


def get_by_key(s: Session, key: str) -> Area | None:
    return s.scalar(select(Area).where(Area.key == key))


def create(s: Session, key: str, name: str, description: str = "") -> Area:
    area = Area(key=key, name=name, description=description)
    s.add(area)
    s.flush()
    return area


def list_all(s: Session) -> list[Area]:
    return list(s.scalars(select(Area).order_by(Area.name)))


def mark_started(s: Session, area_id: int, now: datetime) -> None:
    area = s.get(Area, area_id)
    if area.started_at is None:
        area.started_at = now
        s.flush()
