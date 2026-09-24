import io
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import auth
from app.config import settings
from app.main import app
from app.models import Application
from app.services import TransitionError, applications, notify, parcels, route, signals
from app.services.photos import save_photo
from tests.factories import make_parcel


def jpeg(gps: tuple[float, float] | None = None, taken: str = "2026:09:24 10:00:00") -> bytes:
    img = Image.new("RGB", (8, 8), "gray")
    exif = Image.Exif()
    if gps:
        lat, lon = gps
        dms = lambda v: (float(int(v)), float(int(v * 60 % 60)), round(v * 3600 % 60, 2))  # noqa: E731
        exif[0x8825] = {1: "N", 2: dms(lat), 3: "E", 4: dms(lon)}
    exif[0x0132] = taken
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


# ---------- дубли ----------

def test_nearby_report_becomes_duplicate_and_follows_primary(session):
    calls = []
    notify.set_notifier(lambda s: calls.append(s.code))
    try:
        p = make_parcel(session)
        first = signals.create_signal(session, lat=42.005, lon=71.005, tg_chat_id=1)
        second = signals.create_signal(session, lat=42.0052, lon=71.0051, tg_chat_id=2)  # ~25 м
        far = signals.create_signal(session, lat=42.02, lon=71.005)  # ~1,7 км, вне участка
        assert second.duplicate_of == first.id and far.duplicate_of is None
        assert signals.signal_dict(session, first)["reports"] == 2
        assert [s["code"] for s in signals.list_signals(session)] == [far.code, first.code]

        with pytest.raises(TransitionError):
            signals.set_status(session, second.id, "checking")
        signals.set_status(session, first.id, "confirmed")
        session.refresh(second)
        assert second.status == "confirmed"
        assert sorted(calls) == ["SIG-0001", "SIG-0002"]  # уведомлены оба жителя
        assert parcels.feature_collection(session)["features"][0]["properties"]["open_signals"] == 0
        assert session.get(type(p), p.id).lifecycle == "detected"
    finally:
        notify.set_notifier(None)


# ---------- антиспам и подсказка типа ----------

def test_rate_limit_per_chat(session, monkeypatch):
    monkeypatch.setattr(settings, "signals_per_hour", 2)
    signals.create_signal(session, lat=42.0, lon=71.0, tg_chat_id=7)
    signals.create_signal(session, lat=43.0, lon=72.0, tg_chat_id=7)
    with pytest.raises(signals.RateLimitError):
        signals.create_signal(session, lat=44.0, lon=73.0, tg_chat_id=7)
    signals.create_signal(session, lat=44.0, lon=73.0, tg_chat_id=8)  # другой житель — можно


@pytest.mark.parametrize("text, expected", [
    ("Свалка строительного мусора", "dump"),
    ("Участок заброшен, всё заросло бурьяном", "unused"),
    ("Сосед поставил забор на дороге", "seizure"),
    ("Қоқыс үйіндісі", "dump"),
    ("Просто красивое место", None),
])
def test_guess_violation(text, expected):
    assert signals.guess_violation(text) == expected


def test_confirm_uses_suggested_violation(session):
    p = make_parcel(session)
    s = signals.create_signal(session, lat=42.005, lon=71.005, description="Заброшен, никто не обрабатывает")
    signals.set_status(session, s.id, "confirmed")
    session.refresh(p)
    assert p.violation_type == "unused"


# ---------- EXIF ----------

def test_exif_check_statuses(session):
    near = signals.create_signal(session, lat=42.905, lon=71.36, photos=[jpeg((42.9051, 71.3601))])
    far = signals.create_signal(session, lat=42.5, lon=71.0, photos=[jpeg((42.905, 71.36))])
    bare = signals.create_signal(session, lat=41.0, lon=70.0, photos=[jpeg(None)])
    checks = [signals.signal_dict(session, s)["photos"][0]["exif_check"] for s in (near, far, bare)]
    assert checks[0]["status"] == "ok" and checks[0]["distance_m"] < 50
    assert checks[1]["status"] == "far" and checks[1]["distance_m"] > 40_000
    assert checks[2]["status"] in ("no_gps", "old")


# ---------- заявления ----------

def test_application_stage_change_notifies_subscribers(session):
    session.add(Application(track_no="KZ-2026-042", applicant="И.", type="izhs", stage="review"))
    session.commit()
    sent = []
    notify.set_notifier(None, lambda app, chat, lang: sent.append((app.stage, chat, lang)))
    try:
        applications.subscribe(session, "KZ-2026-042", 100, "kz")
        applications.subscribe(session, "KZ-2026-042", 100, "ru")  # повторная подписка не дублируется
        applications.update(session, "KZ-2026-042", stage="approved", note_ru="Одобрено")
        assert sent == [("approved", 100, "ru")]
        applications.unsubscribe(session, "KZ-2026-042", 100)
        applications.update(session, "KZ-2026-042", stage="rejected")
        assert len(sent) == 1
        with pytest.raises(TransitionError):
            applications.update(session, "KZ-2026-042", stage="unknown")
    finally:
        notify.set_notifier(None)


# ---------- маршрут ----------

def test_route_orders_overdue_and_checks(session):
    make_parcel(session, 1, lon=71.30, lifecycle="in_progress", violation_type="dump",
                deadline=date.today() - timedelta(days=3))
    make_parcel(session, 2, lon=71.40, under_check=True)
    make_parcel(session, 3, lon=71.50)  # зелёный — не в маршруте
    signals.create_signal(session, lat=42.95, lon=71.45)  # сигнал вне участков
    plan = route.plan(session)
    assert [s["reason"] for s in plan["stops"]].count("overdue") == 1
    assert {s["reason"] for s in plan["stops"]} == {"overdue", "check", "signal"}
    assert len(plan["stops"]) == 3 and plan["distance_km"] > 0


# ---------- доступ ----------

def test_panel_requires_password_when_set(session, monkeypatch):
    monkeypatch.setattr(settings, "inspector_password", "secret")
    client = TestClient(app)
    assert client.get("/api/parcels").status_code == 401
    assert client.get("/api/session").json() == {
        "auth_required": True, "authenticated": False, "demo_mode": True, "bot_username": None}
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    assert client.post("/api/login", json={"password": "secret"}).status_code == 200
    assert client.get("/api/parcels").status_code == 200
    assert client.get("/api/session").json()["authenticated"] is True


def test_token_tampering_rejected():
    token = auth.make_token()
    assert auth.verify_token(token)
    role, expires, sig = token.split(".")
    assert not auth.verify_token(f"{role}.{int(expires) + 999}.{sig}")
    assert not auth.verify_token("garbage")


def test_demo_mode_off(monkeypatch, session):
    monkeypatch.setattr(settings, "demo_mode", False)
    assert TestClient(app).post("/api/demo/signal").status_code == 404


def test_media_served_from_db(session):
    p = make_parcel(session)
    photo = save_photo(session, jpeg(), parcel_id=p.id)
    session.commit()
    r = TestClient(app).get(f"/media/{photo.path}")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert TestClient(app).get("/media/nope.jpg").status_code == 404
