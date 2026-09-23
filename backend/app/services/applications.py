import re

from sqlmodel import Session, select

from app.models import Application

_KZ = re.compile(r"^KZ-?(\d{4})-?(\d{1,3})$")
_SIG = re.compile(r"^SIG-?(\d{1,6})$")
_LOOKALIKES = str.maketrans({"К": "K", "З": "Z", "С": "C", "–": "-", "—": "-", "_": "-", "‑": "-"})


def normalize_code(text: str) -> tuple[str, str] | None:
    """Распознать трек-номер заявления (KZ-2026-042) или сигнала (SIG-0007) в свободном вводе."""
    raw = re.sub(r"\s+", "", text.upper().translate(_LOOKALIKES))
    if m := _KZ.match(raw):
        return "application", f"KZ-{m.group(1)}-{int(m.group(2)):03d}"
    if m := _SIG.match(raw):
        return "signal", f"SIG-{int(m.group(1)):04d}"
    return None


def find(session: Session, track_no: str) -> Application | None:
    return session.exec(select(Application).where(Application.track_no == track_no)).first()
