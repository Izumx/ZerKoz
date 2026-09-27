"""Сигналы жителей с настоящими фотографиями из открытых источников (Wikimedia Commons).

Авторы и лицензии — в photos/ATTRIBUTION.md. Входят в демо-данные generate;
в уже заполненную базу добавляются командой: python -m app.seed.real_photos
"""
import random
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from app import db
from app.models import Parcel, Signal, utcnow
from app.services import geo, history, signals

PHOTOS_DIR = Path(__file__).with_name("photos")

# (фото, где: (тип нарушения, назначение) — точка на таком участке с нарушением, или (lat, lon) вне участков,
#  описание жителя, язык, статус, сколько дней назад)
SPECS = [
    ("mattresses.jpg", ("dump", "industrial"),
     "У дорожки возле участка выбросили старые матрасы и строительный мусор", "ru", "new", 0.1),
    ("fence.jpg", ("seizure", "commercial"),
     "Огородили профлистом часть проезда и тротуара, пешеходы идут прямо по дороге", "ru", "new", 1.1),
    ("steppe_dump.jpg", (42.9405, 71.2920),
     "За городом у грунтовой дороги вывалили бытовой мусор: пакеты, пластик, стройматериалы", "ru", "new", 0.4),
    ("tires_dump.jpg", (42.8745, 71.3050),
     "Қала шетінде ескі шиналар мен қоқыс төгілген, жел бүкіл далаға таратып жатыр", "kz", "checking", 1.8),
    ("weeds.jpg", ("unused", "izhs"),
     "Участок годами пустует, зарос бурьяном и сорняком, никто не обрабатывает", "ru", "checking", 2.5),
]


def _violating_parcel(session: Session, violation: str, purpose: str) -> Parcel | None:
    query = select(Parcel).where(Parcel.violation_type == violation, Parcel.lifecycle.in_(("detected", "in_progress")))
    candidates = session.exec(query.order_by(Parcel.id)).all()
    return next((p for p in candidates if p.purpose == purpose), candidates[0] if candidates else None)


def _free_point(session: Session, parcel: Parcel, rng: random.Random) -> tuple[float, float]:
    """Точка на участке, не ближе 50 м к открытым сигналам — иначе новый сигнал станет повтором."""
    for _ in range(30):
        lat, lon = geo.random_point_in(parcel.geometry, rng)
        if signals.find_duplicate_target(session, lat, lon) is None:
            break
    return lat, lon


def add_real_photo_signals(session: Session, rng: random.Random | None = None) -> list[Signal]:
    """Создать сигналы с настоящими фото; уже добавленные (по тексту описания) пропускаются."""
    from app.seed.generate import backdate_events  # generate сам импортирует этот модуль

    rng = rng or random.Random(2027)
    existing = set(session.exec(select(Signal.description)).all())
    created = []
    for filename, where, text, lang, status, days_ago in SPECS:
        if text in existing:
            continue
        if isinstance(where[0], str):
            parcel = _violating_parcel(session, *where)
            if parcel is None:
                continue
            lat, lon = _free_point(session, parcel, rng)
        else:
            lat, lon = where
        photo = (PHOTOS_DIR / filename).read_bytes()
        s = signals.create_signal(session, lat=lat, lon=lon, description=text, source="seed", lang=lang, photos=[photo])
        if status != "new":
            s.status = status
            history.log(session, "signal", s.id, "status", {"from": "new", "to": status})
        s.created_at = s.updated_at = utcnow() - timedelta(days=days_ago)
        session.add(s)
        session.flush()
        backdate_events(session, "signal", s.id, start_days_ago=int(days_ago))
        session.commit()
        created.append(s)
    return created


def main() -> None:
    with db.new_session() as session:
        created = add_real_photo_signals(session)
    print(f"Добавлено сигналов с настоящими фото: {len(created)}" +
          (f" ({', '.join(s.code for s in created)})" if created else ""))


if __name__ == "__main__":
    main()
