"""Фото: проверка, извлечение EXIF (координаты и время съёмки), хранение в БД."""
import io
import uuid
from datetime import datetime

from PIL import Image
from sqlmodel import Session, select

from app.models import Photo, PhotoBlob
from app.services import ServiceError, geo
from app.timeutil import KZ_TZ

MAX_BYTES = 10 * 1024 * 1024
_TYPES = {"JPEG": ("jpg", "image/jpeg"), "PNG": ("png", "image/png"), "WEBP": ("webp", "image/webp"),
          "GIF": ("gif", "image/gif"), "MPO": ("jpg", "image/jpeg"), "HEIF": ("heic", "image/heif")}
GPS_IFD, EXIF_IFD = 0x8825, 0x8769
EXIF_MAX_DISTANCE_M = 300
EXIF_MAX_AGE_DAYS = 7


class PhotoError(ServiceError):
    pass


def _dms_to_deg(dms, ref) -> float:
    d, m, s = (float(x) for x in dms)
    value = d + m / 60 + s / 3600
    return -value if str(ref).upper() in ("S", "W") else value


def read_exif(img: Image.Image) -> dict | None:
    """Координаты и время съёмки из EXIF. Telegram удаляет EXIF у сжатых фото — сохраняется только у файлов."""
    try:
        exif = img.getexif()
    except Exception:
        return None
    result: dict = {}
    gps = exif.get_ifd(GPS_IFD)
    if gps and 2 in gps and 4 in gps:
        try:
            result["lat"] = round(_dms_to_deg(gps[2], gps.get(1, "N")), 6)
            result["lon"] = round(_dms_to_deg(gps[4], gps.get(3, "E")), 6)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    raw = exif.get_ifd(EXIF_IFD).get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
    if raw:
        try:
            taken = datetime.strptime(str(raw).strip("\x00 "), "%Y:%m:%d %H:%M:%S").replace(tzinfo=KZ_TZ)
            result["taken_at"] = taken.isoformat()
        except ValueError:
            pass
    return result or None


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
            exif = read_exif(img)
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
    except Exception as exc:
        raise PhotoError("Файл не является изображением") from exc
    ext, content_type = _TYPES.get(fmt or "", ("jpg", "image/jpeg"))
    photo = Photo(path=f"{uuid.uuid4().hex}.{ext}", content_type=content_type, parcel_id=parcel_id,
                  signal_id=signal_id, source=source, exif=exif)
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


def exif_check(photo: Photo, lat: float, lon: float, reported_at: datetime) -> dict:
    """Сверка EXIF с местом и временем сигнала: ok | far | old | no_gps | none."""
    exif = photo.exif or {}
    if not exif:
        return {"status": "none"}
    result: dict = {"taken_at": exif.get("taken_at")}
    if "lat" in exif and "lon" in exif:
        result["distance_m"] = round(geo.distance_m(lat, lon, exif["lat"], exif["lon"]))
    if exif.get("taken_at"):
        age = reported_at - datetime.fromisoformat(exif["taken_at"])
        result["age_days"] = round(age.total_seconds() / 86400, 1)
    if result.get("distance_m", 0) > EXIF_MAX_DISTANCE_M:
        result["status"] = "far"
    elif result.get("age_days", 0) > EXIF_MAX_AGE_DAYS:
        result["status"] = "old"
    elif "distance_m" in result:
        result["status"] = "ok"
    else:
        result["status"] = "no_gps"
    return result


def photo_dict(photo: Photo, check: dict | None = None) -> dict:
    data = {
        "id": photo.id,
        "url": photo_url(photo),
        "source": photo.source,
        "signal_id": photo.signal_id,
        "created_at": photo.created_at.isoformat(),
    }
    if check is not None:
        data["exif_check"] = check
    return data
