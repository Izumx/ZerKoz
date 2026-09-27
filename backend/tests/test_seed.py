from sqlmodel import select

from app.models import Application, Parcel, Signal
from app.seed.generate import generate
from app.seed.import_geojson import import_features
from app.seed.real_photos import add_real_photo_signals, replace_seed_placeholders, set_inspector_photos
from app.services import parcels, stats


def test_generate_produces_demo_dataset(session):
    generate(session)
    d = stats.dashboard(session)
    assert d["total"] == 31
    assert d["red"] == 7 and d["overdue"] == 3
    assert d["yellow"] >= 5
    assert session.exec(select(Application).where(Application.track_no == "KZ-2026-042")).one()
    all_signals = session.exec(select(Signal).order_by(Signal.id)).all()
    assert len(all_signals) == 12
    assert all_signals[6].duplicate_of == all_signals[0].id  # повторное сообщение о той же свалке
    real = all_signals[7:]  # сигналы с настоящими фото: отдельные, не повторы
    assert all(s.duplicate_of is None for s in real)
    assert sum(s.parcel_id is not None for s in real) == 3
    assert add_real_photo_signals(session) == []  # повторный запуск ничего не дублирует
    assert replace_seed_placeholders(session) == []  # у демо-сигналов уже настоящие фото, а не заглушки
    assert set_inspector_photos(session) == []  # и у инспектора тоже
    red = session.exec(select(Parcel).where(Parcel.lifecycle.in_(("detected", "in_progress")))).all()
    for p in red:
        assert len(parcels.parcel_detail(session, p.id)["photos"]) >= 1
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


def test_replace_seed_placeholders_swaps_drawn_photo(session):
    import io

    from PIL import Image

    from app.models import Photo, PhotoBlob
    from app.seed.real_photos import seed_photo
    from app.services import signals

    drawn = io.BytesIO()
    Image.new("RGB", (64, 48), "orange").save(drawn, "PNG")  # как прежняя нарисованная заглушка
    text = "Кучка листвы у забора"
    s = signals.create_signal(session, lat=42.0, lon=71.0, description=text, source="seed", photos=[drawn.getvalue()])
    assert [x.id for x in replace_seed_placeholders(session)] == [s.id]
    photos = session.exec(select(Photo).where(Photo.signal_id == s.id)).all()
    assert len(photos) == 1
    assert session.exec(select(PhotoBlob).where(PhotoBlob.photo_id == photos[0].id)).one().data == seed_photo(text)
    assert replace_seed_placeholders(session) == []
