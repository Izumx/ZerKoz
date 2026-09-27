"""Генерация демо-данных вокруг г. Тараз.

python -m app.seed.generate [--reset]
"""
import argparse
import math
import random
from datetime import date, timedelta

from sqlmodel import SQLModel, Session, select

from app import db
from app.config import settings
from app.models import Application, Event, Parcel, Signal, utcnow
from app.seed.data import APPLICATIONS, CLUSTERS, OWNERS
from app.seed.real_photos import add_real_photo_signals, seed_photo, set_inspector_photos
from app.services import geo, history, signals
from app.timeutil import today_kz

M_PER_DEG = geo.M_PER_DEG
VIOLATION_BY_PURPOSE = {"agri": "unused", "izhs": "unused", "lph": "seizure", "commercial": "seizure",
                        "industrial": "dump"}


def lot_polygon(lat: float, lon: float, area_ha: float, angle_deg: float, rng: random.Random) -> dict:
    """Прямоугольный участок заданной площади с небольшими неровностями границ."""
    ratio = rng.uniform(1.4, 2.4)
    w = math.sqrt(area_ha * 10_000 / ratio)
    h = w * ratio
    a = math.radians(angle_deg + rng.uniform(-3, 3))
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    kx = M_PER_DEG * math.cos(math.radians(lat))
    ring = []
    for x, y in corners:
        x, y = x * rng.uniform(0.96, 1.04), y * rng.uniform(0.96, 1.04)
        xr, yr = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        ring.append([round(lon + xr / kx, 7), round(lat + yr / M_PER_DEG, 7)])
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def ndvi_series(purpose: str, used: bool, rng: random.Random, months: list[str]) -> list[float]:
    """Используемая сельхозземля — выраженный сезонный пик в июле, заброшенная — плоско и низко."""
    base, amp = {
        "agri": (0.22, 0.55), "lph": (0.25, 0.35), "izhs": (0.25, 0.2),
        "commercial": (0.12, 0.06), "industrial": (0.08, 0.05),
    }[purpose]
    if not used:
        base, amp = 0.1, 0.08
    series = []
    for month in months:
        season = max(0.0, math.cos((int(month[5:]) - 7) / 12 * 2 * math.pi))
        series.append(round(min(0.9, max(0.02, base + amp * season + rng.uniform(-0.03, 0.03))), 2))
    return series


def ndvi_months() -> list[str]:
    """12 месяцев, заканчивая текущим: ['2025-10', …, '2026-09']."""
    today = today_kz()
    months = []
    for back in range(11, -1, -1):
        y, m = divmod(today.year * 12 + today.month - 1 - back, 12)
        months.append(f"{y}-{m + 1:02d}")
    return months


def reset(session: Session) -> None:
    session.close()
    SQLModel.metadata.drop_all(db.engine)
    SQLModel.metadata.create_all(db.engine)


def backdate_events(session: Session, entity: str, entity_id: int, start_days_ago: int) -> None:
    events = session.exec(select(Event).where(Event.entity == entity, Event.entity_id == entity_id)
                          .order_by(Event.id)).all()
    for i, e in enumerate(events):
        e.created_at = utcnow() - timedelta(days=start_days_ago - i * 3, hours=i * 2)
        session.add(e)


def create_parcels(session: Session, rng: random.Random) -> list[Parcel]:
    parcels = []
    owners = iter(rng.sample(OWNERS, len(OWNERS)) * 3)
    for address, district, quarter, purpose, count, (clat, clon), (amin, amax), angle in CLUSTERS:
        cols = math.ceil(math.sqrt(count * 1.5))
        spacing_m = math.sqrt(amax * 10_000 * 2.4) * 1.6
        kx = M_PER_DEG * math.cos(math.radians(clat))
        for i in range(count):
            row, col = divmod(i, cols)
            dx, dy = (col - cols / 2) * spacing_m, (row - 1) * spacing_m
            a = math.radians(angle)
            x, y = dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)
            lat, lon = clat + y / M_PER_DEG, clon + x / kx
            geometry = lot_polygon(lat, lon, rng.uniform(amin, amax), angle, rng)
            parcel = Parcel(
                cadastral_no=f"{district}-{quarter:03d}-{101 + i * 7 + rng.randint(0, 5):03d}",
                purpose=purpose,
                area_ha=round(geo.area_ha(geometry), 4),
                address=address,
                owner=next(owners),
                geometry=geometry,
                ndvi_series=[],
            )
            session.add(parcel)
            parcels.append(parcel)
    session.commit()
    return parcels


