from aiogram import Router

from app.bot.handlers import knowledge, report, start, status


def build_router() -> Router:
    """Порядок важен: кнопки меню и «Отмена» работают из любого состояния, fallback — последним."""
    root = Router(name="root")
    root.include_routers(start.router, status.router, knowledge.router, report.router, status.fallback_router)
    return root
