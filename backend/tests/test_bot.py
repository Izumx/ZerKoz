import pytest

from app.bot import i18n
from app.bot.handlers import build_router
from app.bot.knowledge import ARTICLES
from app.bot.util import parse_coords
from app.models import APPLICATION_STAGES, APPLICATION_TYPES, SIGNAL_STATUSES


@pytest.mark.parametrize(
    "text, expected",
    [("42.90, 71.37", (42.90, 71.37)), ("42,905 71,372", (42.905, 71.372)), ("42.9;71.3", (42.9, 71.3)),
     ("hello", None), ("142.9, 71.3", None)],
)
def test_parse_coords(text, expected):
    assert parse_coords(text) == expected


def test_languages_have_same_keys():
    assert i18n.TEXTS["ru"].keys() == i18n.TEXTS["kz"].keys()
    for lang in ("ru", "kz"):
        assert set(i18n.APPLICATION_TYPES[lang]) == set(APPLICATION_TYPES)
        for article in ARTICLES.values():
            assert article[lang]["title"] and "<b>" in article[lang]["body"]
    assert set(i18n.STAGES) == set(APPLICATION_STAGES)
    assert set(i18n.SIGNAL_STATUSES) == set(SIGNAL_STATUSES)


@pytest.mark.parametrize("lang", ["ru", "kz"])
def test_templates_format(lang):
    i18n.t(lang, "report_sent", code="SIG-0001")
    i18n.t(lang, "report_confirm", place="x", n=1, description="y")
    i18n.t(lang, "place_point", lat=42.0, lon=71.0)
    emoji, status, hint = i18n.signal_status(lang, "confirmed")
    i18n.t(lang, "notify_status", code="SIG-0001", emoji=emoji, status=status, hint=hint)


def test_router_builds():
    assert build_router().name == "root"
