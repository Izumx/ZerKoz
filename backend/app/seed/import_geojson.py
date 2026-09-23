"""Импорт участков из внешнего GeoJSON (задел на интеграцию с ЕГКН / данными акимата).

python -m app.seed.import_geojson parcels.geojson

Поддерживаются Polygon, MultiPolygon (берётся наибольший контур) и Point (строится квадрат по площади).
Поля свойств ищутся по нескольким вариантам имён; существующие участки обновляются по кадастровому номеру.
"""
import json
import math
import sys

from shapely.geometry import mapping, shape
from sqlmodel import Session, select

from app import db
from app.models import PURPOSES, Parcel
from app.services import geo

FIELD_ALIASES = {
    "cadastral_no": ("cadastral_no", "cadastral", "cad_num", "kad_nomer", "kadastr", "кадастровый_номер"),
    "purpose": ("purpose", "target", "naznachenie", "назначение"),
    "area_ha": ("area_ha", "area", "ploshad", "площадь"),
    "address": ("address", "adres", "адрес"),
    "owner": ("owner", "vladelec", "владелец"),
}
PURPOSE_ALIASES = {"ижс": "izhs", "сельхоз": "agri", "сх": "agri", "коммерция": "commercial",
                   "промышленность": "industrial", "лпх": "lph"}


def _prop(props: dict, field: str):
    lowered = {k.lower(): v for k, v in props.items()}
    for alias in FIELD_ALIASES[field]:
        if lowered.get(alias) not in (None, ""):
            return lowered[alias]
    return None


def _square(lat: float, lon: float, area_ha: float) -> dict:
    half = math.sqrt(area_ha * 10_000) / 2
    dlat = half / geo.M_PER_DEG
    dlon = half / (geo.M_PER_DEG * math.cos(math.radians(lat)))
    ring = [[lon - dlon, lat - dlat], [lon + dlon, lat - dlat], [lon + dlon, lat + dlat], [lon - dlon, lat + dlat]]
    return {"type": "Polygon", "coordinates": [ring + [ring[0]]]}


def _geometry(geom: dict, area_ha: float | None) -> dict:
    kind = geom.get("type")
    if kind == "Polygon":
        return geom
    if kind == "MultiPolygon":
        return mapping(max(shape(geom).geoms, key=lambda g: g.area))
    if kind == "Point":
        lon, lat = geom["coordinates"][:2]
        return _square(lat, lon, area_ha or 1.0)
    raise ValueError(f"Неподдерживаемая геометрия: {kind}")


def import_features(session: Session, collection: dict) -> tuple[int, int]:
    """Вернуть (создано, обновлено)."""
    features = collection["features"] if collection.get("type") == "FeatureCollection" else collection
    created = updated = 0
    for i, feature in enumerate(features, start=1):
        props = feature.get("properties") or {}
        cadastral_no = str(_prop(props, "cadastral_no") or f"IMPORT-{i:05d}")
        area = _prop(props, "area_ha")
        area = float(str(area).replace(",", ".")) if area is not None else None
        geometry = _geometry(feature["geometry"], area)
        geometry = json.loads(json.dumps(geometry))  # кортежи shapely → списки для JSONB
        purpose = str(_prop(props, "purpose") or "izhs").lower()
        purpose = PURPOSE_ALIASES.get(purpose, purpose if purpose in PURPOSES else "izhs")

        parcel = session.exec(select(Parcel).where(Parcel.cadastral_no == cadastral_no)).first()
        if parcel is None:
            parcel = Parcel(cadastral_no=cadastral_no, purpose=purpose, area_ha=0, geometry=geometry, ndvi_series=[])
            created += 1
        else:
            updated += 1
        parcel.geometry = geometry
        parcel.purpose = purpose
        parcel.area_ha = round(area if area is not None else geo.area_ha(geometry), 4)
        parcel.address = str(_prop(props, "address") or parcel.address or "")
        parcel.owner = str(_prop(props, "owner") or parcel.owner or "")
        session.add(parcel)
    session.commit()
    return created, updated


def main() -> None:
    if len(sys.argv) != 2:
        print("Использование: python -m app.seed.import_geojson <файл.geojson>")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        collection = json.load(f)
    db.init_db()
    with db.new_session() as session:
        created, updated = import_features(session, collection)
    print(f"Импорт завершён: создано {created}, обновлено {updated}.")


if __name__ == "__main__":
    main()
