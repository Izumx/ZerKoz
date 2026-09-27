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


def jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "gray").save(buf, "JPEG")
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
        "auth_required": True, "authenticated": False, "demo_mode": True, "bot_username": None,
        "sentinel_enabled": False}
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


# ---------- NDVI из Sentinel-2 (ответы Copernicus подменены) ----------

def test_ndvi_refresh_parses_statistics(session, monkeypatch):
    import httpx

    from app.services import ndvi

    def handler(request: httpx.Request) -> httpx.Response:
        if "openid-connect/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 600})
        if request.url.path == "/api/v1/statistics":
            return httpx.Response(404)
        assert request.headers["authorization"] == "Bearer t"
        data = [{"interval": {"from": f"2026-{m:02d}-01T00:00:00Z"},
                 "outputs": {"ndvi": {"bands": {"B0": {"stats": {"mean": 0.1 + m / 100, "sampleCount": 10}}}}}}
                for m in range(1, 10)]
        data.append({"interval": {"from": "2026-10-01T00:00:00Z"},
                     "outputs": {"ndvi": {"bands": {"B0": {"stats": {"mean": "NaN", "sampleCount": 0}}}}}})
        return httpx.Response(200, json={"data": data, "status": "OK"})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "copernicus_client_id", "id")
    monkeypatch.setattr(settings, "copernicus_client_secret", "secret")
    monkeypatch.setattr(ndvi, "_token", None)

    p = make_parcel(session, purpose="agri")
    ndvi.refresh_parcel(session, p, flag_low=True)
    assert p.ndvi_source == "sentinel-2"
    assert p.ndvi_months[0] == "2026-01" and p.ndvi_series[-1] is None
    assert p.under_check is True  # пик 0.19 < 0.25 — участок поставлен на проверку


def test_ndvi_disabled_without_keys(session):
    from app.services import ndvi

    with pytest.raises(ndvi.NdviError):
        ndvi.fetch_series({"type": "Polygon", "coordinates": []})


# ---------- деплой ----------

def test_database_url_normalized():
    from app.config import Settings

    assert Settings(database_url="postgres://u:p@h:5432/db").database_url == "postgresql+psycopg://u:p@h:5432/db"
    assert Settings(database_url="postgresql://u@h/db").database_url == "postgresql+psycopg://u@h/db"


def test_webhook_rejects_wrong_secret(monkeypatch):
    from app.bot import runner

    monkeypatch.setattr(settings, "bot_token", "42:TEST")
    client = TestClient(app)
    assert client.post("/tg/webhook", json={}).status_code == 403
    ok_header = {"X-Telegram-Bot-Api-Secret-Token": runner.webhook_secret("42:TEST")}
    assert client.post("/tg/webhook", json={}, headers=ok_header).status_code == 503  # бот ещё не запущен


# ---------- регрессии из ревью ----------

def test_ndvi_nan_month_becomes_none(session, monkeypatch):
    import httpx

    from app.services import ndvi

    def handler(request: httpx.Request) -> httpx.Response:
        if "openid-connect/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "t", "expires_in": 600})
        body = ('{"data":[{"interval":{"from":"2026-01-01T00:00:00Z"},"outputs":{"ndvi":{"bands":{"B0":'
                '{"stats":{"mean":NaN,"sampleCount":40}}}}}},{"interval":{"from":"2026-06-01T00:00:00Z"},'
                '"outputs":{"ndvi":{"bands":{"B0":{"stats":{"mean":0.6,"sampleCount":40}}}}}}]}')
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "copernicus_client_id", "id")
    monkeypatch.setattr(settings, "copernicus_client_secret", "secret")
    monkeypatch.setattr(ndvi, "_token", None)
    p = make_parcel(session)
    ndvi.refresh_parcel(session, p)  # не падает на записи NaN в JSONB
    assert p.ndvi_series == [None, 0.6]


def test_bot_escapes_application_note(session):
    import asyncio
    from datetime import datetime

    from aiogram.types import Chat, Message

    from app.bot.handlers.status import answer_status

    session.add(Application(track_no="KZ-2026-042", applicant="И.", type="izhs", stage="review",
                            note_ru="Срок < 10 дней, ТОО «А&Б»"))
    session.commit()
    sent = []

    class FakeMessage:
        chat = Chat(id=1, type="private")

        async def answer(self, text, **kwargs):
            sent.append(text)

    asyncio.run(answer_status(FakeMessage(), "ru", "application", "KZ-2026-042"))
    assert "Срок &lt; 10 дней, ТОО «А&amp;Б»" in sent[0]


# ---------- регрессии из второго ревью ----------

def test_closing_parcel_resolves_duplicates_outside_it(session):
    from app.services import parcels

    p = make_parcel(session)  # квадрат 71.00–71.01 × 42.00–42.01
    primary = signals.create_signal(session, lat=42.0001, lon=71.0001, description="Свалка")
    outside = signals.create_signal(session, lat=41.9999, lon=70.9999, description="Та же свалка")
    assert outside.parcel_id is None and outside.duplicate_of == primary.id
    signals.set_status(session, primary.id, "confirmed")
    parcels.update_parcel(session, p.id, {"lifecycle": "resolved"})
    session.refresh(primary)
    session.refresh(outside)
    assert (primary.status, outside.status) == ("resolved", "resolved")


def test_ndvi_network_error_is_readable(session, monkeypatch):
    import httpx

    from app.services import ndvi

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    real_client = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "copernicus_client_id", "id")
    monkeypatch.setattr(settings, "copernicus_client_secret", "secret")
    monkeypatch.setattr(ndvi, "_token", None)
    with pytest.raises(ndvi.NdviError, match="Copernicus недоступен"):
        ndvi.fetch_series(make_parcel(session).geometry)


def test_bot_hides_exact_point_of_foreign_signal(session):
    import asyncio

    from aiogram.types import Chat

    from app.bot.handlers.status import answer_status

    s = signals.create_signal(session, lat=42.123456, lon=71.654321, description="Свалка", tg_chat_id=7)
    sent = []

    def fake(chat_id):
        class FakeMessage:
            chat = Chat(id=chat_id, type="private")

            async def answer(self, text, **kwargs):
                sent.append(text)

        return FakeMessage()

    asyncio.run(answer_status(fake(99), "ru", "signal", s.code))
    asyncio.run(answer_status(fake(7), "ru", "signal", s.code))
    assert "42.123456"[:7] not in sent[0] and "42.12300" in sent[0]  # чужой — только район
    assert "42.12346" in sent[1]  # автор видит точную точку


def test_history_for_several_entities_in_one_query(session):
    from app.services import history

    history.log(session, "parcel", 1, "a")
    history.log(session, "signal", 5, "b")
    history.log(session, "signal", 6, "c")
    history.log(session, "signal", 1, "not mine")
    session.commit()
    actions = {e["action"] for e in history.for_entities(session, [("parcel", 1), ("signal", 5), ("signal", 6)])}
    assert actions == {"a", "b", "c"}
    assert history.for_entities(session, []) == []
