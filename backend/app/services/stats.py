import csv
import io
from datetime import timedelta

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Parcel, Signal, utcnow
from app.services.parcels import OPEN_SIGNAL_STATUSES, compute_color, is_overdue, open_signal_counts

PURPOSE_RU = {"izhs": "ИЖС", "agri": "Сельхозназначение", "commercial": "Коммерческое",
              "industrial": "Промышленное", "lph": "ЛПХ"}
LIFECYCLE_RU = {"none": "Нарушений нет", "detected": "Выявлено нарушение", "in_progress": "В процессе устранения",
                "resolved": "Устранено", "returned": "Возвращено государству"}
VIOLATION_RU = {"unused": "Неиспользование", "seizure": "Самозахват", "dump": "Свалка"}
COLOR_RU = {"green": "Зелёный", "yellow": "Жёлтый", "red": "Красный"}


def dashboard(session: Session) -> dict:
    counts = open_signal_counts(session)
    result = {"total": 0, "green": 0, "yellow": 0, "red": 0, "overdue": 0}
    for p in session.exec(select(Parcel)).all():
        result["total"] += 1
        result[compute_color(p, counts.get(p.id, 0))] += 1
        result["overdue"] += is_overdue(p)

    def count(*conditions) -> int:
        return session.exec(select(func.count()).select_from(Signal).where(*conditions)).one()

    result["signals_new"] = count(Signal.status == "new")
    result["signals_open"] = count(Signal.status.in_(OPEN_SIGNAL_STATUSES))
    result["signals_24h"] = count(Signal.created_at >= utcnow() - timedelta(hours=24))
    return result


def parcels_csv(session: Session) -> str:
    counts = open_signal_counts(session)
    buf = io.StringIO()
    buf.write("﻿")  # BOM — чтобы Excel открыл UTF-8 корректно
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["Кадастровый номер", "Адрес", "Целевое назначение", "Площадь, га", "Пользователь",
                     "Статус", "Этап", "Тип нарушения", "Срок устранения", "Просрочено", "Открытых сигналов"])
    for p in session.exec(select(Parcel).order_by(Parcel.cadastral_no)).all():
        open_count = counts.get(p.id, 0)
        writer.writerow([
            p.cadastral_no, p.address, PURPOSE_RU.get(p.purpose, p.purpose), f"{p.area_ha:.4f}".replace(".", ","),
            p.owner, COLOR_RU[compute_color(p, open_count)], LIFECYCLE_RU.get(p.lifecycle, p.lifecycle),
            VIOLATION_RU.get(p.violation_type or "", ""), p.deadline.isoformat() if p.deadline else "",
            "да" if is_overdue(p) else "", open_count,
        ])
    return buf.getvalue()
