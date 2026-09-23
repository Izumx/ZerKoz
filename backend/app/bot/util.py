import asyncio
import re
from collections.abc import Callable
from typing import TypeVar

from app import db
from app.services import botusers

T = TypeVar("T")
_lang_cache: dict[int, str] = {}
_COORDS = re.compile(r"^\s*(-?\d{1,2}(?:[.,]\d+)?)\s*[,;\s]\s*(-?\d{1,3}(?:[.,]\d+)?)\s*$")


async def db_call(fn: Callable[..., T], *args, **kwargs) -> T:
    """Выполнить синхронную сервисную функцию fn(session, ...) в отдельном потоке."""
    def run() -> T:
        with db.new_session() as session:
            return fn(session, *args, **kwargs)

    return await asyncio.to_thread(run)


async def get_lang(chat_id: int) -> str | None:
    if chat_id not in _lang_cache:
        lang = await db_call(botusers.get_lang, chat_id)
        if lang is None:
            return None
        _lang_cache[chat_id] = lang
    return _lang_cache[chat_id]


async def set_lang(chat_id: int, lang: str) -> None:
    await db_call(botusers.set_lang, chat_id, lang)
    _lang_cache[chat_id] = lang


def parse_coords(text: str) -> tuple[float, float] | None:
    """«42.90, 71.37» / «42,90 71,37» → (lat, lon)."""
    m = _COORDS.match(text or "")
    if not m:
        return None
    lat, lon = (float(g.replace(",", ".")) for g in m.groups())
    return (lat, lon) if -90 <= lat <= 90 and -180 <= lon <= 180 else None
