"""Настоящие фотографии для демо-данных из открытых источников (Wikimedia Commons).

Авторы и лицензии — в photos/ATTRIBUTION.md. Используются генератором демо-данных и кнопкой «Демо: сигнал жителя»;
для уже заполненной базы `python -m app.seed.real_photos` заменяет прежние нарисованные заглушки
(у демо-сигналов и в фотофиксации инспектора) и добавляет сигналы из SPECS.
"""
import random
from datetime import timedelta
from pathlib import Path

from sqlmodel import Session, select

from app import db
from app.models import Event, Parcel, Photo, PhotoBlob, Signal, utcnow
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


# фотофиксация инспектора на участках с нарушением: (тип, назначение) → фото по кругу; (тип, None) — для остальных
INSPECTOR_PHOTOS = {
    ("unused", "agri"): ["insp_field_1.jpg", "insp_field_2.jpg"],  # степь Жамбылской области
    ("unused", None): ["insp_lot_1.jpg", "insp_lot_2.jpg", "insp_lot_3.jpg"],
    ("seizure", None): ["insp_fences.jpg"],
    ("dump", None): ["insp_industrial.jpg"],
}

# кнопка «Демо: сигнал жителя» — фото того же типа, что и описание
DEMO_PHOTOS = {
    "dump": ["household_dump.jpg", "roadside_dump.jpg", "steppe_dump.jpg", "tires_dump.jpg", "mattresses.jpg"],
    "unused": ["tall_weeds.jpg", "weeds.jpg"],
    "seizure": ["fence.jpg", "fence_path.jpg"],
}


def _read(filename: str) -> bytes:
    return (PHOTOS_DIR / filename).read_bytes()


def seed_photo(description: str) -> bytes:
    return _read(SEED_SIGNAL_PHOTOS[description])


def demo_photo(kind: str, rng: random.Random) -> bytes:
    return _read(rng.choice(DEMO_PHOTOS[kind]))


def _replace_photos(session: Session, photos: list[Photo], data: bytes, **owner) -> bool:
    """Оставить у владельца одно фото data; False — если оно уже такое."""
    blobs = session.exec(select(PhotoBlob).where(PhotoBlob.photo_id.in_([p.id for p in photos]))).all()         if photos else []
    if len(blobs) == 1 and blobs[0].data == data:
        return False
    for b in blobs:
        session.delete(b)
    session.flush()
    for p in photos:
        session.delete(p)
    session.flush()
    save_photo(session, data, **owner)
    return True


def set_inspector_photos(session: Session) -> list[Parcel]:
    """Фотофиксация инспектора на участках с нарушением. Участки, куда инспектор сам загружал фото, не трогаем."""
    manual = set(session.exec(select(Event.entity_id).where(Event.entity == "parcel", Event.action == "photos")).all())
    counters: dict[tuple, int] = {}
    changed = []
    red = session.exec(select(Parcel).where(Parcel.lifecycle.in_(("detected", "in_progress")))
                       .order_by(Parcel.id)).all()
    for parcel in red:
        key = (parcel.violation_type, parcel.purpose)
        if key not in INSPECTOR_PHOTOS:
            key = (parcel.violation_type, None)
        if key not in INSPECTOR_PHOTOS or parcel.id in manual:
            continue
        pool = INSPECTOR_PHOTOS[key]
        filename = pool[counters.get(key, 0) % len(pool)]
        counters[key] = counters.get(key, 0) + 1
        photos = session.exec(select(Photo).where(Photo.parcel_id == parcel.id, Photo.source == "inspector")).all()
        if _replace_photos(session, list(photos), _read(filename), parcel_id=parcel.id, source="inspector"):
            changed.append(parcel)
    session.commit()
    return changed


def replace_seed_placeholders(session: Session) -> list[Signal]:
    """Заменить нарисованные заглушки у демо-сигналов настоящими фото (повторный запуск ничего не меняет)."""
    replaced = []
    rows = session.exec(select(Signal).where(Signal.source == "seed",
                                             Signal.description.in_(list(SEED_SIGNAL_PHOTOS)))).all()
    for s in rows:
        photos = session.exec(select(Photo).where(Photo.signal_id == s.id)).all()
        if _replace_photos(session, list(photos), seed_photo(s.description), signal_id=s.id, source="citizen"):
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
        inspected = set_inspector_photos(session)
        created = add_real_photo_signals(session)
    print(f"Заглушки заменены настоящими фото: {len(replaced)}{codes(replaced)}")
    print(f"Фотофиксация инспектора обновлена на участках: {len(inspected)}"
          + (f" ({', '.join(p.cadastral_no for p in inspected)})" if inspected else ""))
    print(f"Добавлено сигналов с настоящими фото: {len(created)}{codes(created)}")


if __name__ == "__main__":
    main()
