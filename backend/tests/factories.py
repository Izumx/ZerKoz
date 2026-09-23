from app.models import Parcel


def square(lon: float, lat: float, size: float = 0.01) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size], [lon, lat + size], [lon, lat]]],
    }


def make_parcel(session, n: int = 1, lon: float = 71.0, lat: float = 42.0, **kw) -> Parcel:
    parcel = Parcel(
        cadastral_no=kw.pop("cadastral_no", f"06-097-001-{n:03d}"),
        purpose=kw.pop("purpose", "izhs"),
        area_ha=kw.pop("area_ha", 1.0),
        geometry=kw.pop("geometry", square(lon, lat)),
        ndvi_series=kw.pop("ndvi_series", [0.5] * 12),
        **kw,
    )
    session.add(parcel)
    session.commit()
    return parcel
