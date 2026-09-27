from datetime import date, datetime, timezone

from sqlalchemy import BigInteger, DateTime, LargeBinary, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

PURPOSES = ("izhs", "agri", "commercial", "industrial", "lph")
LIFECYCLES = ("none", "detected", "in_progress", "resolved", "returned")
VIOLATION_TYPES = ("unused", "seizure", "dump")
SIGNAL_STATUSES = ("new", "checking", "confirmed", "rejected", "resolved")
APPLICATION_STAGES = ("review", "inspection", "approved", "rejected")
APPLICATION_TYPES = ("change_purpose", "lease_extension", "izhs")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts() -> Field:
    return Field(default_factory=utcnow, sa_type=DateTime(timezone=True), nullable=False)


class Parcel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cadastral_no: str = Field(unique=True, index=True)
    purpose: str
    area_ha: float
    address: str = ""
    owner: str = ""
    geometry: dict = Field(sa_type=JSONB, nullable=False)
    lifecycle: str = "none"
    violation_type: str | None = None
    deadline: date | None = None
    under_check: bool = False
    ndvi_series: list = Field(default_factory=list, sa_type=JSONB, nullable=False)
    ndvi_source: str = "simulation"  # simulation | sentinel-2
    ndvi_months: list = Field(default_factory=list, sa_type=JSONB, nullable=False)  # «2026-09» для каждой точки
    updated_at: datetime = _ts()


class Signal(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str | None = Field(default=None, unique=True, index=True)
    lat: float
    lon: float
    description: str = ""
    source: str = "telegram"
    tg_chat_id: int | None = Field(default=None, sa_type=BigInteger, index=True)
    lang: str = "ru"
    status: str = "new"
    parcel_id: int | None = Field(default=None, foreign_key="parcel.id", index=True)
    # повторное сообщение о том же месте: статус ведёт основной сигнал
    duplicate_of: int | None = Field(default=None, foreign_key="signal.id", index=True)
    suggested_violation: str | None = None
    ai: dict | None = Field(default=None, sa_type=JSONB)
    created_at: datetime = _ts()
    updated_at: datetime = _ts()


class Photo(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    path: str = Field(unique=True, index=True)  # публичное имя: <uuid>.<ext>
    content_type: str = "image/jpeg"
    parcel_id: int | None = Field(default=None, foreign_key="parcel.id", index=True)
    signal_id: int | None = Field(default=None, foreign_key="signal.id", index=True)
    source: str = "inspector"
    created_at: datetime = _ts()


class PhotoBlob(SQLModel, table=True):
    """Содержимое фото хранится в БД — не зависит от временного диска хостинга."""

    photo_id: int = Field(primary_key=True, foreign_key="photo.id")
    data: bytes = Field(sa_type=LargeBinary, nullable=False)


class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    track_no: str = Field(unique=True, index=True)
    applicant: str
    type: str
    stage: str = "review"
    note_ru: str = ""
    note_kz: str = ""
    updated_at: datetime = _ts()


class ApplicationSubscription(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("track_no", "chat_id"),)

    id: int | None = Field(default=None, primary_key=True)
    track_no: str = Field(index=True)
    chat_id: int = Field(sa_type=BigInteger)
    lang: str = "ru"
    created_at: datetime = _ts()


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    entity: str = Field(index=True)
    entity_id: int = Field(index=True)
    action: str
    payload: dict = Field(default_factory=dict, sa_type=JSONB, nullable=False)
    created_at: datetime = _ts()


class BotUser(SQLModel, table=True):
    chat_id: int = Field(primary_key=True, sa_type=BigInteger)
    lang: str = "ru"
    created_at: datetime = _ts()
