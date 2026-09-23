from sqlmodel import Session, select

from app.events import bus
from app.models import VIOLATION_TYPES, Parcel, Photo, Signal, utcnow
from app.services import NotFound, ServiceError, TransitionError, geo, history, notify
from app.services.photos import photo_dict, save_photo

STATUS_TRANSITIONS: dict[str, set[str]] = {
    "new": {"checking", "confirmed", "rejected"},
    "checking": {"confirmed", "rejected"},
    "confirmed": {"resolved"},
    "rejected": {"checking"},
    "resolved": set(),
}
MAX_DESCRIPTION = 1000


def create_signal(
    session: Session,
    *,
    lat: float,
    lon: float,
    description: str = "",
    source: str = "telegram",
    tg_chat_id: int | None = None,
    lang: str = "ru",
    photos: list[bytes] | tuple[bytes, ...] = (),
) -> Signal:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ServiceError("Некорректные координаты")
    parcel = geo.find_parcel(session, lat=lat, lon=lon)
    signal = Signal(
        lat=lat,
        lon=lon,
        description=description.strip()[:MAX_DESCRIPTION],
        source=source,
        tg_chat_id=tg_chat_id,
        lang=lang,
        parcel_id=parcel.id if parcel else None,
    )
    session.add(signal)
    try:
        session.flush()
        signal.code = f"SIG-{signal.id:04d}"
        for data in photos:
            save_photo(session, data, signal_id=signal.id, source="citizen")
        history.log(session, "signal", signal.id, "created",
                    {"source": source, "parcel": parcel.cadastral_no if parcel else None})
        session.commit()
    except Exception:
        session.rollback()
        raise

    bus.publish("signal.created", {"id": signal.id, "code": signal.code, "lat": lat, "lon": lon,
                                   "parcel_id": signal.parcel_id})
    if signal.parcel_id:
        bus.publish("parcel.updated", {"id": signal.parcel_id})
    return signal


def get_signal(session: Session, signal_id: int) -> Signal:
    signal = session.get(Signal, signal_id)
    if signal is None:
        raise NotFound(f"Сигнал {signal_id} не найден")
    return signal


def get_by_code(session: Session, code: str) -> Signal | None:
    return session.exec(select(Signal).where(Signal.code == code)).first()


def set_status(session: Session, signal_id: int, status: str, violation_type: str | None = None) -> Signal:
    signal = get_signal(session, signal_id)
    old = signal.status
    if status not in STATUS_TRANSITIONS.get(old, set()):
        raise TransitionError(f"Переход сигнала «{old}» → «{status}» недопустим")
    if violation_type is not None and violation_type not in VIOLATION_TYPES:
        raise TransitionError(f"Неизвестный тип нарушения: {violation_type}")

    signal.status = status
    signal.updated_at = utcnow()
    history.log(session, "signal", signal.id, "status", {"from": old, "to": status})

    if status == "confirmed" and signal.parcel_id:
        parcel = session.get(Parcel, signal.parcel_id)
        if parcel.lifecycle in ("none", "resolved", "returned"):
            history.log(session, "parcel", parcel.id, "lifecycle",
                        {"from": parcel.lifecycle, "to": "detected", "signal": signal.code})
            if parcel.lifecycle != "none":
                parcel.deadline = None
            parcel.lifecycle = "detected"
            parcel.violation_type = violation_type or parcel.violation_type or "dump"
            parcel.under_check = False
            parcel.updated_at = utcnow()
            session.add(parcel)

    session.add(signal)
    session.commit()
    after_status_change(signal)
    return signal


def resolve_confirmed_for_parcel(session: Session, parcel_id: int) -> list[Signal]:
    """Перевести подтверждённые сигналы участка в «устранено» (без commit)."""
    signals = session.exec(
        select(Signal).where(Signal.parcel_id == parcel_id, Signal.status == "confirmed")
    ).all()
    for s in signals:
        s.status = "resolved"
        s.updated_at = utcnow()
        history.log(session, "signal", s.id, "status", {"from": "confirmed", "to": "resolved"})
        session.add(s)
    return list(signals)


def after_status_change(signal: Signal) -> None:
    bus.publish("signal.updated", {"id": signal.id, "code": signal.code, "status": signal.status})
    if signal.parcel_id:
        bus.publish("parcel.updated", {"id": signal.parcel_id})
    notify.signal_status_changed(signal)


def _parcel_brief(session: Session, parcel_id: int | None) -> dict | None:
    if parcel_id is None:
        return None
    p = session.get(Parcel, parcel_id)
    return {"id": p.id, "cadastral_no": p.cadastral_no, "lifecycle": p.lifecycle} if p else None


def signal_dict(session: Session, signal: Signal, *, full: bool = True) -> dict:
    photos = session.exec(select(Photo).where(Photo.signal_id == signal.id).order_by(Photo.id)).all()
    data = {
        "id": signal.id,
        "code": signal.code,
        "lat": signal.lat,
        "lon": signal.lon,
        "description": signal.description,
        "source": signal.source,
        "lang": signal.lang,
        "status": signal.status,
        "parcel": _parcel_brief(session, signal.parcel_id),
        "has_citizen": signal.tg_chat_id is not None,
        "photos": [photo_dict(p) for p in photos],
        "created_at": signal.created_at.isoformat(),
        "updated_at": signal.updated_at.isoformat(),
    }
    if full:
        data["history"] = history.for_entities(session, [("signal", signal.id)])
    return data


def list_signals(session: Session, status: str | None = None) -> list[dict]:
    query = select(Signal).order_by(Signal.created_at.desc())
    if status:
        query = query.where(Signal.status == status)
    return [signal_dict(session, s, full=False) for s in session.exec(query).all()]
