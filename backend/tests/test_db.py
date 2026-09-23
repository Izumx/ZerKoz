from sqlmodel import select

from app.models import Parcel


def test_parcel_roundtrip_with_jsonb(session):
    geom = {"type": "Polygon", "coordinates": [[[71.0, 42.0], [71.1, 42.0], [71.1, 42.1], [71.0, 42.0]]]}
    session.add(Parcel(cadastral_no="06-097-001-001", purpose="izhs", area_ha=0.1, geometry=geom, ndvi_series=[0.1]))
    session.commit()

    loaded = session.exec(select(Parcel)).one()
    assert loaded.geometry == geom
    assert loaded.lifecycle == "none"
    assert loaded.updated_at.tzinfo is not None
