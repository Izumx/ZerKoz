"""Уведомления жителей.

Сервисный слой не знает о Telegram: бот при старте регистрирует свои реализации через set_notifier().
"""
import logging
from collections.abc import Callable

from app.models import Application, Signal

log = logging.getLogger(__name__)

SignalNotifier = Callable[[Signal], None]
ApplicationNotifier = Callable[[Application, int, str], None]  # заявление, chat_id, язык

_signal: SignalNotifier | None = None
_application: ApplicationNotifier | None = None


def set_notifier(signal_fn: SignalNotifier | None, application_fn: ApplicationNotifier | None = None) -> None:
    global _signal, _application
    _signal, _application = signal_fn, application_fn


def signal_status_changed(signal: Signal) -> None:
    if _signal is None or signal.tg_chat_id is None:
        return
    try:
        _signal(signal)
    except Exception:  # уведомление не должно ломать смену статуса
        log.exception("Не удалось уведомить жителя о %s", signal.code)


def application_stage_changed(application: Application, subscribers: list[tuple[int, str]]) -> None:
    if _application is None:
        return
    for chat_id, lang in subscribers:
        try:
            _application(application, chat_id, lang)
        except Exception:
            log.exception("Не удалось уведомить подписчика %s о %s", chat_id, application.track_no)
