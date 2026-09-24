"""Маршрут выезда инспектора: просроченные нарушения, участки на проверке и новые сигналы.

Порядок объезда — жадный «ближайший сосед» от офиса + улучшение 2-opt (для десятков точек достаточно).
"""
from sqlmodel import Session, select

from app.config import settings
from app.models import Parcel, Signal
from app.services import geo
from app.services.parcels import compute_color, is_overdue, open_signal_counts

MAX_STOPS = 10  # ссылка Google Maps: старт + 9 промежуточных точек + финиш


def _stops(session: Session) -> list[dict]:
    counts = open_signal_counts(session)
    stops = []
    for p in session.exec(select(Parcel)).all():
        color = compute_color(p, counts.get(p.id, 0))
        if is_overdue(p):
            reason, priority = "overdue", 0
        elif color == "yellow":
            reason, priority = "check", 1
        else:
            continue
        lat, lon = geo.centroid(p.geometry)
        stops.append({"kind": "parcel", "id": p.id, "label": p.cadastral_no, "address": p.address,
                      "reason": reason, "priority": priority, "lat": lat, "lon": lon})
    for s in session.exec(select(Signal).where(Signal.parcel_id.is_(None), Signal.duplicate_of.is_(None),
                                               Signal.status.in_(("new", "checking")))).all():
        stops.append({"kind": "signal", "id": s.id, "label": s.code, "address": "", "reason": "signal",
                      "priority": 2, "lat": s.lat, "lon": s.lon})
    stops.sort(key=lambda x: x["priority"])
    return stops[:MAX_STOPS]


def _length(points: list[tuple[float, float]]) -> float:
    return sum(geo.distance_m(*points[i], *points[i + 1]) for i in range(len(points) - 1))


def plan(session: Session) -> dict:
    start = (settings.office_lat, settings.office_lon)
    remaining = _stops(session)
    order: list[dict] = []
    current = start
    while remaining:
        nxt = min(remaining, key=lambda s: geo.distance_m(*current, s["lat"], s["lon"]))
        order.append(nxt)
        remaining.remove(nxt)
        current = (nxt["lat"], nxt["lon"])

    improved = True
    while improved and len(order) > 3:  # 2-opt без возврата в офис
        improved = False
        for i in range(len(order) - 1):
            for j in range(i + 2, len(order) + 1):
                pts = [start] + [(s["lat"], s["lon"]) for s in order]
                a, b = pts[i], pts[i + 1]
                c, d = pts[j], pts[j + 1] if j + 1 < len(pts) else None
                before = geo.distance_m(*a, *b) + (geo.distance_m(*c, *d) if d else 0)
                after = geo.distance_m(*a, *c) + (geo.distance_m(*b, *d) if d else 0)
                if after + 1 < before:
                    order[i:j] = reversed(order[i:j])
                    improved = True

    points = [start] + [(s["lat"], s["lon"]) for s in order]
    return {
        "start": {"lat": start[0], "lon": start[1]},
        "stops": [{k: v for k, v in s.items() if k != "priority"} for s in order],
        "distance_km": round(_length(points) / 1000, 1),
    }
