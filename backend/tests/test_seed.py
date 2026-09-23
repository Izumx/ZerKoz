from sqlmodel import select

from app.models import Application, Parcel, Signal
from app.seed.generate import generate
from app.seed.import_geojson import import_features
from app.services import parcels, stats


def test_generate_produces_demo_dataset(session):
    generate(session)
    d = stats.dashboard(session)
    assert d["total"] == 31
    assert d["red"] == 7 and d["overdue"] == 3
    assert d["yellow"] >= 5
    assert session.exec(select(Application).where(Application.track_no == "KZ-2026-042")).one()
    assert len(session.exec(select(Signal)).all()) == 6
    # участки не пересекаются — иначе привязка сигнала неоднозначна
    from shapely.geometry import shape
    shapes = [shape(p.geometry) for p in session.exec(select(Parcel)).all()]
    assert not any(a.intersects(b) for i, a in enumerate(shapes) for b in shapes[i + 1:])


def test_import_polygon_and_point(session):
    fc = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"Cadastral": "06-097-999-001", "Назначение": "ИЖС"},
             "geometry": {"type": "Polygon", "coordinates": [[[71, 42], [71.001, 42], [71.001, 42.001], [71, 42]]]}},
            {"type": "Feature", "properties": {"kad_nomer": "06-097-999-002", "area": "2,5"},
             "geometry": {"type": "Point", "coordinates": [71.4, 42.9]}},
        ],
    }
    assert import_features(session, fc) == (2, 0)
    assert import_features(session, fc) == (0, 2)
    point_parcel = session.exec(select(Parcel).where(Parcel.cadastral_no == "06-097-999-002")).one()
    assert point_parcel.area_ha == 2.5
    assert parcels.compute_color(point_parcel, 0) == "green"
    from app.services import geo
    assert 2.4 < geo.area_ha(point_parcel.geometry) < 2.6
