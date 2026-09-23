import pytest

from app.models import Application
from app.services import applications, botusers


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("KZ-2026-042", ("application", "KZ-2026-042")),
        (" kz 2026 042 ", ("application", "KZ-2026-042")),
        ("KZ2026042", ("application", "KZ-2026-042")),
        ("КЗ-2026-42", ("application", "KZ-2026-042")),  # кириллица
        ("KZ–2026–042", ("application", "KZ-2026-042")),  # длинное тире
        ("sig-7", ("signal", "SIG-0007")),
        ("SIG0012", ("signal", "SIG-0012")),
        ("привет", None),
        ("KZ-26-1", None),
    ],
)
def test_normalize_code(raw, expected):
    assert applications.normalize_code(raw) == expected


def test_find_application(session):
    session.add(Application(track_no="KZ-2026-042", applicant="А. Б.", type="izhs", stage="inspection"))
    session.commit()
    assert applications.find(session, "KZ-2026-042").stage == "inspection"
    assert applications.find(session, "KZ-2026-999") is None


def test_bot_user_language(session):
    assert botusers.get_lang(session, 1) is None
    botusers.set_lang(session, 1, "kz")
    botusers.set_lang(session, 1, "ru")
    assert botusers.get_lang(session, 1) == "ru"
