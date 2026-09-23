from sqlmodel import Session

from app.models import BotUser


def get_lang(session: Session, chat_id: int) -> str | None:
    user = session.get(BotUser, chat_id)
    return user.lang if user else None


def set_lang(session: Session, chat_id: int, lang: str) -> None:
    user = session.get(BotUser, chat_id) or BotUser(chat_id=chat_id)
    user.lang = lang
    session.add(user)
    session.commit()
