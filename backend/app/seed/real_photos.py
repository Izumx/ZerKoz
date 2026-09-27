"""Настоящие фотографии для сигналов жителей из открытых источников (Wikimedia Commons).

Авторы и лицензии — в photos/ATTRIBUTION.md. Входят в демо-данные generate; для уже заполненной базы
`python -m app.seed.real_photos` заменяет нарисованные заглушки у демо-сигналов и добавляет сигналы из SPECS.
"""
import random
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from app import db
from app.models import Parcel, Photo, PhotoBlob, Signal, utcnow
from app.services import geo, history, signals
from app.services.photos import save_photo

PHOTOS_DIR = Path(__file__).with_name("photos")

# фото для базовых демо-сигналов generate.create_signals (ключ — описание жителя)
SEED_SIGNAL_PHOTOS = {
    "Свалка бытового мусора на пустом участке, уже неделю никто не убирает": "household_dump.jpg",
    "Мусор так и лежит, уже пахнет": "household_dump_2.jpg",  # повтор: та же свалка с другой стороны
    "Участок заброшен, бурьян выше человеческого роста": "tall_weeds.jpg",
    "Забор вынесен на тротуар, пройти невозможно": "fence_path.jpg",
    "Промышленные отходы вывозят прямо на соседний участок": "industrial_waste.jpg",
    "Кучка листвы у забора": "leaves.jpg",
    "Стихийная свалка у обочины трассы Тараз — Шымкент": "roadside_dump.jpg",
}


def seed_photo(description: str) -> bytes:
    return (PHOTOS_DIR / SEED_SIGNAL_PHOTOS[description]).read_bytes()


def replace_seed_placeholders(session: Session) -> list[Signal]:
    """Заменить нарисованные заглушки у демо-сигналов настоящими фото (повторный запуск ничего не меняет)."""
    replaced = []
    rows = session.exec(select(Signal).where(Signal.source == "seed",
                                             Signal.description.in_(list(SEED_SIGNAL_PHOTOS)))).all()
    for s in rows:
        data = seed_photo(s.description)
        photos = session.exec(select(Photo).where(Photo.signal_id == s.id)).all()
        blobs = session.exec(select(PhotoBlob).where(PhotoBlob.photo_id.in_([p.id for p in photos]))).all()             if photos else []
        if len(blobs) == 1 and blobs[0].data == data:
            continue
        for b in blobs:
            session.delete(b)
        session.flush()
        for p in photos:
            session.delete(p)
        session.flush()
        save_photo(session, data, signal_id=s.id, source="citizen")
        replaced.append(s)
    session.commit()
    return replaced

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
    def codes(items: list[Signal]) -> str:
        return f" ({', '.join(s.code for s in items)})" if items else ""

    with db.new_session() as session:
        replaced = replace_seed_placeholders(session)
        created = add_real_photo_signals(session)
    print(f"Заглушки заменены настоящими фото: {len(replaced)}{codes(replaced)}")
    print(f"Добавлено сигналов с настоящими фото: {len(created)}{codes(created)}")


if __name__ == "__main__":
    main()
