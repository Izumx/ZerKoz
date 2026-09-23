from datetime import date

from sqlalchemy import func, or_
from sqlmodel import Session, select

from app.events import bus
from app.models import VIOLATION_TYPES, Parcel, Photo, Signal, utcnow
from app.services import NotFound, TransitionError, history
from app.services.photos import photo_dict

__all__ = ["TransitionError", "compute_color", "is_overdue", "update_parcel", "feature_collection", "parcel_detail"]

ACTIVE = frozenset({"detected", "in_progress"})
CLOSED = frozenset({"resolved", "returned"})
OPEN_SIGNAL_STATUSES = ("new", "checking")
TRANSITIONS: dict[str, set[str]] = {
    "none": {"detected"},
    "detected": {"in_progress", "resolved", "returned"},
    "in_progress": {"resolved", "returned"},
    "resolved": {"detected"},
    "returned": {"detected"},
}
EDITABLE = {"lifecycle", "violation_type", "deadline", "under_check"}


def compute_color(parcel: Parcel, open_signals: int) -> str:
    if parcel.lifecycle in ACTIVE:
        return "red"
    if parcel.under_check or open_signals > 0:
        return "yellow"
    return "green"


def is_overdue(parcel: Parcel, today: date | None = None) -> bool:
    today = today or date.today()
    return parcel.lifecycle in ACTIVE and parcel.deadline is not None and parcel.deadline < today


def get_parcel(session: Session, parcel_id: int) -> Parcel:
    parcel = session.get(Parcel, parcel_id)
    if parcel is None:
        raise NotFound(f"Участок {parcel_id} не найден")
    return parcel


def update_parcel(session: Session, parcel_id: int, changes: dict) -> Parcel:
    """Изменить участок с проверкой правил жизненного цикла. Коммитит и публикует событие."""
    parcel = get_parcel(session, parcel_id)
    unknown = set(changes) - EDITABLE
    if unknown:
        raise TransitionError(f"Нельзя изменить поля: {', '.join(sorted(unknown))}")

    old = parcel.lifecycle
    new = changes.get("lifecycle") or old
    violation_type = changes.get("violation_type", parcel.violation_type)
    if "deadline" in changes:
        deadline = changes["deadline"]
    elif new == "detected" and old != "detected":
        deadline = None  # новое нарушение — новый срок
    else:
        deadline = parcel.deadline

    if violation_type is not None and violation_type not in VIOLATION_TYPES:
        raise TransitionError(f"Неизвестный тип нарушения: {violation_type}")
    if new != old:
        if new not in TRANSITIONS.get(old, set()):
            raise TransitionError(f"Переход «{old}» → «{new}» недопустим")
        if new == "detected" and not violation_type:
            raise TransitionError("Укажите тип нарушения")
        if new == "in_progress" and not deadline:
            raise TransitionError("Установите контрольный срок устранения")

    changed = {}
    for field, value in (("violation_type", violation_type), ("deadline", deadline)):
        if getattr(parcel, field) != value:
            changed[field] = value
            setattr(parcel, field, value)
    if "under_check" in changes and changes["under_check"] != parcel.under_check:
        changed["under_check"] = parcel.under_check = bool(changes["under_check"])

    affected_signals: list[Signal] = []
    if new != old:
        parcel.lifecycle = new
        if new == "detected":
            parcel.under_check = False
        history.log(session, "parcel", parcel.id, "lifecycle", {"from": old, "to": new, **changed})
        if new in CLOSED:
            from app.services import signals  # локальный импорт: signals зависит от parcels

            affected_signals = signals.resolve_confirmed_for_parcel(session, parcel.id)
    elif changed:
        history.log(session, "parcel", parcel.id, "updated", changed)

    parcel.updated_at = utcnow()
    session.add(parcel)
    session.commit()

    bus.publish("parcel.updated", {"id": parcel.id})
    if affected_signals:
        from app.services import signals

        for s in affected_signals:
            signals.after_status_change(s)
    return parcel


def open_signal_counts(session: Session) -> dict[int, int]:
    rows = session.exec(
        select(Signal.parcel_id, func.count())
        .where(Signal.parcel_id.is_not(None), Signal.status.in_(OPEN_SIGNAL_STATUSES))
        .group_by(Signal.parcel_id)
    ).all()
    return dict(rows)


def parcel_properties(parcel: Parcel, open_signals: int) -> dict:
    return {
        "id": parcel.id,
        "cadastral_no": parcel.cadastral_no,
        "purpose": parcel.purpose,
        "area_ha": round(parcel.area_ha, 4),
        "address": parcel.address,
        "owner": parcel.owner,
        "lifecycle": parcel.lifecycle,
        "violation_type": parcel.violation_type,
        "deadline": parcel.deadline.isoformat() if parcel.deadline else None,
        "under_check": parcel.under_check,
        "open_signals": open_signals,
        "color": compute_color(parcel, open_signals),
        "overdue": is_overdue(parcel),
        "updated_at": parcel.updated_at.isoformat(),
    }


def feature_collection(session: Session) -> dict:
    counts = open_signal_counts(session)
    parcels = session.exec(select(Parcel).order_by(Parcel.cadastral_no)).all()
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "id": p.id,
                "geometry": p.geometry,
                "properties": parcel_properties(p, counts.get(p.id, 0)),
            }
            for p in parcels
        ],
    }


def parcel_detail(session: Session, parcel_id: int) -> dict:
    parcel = get_parcel(session, parcel_id)
    signals = session.exec(
        select(Signal).where(Signal.parcel_id == parcel_id).order_by(Signal.created_at.desc())
    ).all()
    open_count = sum(1 for s in signals if s.status in OPEN_SIGNAL_STATUSES)
    signal_ids = [s.id for s in signals]
    condition = Photo.parcel_id == parcel_id
    if signal_ids:
        condition = or_(condition, Photo.signal_id.in_(signal_ids))
    photos = session.exec(select(Photo).where(condition).order_by(Photo.created_at.desc())).all()
    return {
        **parcel_properties(parcel, open_count),
        "geometry": parcel.geometry,
        "ndvi_series": parcel.ndvi_series,
        "photos": [photo_dict(p) for p in photos],
        "signals": [
            {"id": s.id, "code": s.code, "status": s.status, "description": s.description,
             "created_at": s.created_at.isoformat()}
            for s in signals
        ],
        "history": history.for_entities(session, [("parcel", parcel_id)] + [("signal", i) for i in signal_ids]),
    }
