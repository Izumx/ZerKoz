import io
from datetime import date, timedelta

import pytest
from PIL import Image

from app.services import ServiceError, TransitionError, notify, parcels, signals
from app.services.photos import PhotoError
from tests.factories import make_parcel


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def notified():
    calls = []
    notify.set_notifier(lambda s: calls.append((s.code, s.status)))
    yield calls
    notify.set_notifier(None)


def test_create_signal_binds_to_parcel_and_saves_photo(session):
    p = make_parcel(session)
    s = signals.create_signal(session, lat=42.005, lon=71.005, description=" Свалка ", photos=[jpeg()])
    assert s.code == "SIG-0001"
    assert s.parcel_id == p.id
    data = signals.signal_dict(session, s)
    assert data["description"] == "Свалка"
    assert data["photos"][0]["url"].startswith("/media/")
    assert data["parcel"]["cadastral_no"] == p.cadastral_no
    assert parcels.feature_collection(session)["features"][0]["properties"]["color"] == "yellow"


def test_create_signal_outside_parcels(session):
    s = signals.create_signal(session, lat=40.0, lon=70.0)
    assert s.parcel_id is None and s.code == "SIG-0001"


def test_create_signal_rejects_bad_input(session):
    with pytest.raises(ServiceError):
        signals.create_signal(session, lat=200, lon=0)
    with pytest.raises(PhotoError):
        signals.create_signal(session, lat=42, lon=71, photos=[b"not an image"])


def test_confirm_marks_parcel_detected_and_notifies(session, notified):
    p = make_parcel(session)
    s = signals.create_signal(session, lat=42.005, lon=71.005, tg_chat_id=123)
    signals.set_status(session, s.id, "checking")
    signals.set_status(session, s.id, "confirmed", violation_type="seizure")
    session.refresh(p)
    assert p.lifecycle == "detected" and p.violation_type == "seizure"
    assert notified == [("SIG-0001", "checking"), ("SIG-0001", "confirmed")]


def test_confirm_without_violation_type_defaults_to_dump(session):
    p = make_parcel(session)
    s = signals.create_signal(session, lat=42.005, lon=71.005)
    signals.set_status(session, s.id, "confirmed")
    session.refresh(p)
    assert p.violation_type == "dump"


def test_resolving_parcel_resolves_confirmed_signals(session, notified):
    p = make_parcel(session)
    s = signals.create_signal(session, lat=42.005, lon=71.005, tg_chat_id=5)
    signals.set_status(session, s.id, "confirmed")
    parcels.update_parcel(session, p.id, {"lifecycle": "in_progress", "deadline": date.today() + timedelta(days=5)})
    parcels.update_parcel(session, p.id, {"lifecycle": "resolved"})
    session.refresh(s)
    assert s.status == "resolved"
    assert notified[-1] == ("SIG-0001", "resolved")


def test_forbidden_signal_transition(session):
    s = signals.create_signal(session, lat=42, lon=71)
    with pytest.raises(TransitionError):
        signals.set_status(session, s.id, "resolved")


def test_no_notification_without_chat(session, notified):
    s = signals.create_signal(session, lat=42, lon=71)
    signals.set_status(session, s.id, "rejected")
    assert notified == []


def test_get_by_code(session):
    s = signals.create_signal(session, lat=42, lon=71)
    assert signals.get_by_code(session, "SIG-0001").id == s.id
    assert signals.get_by_code(session, "SIG-9999") is None
