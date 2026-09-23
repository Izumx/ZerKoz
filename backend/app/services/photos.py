import io
import uuid

from PIL import Image
from sqlmodel import Session

from app.config import settings
from app.models import Photo
from app.services import ServiceError

MAX_BYTES = 10 * 1024 * 1024
_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}


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
    """Проверить, что это изображение, сохранить файл и добавить запись (без commit)."""
    if len(data) > MAX_BYTES:
        raise PhotoError("Файл больше 10 МБ")
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:
        raise PhotoError("Файл не является изображением") from exc
    ext = _EXT.get(fmt or "", ".jpg")
    name = f"{uuid.uuid4().hex}{ext}"
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / name).write_bytes(data)
    photo = Photo(path=name, parcel_id=parcel_id, signal_id=signal_id, source=source)
    session.add(photo)
    return photo


def photo_url(photo: Photo) -> str:
    return f"/uploads/{photo.path}"


def photo_dict(photo: Photo) -> dict:
    return {
        "id": photo.id,
        "url": photo_url(photo),
        "source": photo.source,
        "signal_id": photo.signal_id,
        "created_at": photo.created_at.isoformat(),
    }
