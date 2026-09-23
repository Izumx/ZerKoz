from datetime import date

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session
from app.events import bus
from app.services import history, parcels
from app.services.photos import save_photo

router = APIRouter(tags=["parcels"])


class ParcelPatch(BaseModel):
    lifecycle: str | None = None
    violation_type: str | None = None
    deadline: date | None = None
    under_check: bool | None = None


@router.get("/parcels")
def list_parcels(session: Session = Depends(get_session)) -> dict:
    return parcels.feature_collection(session)


@router.get("/parcels/{parcel_id}")
def get_parcel(parcel_id: int, session: Session = Depends(get_session)) -> dict:
    return parcels.parcel_detail(session, parcel_id)


@router.patch("/parcels/{parcel_id}")
def patch_parcel(parcel_id: int, body: ParcelPatch, session: Session = Depends(get_session)) -> dict:
    parcels.update_parcel(session, parcel_id, body.model_dump(exclude_unset=True))
    return parcels.parcel_detail(session, parcel_id)


@router.post("/parcels/{parcel_id}/photos")
def upload_photos(
    parcel_id: int, files: list[UploadFile] = File(...), session: Session = Depends(get_session)
) -> dict:
    parcels.get_parcel(session, parcel_id)
    try:
        for f in files:
            save_photo(session, f.file.read(), parcel_id=parcel_id, source="inspector")
        history.log(session, "parcel", parcel_id, "photos", {"count": len(files)})
        session.commit()
    except Exception:
        session.rollback()
        raise
    bus.publish("parcel.updated", {"id": parcel_id})
    return parcels.parcel_detail(session, parcel_id)
