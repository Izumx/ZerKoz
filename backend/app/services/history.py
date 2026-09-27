from datetime import date, datetime

from collections import defaultdict

from sqlalchemy import and_, or_
from sqlmodel import Session, select

from app.models import Event


def _jsonable(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def log(session: Session, entity: str, entity_id: int, action: str, payload: dict | None = None) -> None:
    payload = {k: _jsonable(v) for k, v in (payload or {}).items()}
    session.add(Event(entity=entity, entity_id=entity_id, action=action, payload=payload))


def for_entities(session: Session, pairs: list[tuple[str, int]]) -> list[dict]:
    """История нескольких объектов (участок + его сигналы), новые сверху."""
    if not pairs:
        return []
    ids_by_entity: dict[str, list[int]] = defaultdict(list)
    for entity, entity_id in pairs:
        ids_by_entity[entity].append(entity_id)
    condition = or_(*(and_(Event.entity == entity, Event.entity_id.in_(ids)) for entity, ids in ids_by_entity.items()))
    events = list(session.exec(select(Event).where(condition)).all())
    events.sort(key=lambda e: (e.created_at, e.id), reverse=True)
    return [
        {
            "entity": e.entity,
            "entity_id": e.entity_id,
            "action": e.action,
            "payload": e.payload,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]