def apply_scenarios(session: Session, parcels: list[Parcel], rng: random.Random) -> dict[str, list[Parcel]]:
    """Распределить статусы: 7 красных (3 просрочены), 3 на проверке, 2 закрытых нарушения, остальные зелёные."""
    today = today_kz()
    pool = parcels[:]
    rng.shuffle(pool)
    # (lifecycle, сдвиг дедлайна в днях | None, under_check)
    scenarios = [
        ("in_progress", -12, False), ("in_progress", -4, False), ("detected", -2, False),
        ("in_progress", 18, False), ("in_progress", 45, False), ("detected", None, False), ("detected", None, False),
        ("none", None, True), ("none", None, True), ("none", None, True),
        ("resolved", -20, False), ("returned", -30, False),
    ]
    groups: dict[str, list[Parcel]] = {"red": [], "check": [], "closed": [], "green": []}
    for parcel, (lifecycle, shift, under_check) in zip(pool, scenarios):
        vt = VIOLATION_BY_PURPOSE[parcel.purpose] if lifecycle != "none" else None
        if lifecycle in ("detected", "in_progress", "resolved", "returned"):
            history.log(session, "parcel", parcel.id, "lifecycle", {"from": "none", "to": "detected", "violation_type": vt})
        if lifecycle in ("in_progress", "resolved", "returned"):
            history.log(session, "parcel", parcel.id, "lifecycle",
                        {"from": "detected", "to": "in_progress", "deadline": today + timedelta(days=shift or 30)})
        if lifecycle in ("resolved", "returned"):
            history.log(session, "parcel", parcel.id, "lifecycle", {"from": "in_progress", "to": lifecycle})
        parcel.lifecycle, parcel.violation_type, parcel.under_check = lifecycle, vt, under_check
        parcel.deadline = today + timedelta(days=shift) if shift is not None else None
        session.add(parcel)
        session.flush()
        backdate_events(session, "parcel", parcel.id, start_days_ago=40)
        if lifecycle in ("detected", "in_progress"):
            groups["red"].append(parcel)
        elif under_check:
            groups["check"].append(parcel)
        else:
            groups["closed"].append(parcel)
    groups["green"] = pool[len(scenarios):]
    for parcel in parcels:
        parcel.ndvi_months = ndvi_months()
        parcel.ndvi_series = ndvi_series(parcel.purpose, parcel.violation_type != "unused" or
                                         parcel.lifecycle in ("resolved", "returned"), rng, parcel.ndvi_months)
        session.add(parcel)
    session.commit()
    return groups


def create_signals(session: Session, groups: dict[str, list[Parcel]], rng: random.Random) -> None:
    def point(parcel: Parcel) -> tuple[float, float]:
        return geo.random_point_in(parcel.geometry, rng)

    green = groups["green"]
    specs = [  # (участок | None, kind, описание, статус, дней назад)
        (green[0], "dump", "Свалка бытового мусора на пустом участке, уже неделю никто не убирает", "new", 0.2),
        (green[1], "unused", "Участок заброшен, бурьян выше человеческого роста", "new", 1.3),
        (groups["check"][0], "seizure", "Забор вынесен на тротуар, пройти невозможно", "checking", 3),
        (next(p for p in groups["red"] if p.violation_type == "dump") if any(
            p.violation_type == "dump" for p in groups["red"]) else groups["red"][0],
         "dump", "Промышленные отходы вывозят прямо на соседний участок", "confirmed", 9),
        (green[2], "dump", "Кучка листвы у забора", "rejected", 6),
        (None, "dump", "Стихийная свалка у обочины трассы Тараз — Шымкент", "new", 0.6),
    ]
    first = None
    for parcel, _kind, text, status, days_ago in specs:
        lat, lon = point(parcel) if parcel else (42.8870, 71.3000)
        s = signals.create_signal(session, lat=lat, lon=lon, description=text, source="seed", photos=[seed_photo(text)])
        first = first or s
        if status != "new":
            s.status = status
            history.log(session, "signal", s.id, "status", {"from": "new", "to": status})
        s.created_at = s.updated_at = utcnow() - timedelta(days=days_ago)
        session.add(s)
        session.flush()
        backdate_events(session, "signal", s.id, start_days_ago=int(days_ago))
    session.commit()
    # второй житель сообщает о той же свалке в ~12 м — сигнал автоматически станет повтором первого
    dup_text = "Мусор так и лежит, уже пахнет"
    dup = signals.create_signal(session, lat=first.lat + 0.0001, lon=first.lon + 0.00005,
                                description=dup_text, source="seed", photos=[seed_photo(dup_text)])
    dup.created_at = dup.updated_at = utcnow() - timedelta(hours=2)
    session.add(dup)
    session.commit()


def create_applications(session: Session) -> None:
    for i, (track_no, applicant, type_, stage, note_ru, note_kz) in enumerate(APPLICATIONS):
        session.add(Application(track_no=track_no, applicant=applicant, type=type_, stage=stage,
                                note_ru=note_ru, note_kz=note_kz, updated_at=utcnow() - timedelta(days=10 - i)))
    session.commit()


def generate(session: Session, seed: int = 2026) -> None:
    rng = random.Random(seed)
    parcels = create_parcels(session, rng)
    groups = apply_scenarios(session, parcels, rng)
    set_inspector_photos(session)
    create_signals(session, groups, rng)
    add_real_photo_signals(session, rng)
    create_applications(session)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reset", action="store_true", help="удалить все данные и сгенерировать заново")
    args = parser.parse_args()
    db.ensure_database(settings.database_url)
    with db.new_session() as session:
        if args.reset:  # сначала сброс — старая схема могла не совпадать с моделями
            reset(session)
        else:
            db.init_db()
            if session.exec(select(Parcel)).first():
                print("Данные уже есть. Для пересоздания: python -m app.seed.generate --reset")
                return
    with db.new_session() as session:
        generate(session)
        n_parcels = len(session.exec(select(Parcel)).all())
        n_signals = len(session.exec(select(Signal)).all())
        n_apps = len(session.exec(select(Application)).all())
    print(f"Готово: участков — {n_parcels}, сигналов — {n_signals}, заявлений — {n_apps}.")
    print("Тестовые трек-номера: " + ", ".join(a[0] for a in APPLICATIONS))


if __name__ == "__main__":
    main()
