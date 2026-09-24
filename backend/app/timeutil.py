"""Время Казахстана. С 2024 г. вся страна живёт по UTC+5 — серверный часовой пояс не важен."""
from datetime import date, datetime, timedelta, timezone

KZ_TZ = timezone(timedelta(hours=5))


def now_kz() -> datetime:
    return datetime.now(KZ_TZ)


def today_kz() -> date:
    return now_kz().date()
