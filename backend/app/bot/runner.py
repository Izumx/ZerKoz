"""Запуск Telegram-бота внутри процесса FastAPI и доставка уведомлений жителям.

Режимы: polling (по умолчанию, локально) или webhook, если задан PUBLIC_URL —
тогда бот работает и на хостингах, которые «усыпляют» сервис без входящих запросов.
"""
import asyncio
import hashlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent
from fastapi import Request
from fastapi.responses import JSONResponse

from app import runtime
from app.bot import keyboards as kb
from app.bot.i18n import APPLICATION_TYPES, signal_status, stage, t
from app.bot.handlers import build_router
from app.bot.util import get_lang
from app.config import settings
from app.models import Application, Signal
from app.services import notify

log = logging.getLogger("zherkoz.bot")

COMMANDS = {
    "ru": [("start", "Главное меню"), ("status", "Статус заявления"), ("report", "Сообщить о нарушении"),
           ("help", "База знаний"), ("lang", "Язык / Тіл")],
    "kk": [("start", "Басты мәзір"), ("status", "Өтініш мәртебесі"), ("report", "Бұзушылық туралы хабарлау"),
           ("help", "Анықтамалық"), ("lang", "Тіл / Язык")],
}

_active: tuple[Bot, Dispatcher] | None = None
_tasks: set[asyncio.Task] = set()


def webhook_secret(token: str) -> str:
    return hashlib.sha256(f"zherkoz:{token}".encode()).hexdigest()[:48]


def _deliver(loop: asyncio.AbstractEventLoop, coro) -> None:
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is loop:
        loop.create_task(coro)
    else:  # вызов из потока FastAPI
        asyncio.run_coroutine_threadsafe(coro, loop)


def make_notifier(bot: Bot, loop: asyncio.AbstractEventLoop):
    def notifier(signal: Signal) -> None:
        lang = signal.lang or "ru"
        emoji, status, hint = signal_status(lang, signal.status)
        text = t(lang, "notify_status", code=signal.code, emoji=emoji, status=status, hint=hint)
        _deliver(loop, bot.send_message(signal.tg_chat_id, text, reply_markup=kb.main_menu(lang)))

    return notifier


def make_application_notifier(bot: Bot, loop: asyncio.AbstractEventLoop):
    def notifier(app: Application, chat_id: int, lang: str) -> None:
        emoji, stage_name = stage(lang, app.stage)
        text = t(lang, "notify_application", code=app.track_no, type=APPLICATION_TYPES[lang][app.type],
                 emoji=emoji, stage=stage_name, note=app.note_kz if lang == "kz" else app.note_ru)
        _deliver(loop, bot.send_message(chat_id, text, reply_markup=kb.main_menu(lang)))

    return notifier


async def on_error(event: ErrorEvent) -> None:
    log.exception("Ошибка в обработчике бота", exc_info=event.exception)
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message:
        lang = await get_lang(message.chat.id) or "ru"
        await message.answer(t(lang, "error"), reply_markup=kb.main_menu(lang))


def _storage() -> BaseStorage:
    if settings.redis_url:
        from aiogram.fsm.storage.redis import RedisStorage

        log.info("Состояние диалогов бота хранится в Redis")
        return RedisStorage.from_url(settings.redis_url)
    return MemoryStorage()


async def handle_webhook(request: Request) -> JSONResponse:
    if not settings.bot_token or request.headers.get("x-telegram-bot-api-secret-token") != webhook_secret(settings.bot_token):
        return JSONResponse({"detail": "forbidden"}, status_code=403)
    if _active is None:
        return JSONResponse({"detail": "bot is starting"}, status_code=503)  # Telegram повторит позже
    bot, dp = _active
    task = asyncio.create_task(dp.feed_raw_update(bot, await request.json()))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return JSONResponse({"ok": True})


async def run_bot(token: str) -> None:
    global _active
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=_storage())
    dp.include_router(build_router())
    dp.errors.register(on_error)
    try:
        while True:
            try:
                me = await bot.get_me()
                break
            except TelegramUnauthorizedError:
                log.error("BOT_TOKEN недействителен — бот не запущен")
                return
            except Exception as exc:
                log.warning("Telegram недоступен (%s), повтор через 10 с", exc)
                await asyncio.sleep(10)
        for lang_code, commands in COMMANDS.items():
            await bot.set_my_commands([BotCommand(command=c, description=d) for c, d in commands],
                                      language_code=None if lang_code == "ru" else lang_code)
        loop = asyncio.get_running_loop()
        notify.set_notifier(make_notifier(bot, loop), make_application_notifier(bot, loop))
        runtime.bot_username = me.username
        _active = (bot, dp)

        if settings.webhook_base:
            url = f"{settings.webhook_base}/tg/webhook"
            await bot.set_webhook(url, secret_token=webhook_secret(token),
                                  allowed_updates=dp.resolve_used_update_types())
            log.info("Telegram-бот @%s запущен (webhook: %s)", me.username, url)
            await asyncio.Event().wait()
        else:
            await bot.delete_webhook()
            log.info("Telegram-бот @%s запущен (polling)", me.username)
            await dp.start_polling(bot, handle_signals=False)
    finally:
        _active = None
        notify.set_notifier(None)
        runtime.bot_username = None
        await dp.storage.close()
        await bot.session.close()
