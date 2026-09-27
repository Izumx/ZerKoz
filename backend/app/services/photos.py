"""Фото: проверка, что это изображение, и хранение в БД."""
import io
import uuid

from PIL import Image
from sqlmodel import Session, select

from app.models import Photo, PhotoBlob
from app.services import ServiceError

MAX_BYTES = 10 * 1024 * 1024
_TYPES = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp"),
          "GIF": ("gif", "image/gif"), "MPO": ("jpg", "image/jpeg"), "HEIF": ("heic", "image/heif")}


class PhotoError(ServiceError):
    pass


def save_photo(
    session: Session,
    data: bytes,
    *,
    parcel_id: int | None = None,
    signal_id: int | None = None,
    source: str = "inspector",
) -> Photo:
    """Проверить, что это изображение, и сохранить в БД (без commit)."""
    if len(data) > MAX_BYTES:
        raise PhotoError("Файл больше 10 МБ")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:
        raise PhotoError("Файл не является изображением") from exc
    ext, content_type = _TYPES.get(fmt or "", ("jpg", "image/jpeg"))
    photo = Photo(path=f"{uuid.uuid4().hex}.{ext}", content_type=content_type, parcel_id=parcel_id,
                  signal_id=signal_id, source=source)
    session.add(photo)
    session.flush()
    session.add(PhotoBlob(photo_id=photo.id, data=data))
    return photo


def load(session: Session, name: str) -> tuple[bytes, str] | None:
    row = session.exec(
        select(PhotoBlob.data, Photo.content_type).join(Photo, Photo.id == PhotoBlob.photo_id).where(Photo.path == name)
    ).first()
    return (row[0], row[1]) if row else None


def photo_url(photo: Photo) -> str:
    return f"/media/{photo.path}"


def photo_dict(photo: Photo) -> dict:
    return {
        "id": photo.id,
        "url": photo_url(photo),
        "source": photo.source,
        "signal_id": photo.signal_id,
        "created_at": photo.created_at.isoformat(),
    }
