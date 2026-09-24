import re

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.events import bus
from app.models import APPLICATION_STAGES, Application, ApplicationSubscription, utcnow
from app.services import NotFound, TransitionError, notify

_KZ = re.compile(r"^KZ-?(\d{4})-?(\d{1,3})$")
_SIG = re.compile(r"^SIG-?(\d{1,6})$")
_LOOKALIKES = str.maketrans({"К": "K", "З": "Z", "С": "C", "–": "-", "—": "-", "_": "-", "‑": "-"})


def normalize_code(text: str) -> tuple[str, str] | None:
    """Распознать трек-номер заявления (KZ-2026-042) или сигнала (SIG-0007) в свободном вводе."""
    raw = re.sub(r"\s+", "", text.upper().translate(_LOOKALIKES))
    if m := _KZ.match(raw):
        return "application", f"KZ-{m.group(1)}-{int(m.group(2)):03d}"
    if m := _SIG.match(raw):
        return "signal", f"SIG-{int(m.group(1)):04d}"
    return None


def find(session: Session, track_no: str) -> Application | None:
    return session.exec(select(Application).where(Application.track_no == track_no)).first()


def get(session: Session, track_no: str) -> Application:
    app = find(session, track_no)
    if app is None:
        raise NotFound(f"Заявление {track_no} не найдено")
    return app


def subscriber_counts(session: Session) -> dict[str, int]:
    rows = session.exec(
        select(ApplicationSubscription.track_no, func.count()).group_by(ApplicationSubscription.track_no)
    ).all()
    return dict(rows)


def application_dict(app: Application, subscribers: int = 0) -> dict:
    return {
        "track_no": app.track_no,
        "applicant": app.applicant,
        "type": app.type,
        "stage": app.stage,
        "note_ru": app.note_ru,
        "note_kz": app.note_kz,
        "subscribers": subscribers,
        "updated_at": app.updated_at.isoformat(),
    }


def list_all(session: Session) -> list[dict]:
    counts = subscriber_counts(session)
    apps = session.exec(select(Application).order_by(Application.track_no.desc())).all()
    return [application_dict(a, counts.get(a.track_no, 0)) for a in apps]


def update(session: Session, track_no: str, *, stage: str | None = None,
           note_ru: str | None = None, note_kz: str | None = None) -> Application:
    """Сменить этап / пояснение и уведомить подписанных жителей."""
    app = get(session, track_no)
    if stage is not None and stage not in APPLICATION_STAGES:
        raise TransitionError(f"Неизвестный этап: {stage}")
    changed = False
    for field, value in (("stage", stage), ("note_ru", note_ru), ("note_kz", note_kz)):
        if value is not None and getattr(app, field) != value:
            setattr(app, field, value)
            changed = True
    if not changed:
        return app
    app.updated_at = utcnow()
    session.add(app)
    session.commit()
    subs = session.exec(select(ApplicationSubscription).where(ApplicationSubscription.track_no == track_no)).all()
    notify.application_stage_changed(app, [(s.chat_id, s.lang) for s in subs])
    bus.publish("application.updated", {"track_no": track_no})
    return app


def subscribe(session: Session, track_no: str, chat_id: int, lang: str) -> None:
    get(session, track_no)
    session.exec(
        insert(ApplicationSubscription)
        .values(track_no=track_no, chat_id=chat_id, lang=lang, created_at=utcnow())
        .on_conflict_do_update(index_elements=["track_no", "chat_id"], set_={"lang": lang})
    )
    session.commit()


def is_subscribed(session: Session, track_no: str, chat_id: int) -> bool:
    return session.exec(select(ApplicationSubscription).where(
        ApplicationSubscription.track_no == track_no, ApplicationSubscription.chat_id == chat_id)).first() is not None


def unsubscribe(session: Session, track_no: str, chat_id: int) -> None:
    sub = session.exec(select(ApplicationSubscription).where(
        ApplicationSubscription.track_no == track_no, ApplicationSubscription.chat_id == chat_id)).first()
    if sub:
        session.delete(sub)
        session.commit()
