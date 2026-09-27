from collections import defaultdict
from datetime import timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.config import settings
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
OPEN_STATUSES = ("new", "checking", "confirmed")
MAX_DESCRIPTION = 1000
DUPLICATE_RADIUS_M = 50
DUPLICATE_WINDOW = timedelta(days=7)

# ключевые слова (RU + KZ) → тип нарушения, предлагаемый инспектору по описанию жителя
KEYWORDS = {
    "dump": ("мусор", "свалк", "отход", "помойк", "хлам", "бытов", "покрышк", "шин", "қоқыс", "үйінді", "қалдық"),
    "seizure": ("забор", "захват", "занял", "заняли", "построил", "сарай", "самовол", "пристрой", "огородил",
                "басып", "қоршау", "иеленіп", "салып"),
    "unused": ("заброш", "бурьян", "не обрабат", "пустует", "зарос", "сорняк", "никто не", "не использ",
               "иесіз", "қаңырап", "арамшөп", "пайдаланылмай", "өңделмей"),
}


class RateLimitError(ServiceError):
    pass


def guess_violation(description: str) -> str | None:
    text = description.lower()
    scores = {vt: sum(word in text for word in words) for vt, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def check_rate_limit(session: Session, chat_id: int) -> None:
    def count(hours: int) -> int:
        since = utcnow() - timedelta(hours=hours)
        return session.exec(select(func.count()).select_from(Signal)
                            .where(Signal.tg_chat_id == chat_id, Signal.created_at >= since)).one()

    if count(1) >= settings.signals_per_hour or count(24) >= settings.signals_per_day:
        raise RateLimitError("Слишком много сигналов, попробуйте позже")


def find_duplicate_target(session: Session, lat: float, lon: float) -> Signal | None:
    """Открытый сигнал в радиусе 50 м за последние 7 дней — о том же месте уже сообщали."""
    candidates = session.exec(
        select(Signal).where(Signal.duplicate_of.is_(None), Signal.status.in_(OPEN_STATUSES),
                             Signal.created_at >= utcnow() - DUPLICATE_WINDOW)
    ).all()
    near = [(geo.distance_m(lat, lon, s.lat, s.lon), s) for s in candidates]
    near = [(d, s) for d, s in near if d <= DUPLICATE_RADIUS_M]
    return min(near, key=lambda x: x[0])[1] if near else None


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
    if tg_chat_id is not None:
        check_rate_limit(session, tg_chat_id)
    description = description.strip()[:MAX_DESCRIPTION]
    parcel = geo.find_parcel(session, lat=lat, lon=lon)
    primary = find_duplicate_target(session, lat, lon)
    signal = Signal(
        lat=lat,
        lon=lon,
        description=description,
        source=source,
        tg_chat_id=tg_chat_id,
        lang=lang,
        parcel_id=parcel.id if parcel else None,
        duplicate_of=primary.id if primary else None,
        status=primary.status if primary else "new",
        suggested_violation=guess_violation(description),
    )
    session.add(signal)
    try:
        session.flush()
        signal.code = f"SIG-{signal.id:04d}"
        for data in photos:
            save_photo(session, data, signal_id=signal.id, source="citizen")
        history.log(session, "signal", signal.id, "created",
                    {"source": source, "parcel": parcel.cadastral_no if parcel else None,
                     "duplicate_of": primary.code if primary else None})
        if primary:
            history.log(session, "signal", primary.id, "duplicate", {"code": signal.code})
        session.commit()
    except Exception:
        session.rollback()
        raise

    bus.publish("signal.created", {"id": signal.id, "code": signal.code, "lat": lat, "lon": lon,
                                   "parcel_id": signal.parcel_id,
                                   "duplicate_of": primary.code if primary else None})
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


def duplicates_of(session: Session, signal_id: int) -> list[Signal]:
    return list(session.exec(select(Signal).where(Signal.duplicate_of == signal_id).order_by(Signal.id)).all())


def set_status(session: Session, signal_id: int, status: str, violation_type: str | None = None) -> Signal:
    signal = get_signal(session, signal_id)
    if signal.duplicate_of:
        primary = session.get(Signal, signal.duplicate_of)
        raise TransitionError(f"Это повторное сообщение — статус меняется в основном сигнале {primary.code}")
    old = signal.status
    if status not in STATUS_TRANSITIONS.get(old, set()):
        raise TransitionError(f"Переход сигнала «{old}» → «{status}» недопустим")
    if violation_type is not None and violation_type not in VIOLATION_TYPES:
        raise TransitionError(f"Неизвестный тип нарушения: {violation_type}")

    changed = [signal] + duplicates_of(session, signal.id)
    for s in changed:
        s.status = status
        s.updated_at = utcnow()
        history.log(session, "signal", s.id, "status", {"from": old, "to": status})
        session.add(s)

    if status == "confirmed" and signal.parcel_id:
        parcel = session.get(Parcel, signal.parcel_id)
        if parcel.lifecycle in ("none", "resolved", "returned"):
            history.log(session, "parcel", parcel.id, "lifecycle",
                        {"from": parcel.lifecycle, "to": "detected", "signal": signal.code})
            if parcel.lifecycle != "none":
                parcel.deadline = None
            parcel.lifecycle = "detected"
            parcel.violation_type = violation_type or signal.suggested_violation or parcel.violation_type or "dump"
            parcel.under_check = False
            parcel.updated_at = utcnow()
            session.add(parcel)

    session.commit()
    for s in changed:
        after_status_change(s)
    return signal


def resolve_confirmed_for_parcel(session: Session, parcel_id: int) -> list[Signal]:
    """Перевести подтверждённые сигналы участка (и их повторы) в «устранено» (без commit)."""
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


def _signal_dicts(session: Session, signals: list[Signal], *, full: bool) -> list[dict]:
    """Сериализация пачкой: фиксированное число запросов на весь список, а не на каждый сигнал."""
    if not signals:
        return []
    ids = [s.id for s in signals]
    dups_by: dict[int, list[Signal]] = defaultdict(list)
    for d in session.exec(select(Signal).where(Signal.duplicate_of.in_(ids)).order_by(Signal.id)).all():
        dups_by[d.duplicate_of].append(d)
    by_id = {s.id: s for s in signals} | {d.id: d for group in dups_by.values() for d in group}
    photos_by: dict[int, list[Photo]] = defaultdict(list)
    for p in session.exec(select(Photo).where(Photo.signal_id.in_(list(by_id))).order_by(Photo.id)).all():
        owner = p.signal_id if p.signal_id in ids else by_id[p.signal_id].duplicate_of
        photos_by[owner].append(p)
    parcel_ids = {s.parcel_id for s in signals if s.parcel_id}
    parcels = {p.id: p for p in session.exec(select(Parcel).where(Parcel.id.in_(parcel_ids))).all()} if parcel_ids else {}
    primary_ids = {s.duplicate_of for s in signals if s.duplicate_of}
    primary_codes = dict(session.exec(select(Signal.id, Signal.code).where(Signal.id.in_(primary_ids))).all()) \
        if primary_ids else {}

    result = []
    for signal in signals:
        group = [signal] + dups_by[signal.id]
        parcel = parcels.get(signal.parcel_id)
        data = {
            "id": signal.id,
            "code": signal.code,
            "lat": signal.lat,
            "lon": signal.lon,
            "description": signal.description,
            "source": signal.source,
            "lang": signal.lang,
            "status": signal.status,
            "parcel": {"id": parcel.id, "cadastral_no": parcel.cadastral_no, "lifecycle": parcel.lifecycle}
            if parcel else None,
            "has_citizen": any(s.tg_chat_id is not None for s in group),
            "duplicate_of": {"id": signal.duplicate_of, "code": primary_codes.get(signal.duplicate_of)}
            if signal.duplicate_of else None,
            "reports": len(group),
            "suggested_violation": signal.suggested_violation,
            "photos": [photo_dict(p) for p in photos_by[signal.id]],
            "created_at": signal.created_at.isoformat(),
            "updated_at": signal.updated_at.isoformat(),
        }
        if full:
            data["duplicates"] = [
                {"id": d.id, "code": d.code, "description": d.description, "created_at": d.created_at.isoformat()}
                for d in dups_by[signal.id]
            ]
            data["history"] = history.for_entities(session, [("signal", s.id) for s in group])
        result.append(data)
    return result


def signal_dict(session: Session, signal: Signal, *, full: bool = True) -> dict:
    return _signal_dicts(session, [signal], full=full)[0]


def list_signals(session: Session, status: str | None = None) -> list[dict]:
    """Основные сигналы (повторы свёрнуты в счётчик reports)."""
    query = select(Signal).where(Signal.duplicate_of.is_(None)).order_by(Signal.created_at.desc())
    if status:
        query = query.where(Signal.status == status)
    return _signal_dicts(session, list(session.exec(query).all()), full=False)
