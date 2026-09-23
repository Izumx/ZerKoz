"""Запуск Telegram-бота внутри процесса FastAPI и доставка уведомлений жителям."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from app import runtime
from app.bot import keyboards as kb
from app.bot.handlers import build_router
from app.bot.i18n import signal_status, t
from app.bot.util import get_lang
from app.models import Signal
from app.services import notify

log = logging.getLogger("zherkoz.bot")

COMMANDS = {
    "ru": [("start", "Главное меню"), ("status", "Статус заявления"), ("report", "Сообщить о нарушении"),
           ("help", "База знаний"), ("lang", "Язык / Тіл")],
    "kk": [("start", "Басты мәзір"), ("status", "Өтініш мәртебесі"), ("report", "Бұзушылық туралы хабарлау"),
           ("help", "Анықтамалық"), ("lang", "Тіл / Язык")],
}


def make_notifier(bot: Bot, loop: asyncio.AbstractEventLoop):
    def notifier(signal: Signal) -> None:
        lang = signal.lang or "ru"
        emoji, status, hint = signal_status(lang, signal.status)
        text = t(lang, "notify_status", code=signal.code, emoji=emoji, status=status, hint=hint)
        coro = bot.send_message(signal.tg_chat_id, text, reply_markup=kb.main_menu(lang))
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(coro)
        else:  # вызов из потока FastAPI
            asyncio.run_coroutine_threadsafe(coro, loop)

    return notifier


async def on_error(event: ErrorEvent) -> None:
    log.exception("Ошибка в обработчике бота", exc_info=event.exception)
    update = event.update
    message = update.message or (update.callback_query.message if update.callback_query else None)
    if message:
        lang = await get_lang(message.chat.id) or "ru"
        await message.answer(t(lang, "error"), reply_markup=kb.main_menu(lang))


async def run_bot(token: str) -> None:
    bot = Bot(token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
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
        runtime.bot_username = me.username
        notify.set_notifier(make_notifier(bot, asyncio.get_running_loop()))
        log.info("Telegram-бот @%s запущен", me.username)
        await dp.start_polling(bot, handle_signals=False)
    finally:
        notify.set_notifier(None)
        runtime.bot_username = None
        await bot.session.close()
