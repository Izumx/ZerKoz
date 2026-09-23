"""Уведомления жителя о смене статуса сигнала.

Сервисный слой не знает о Telegram: бот при старте регистрирует свою реализацию через set_notifier().
"""
import logging
from collections.abc import Callable

from app.models import Signal

log = logging.getLogger(__name__)

Notifier = Callable[[Signal], None]
_notifier: Notifier | None = None


def set_notifier(fn: Notifier | None) -> None:
    global _notifier
    _notifier = fn


def signal_status_changed(signal: Signal) -> None:
    if _notifier is None or signal.tg_chat_id is None:
        return
    try:
        _notifier(signal)
    except Exception:  # уведомление не должно ломать смену статуса
        log.exception("Не удалось уведомить жителя о %s", signal.code)
