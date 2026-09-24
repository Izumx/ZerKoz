"""Публичные данные для Telegram Mini App и проверка подписи initData.

Проверка по документации Telegram: secret = HMAC_SHA256("WebAppData", bot_token),
hash = hex(HMAC_SHA256(secret, data_check_string)), где data_check_string — пары key=value
(кроме hash), отсортированные по ключу и соединённые переводом строки.
"""
import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import parse_qsl

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Parcel, Signal, utcnow

INIT_DATA_TTL = 24 * 3600
PUBLIC_STATUSES = ("new", "checking", "confirmed", "resolved")  # отклонённые не показываем
PUBLIC_WINDOW = timedelta(days=90)
COORD_DIGITS = 4  # ≈ 10 м — достаточно для карты района, без точного адреса


def validate_init_data(init_data: str, bot_token: str, now: float | None = None) -> dict | None:
    """Вернуть пользователя Telegram, если подпись верна и данные свежие, иначе None."""
    if not init_data or not bot_token:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", "")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return None
    if (now or time.time()) - int(pairs.get("auth_date", "0")) > INIT_DATA_TTL:
        return None
    try:
        return json.loads(pairs.get("user", "{}")) or None
    except json.JSONDecodeError:
        return None


def public_signals(session: Session) -> list[dict]:
    """Сигналы района для жителей: без описаний, фото и контактов, координаты округлены."""
    since = utcnow() - PUBLIC_WINDOW
    reports = dict(session.exec(
        select(Signal.duplicate_of, func.count()).where(Signal.duplicate_of.is_not(None)).group_by(Signal.duplicate_of)
    ).all())
    rows = session.exec(
        select(Signal).where(Signal.duplicate_of.is_(None), Signal.status.in_(PUBLIC_STATUSES),
                             Signal.created_at >= since).order_by(Signal.created_at.desc())
    ).all()
    return [
        {
            "code": s.code,
            "lat": round(s.lat, COORD_DIGITS),
            "lon": round(s.lon, COORD_DIGITS),
            "status": s.status,
            "violation": s.suggested_violation,
            "reports": 1 + reports.get(s.id, 0),
            "created_at": s.created_at.isoformat(),
        }
        for s in rows
    ]


def my_signals(session: Session, chat_id: int) -> list[dict]:
    """Сигналы самого жителя — ему можно показать и описание."""
    rows = session.exec(select(Signal).where(Signal.tg_chat_id == chat_id).order_by(Signal.created_at.desc())).all()
    parcel_ids = {s.parcel_id for s in rows if s.parcel_id}
    cad = dict(session.exec(select(Parcel.id, Parcel.cadastral_no).where(Parcel.id.in_(parcel_ids))).all()) \
        if parcel_ids else {}
    return [
        {
            "code": s.code,
            "lat": s.lat,
            "lon": s.lon,
            "status": s.status,
            "violation": s.suggested_violation,
            "description": s.description,
            "cadastral_no": cad.get(s.parcel_id),
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in rows
    ]
