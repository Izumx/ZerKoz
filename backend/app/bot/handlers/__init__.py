from aiogram import Router

from app.bot.handlers import knowledge, report, start, status

_root: Router | None = None


def build_router() -> Router:
    """Порядок важен: кнопки меню и «Отмена» работают из любого состояния, fallback — последним.

    Дочерние роутеры — синглтоны модулей, поэтому корневой роутер создаётся один раз.
    """
    global _root
    if _root is None:
        _root = Router(name="root")
        _root.include_routers(start.router, status.router, knowledge.router, report.router, status.fallback_router)
    return _root
