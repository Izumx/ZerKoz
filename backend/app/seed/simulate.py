"""Демо-симулятор «сигнала жителя» — страховка для защиты, если Telegram недоступен.

python -m app.seed.simulate [--url http://localhost:8000]
Вызывает POST /api/demo/signal работающего сервера, чтобы событие дошло до открытой панели.
"""
import argparse
import json
import random
import urllib.request

from sqlmodel import Session, select

from app.models import Parcel, Signal
from app.seed.real_photos import demo_photo
from app.services import geo, signals

DESCRIPTIONS = [
    ("dump", "Стихийная свалка строительного мусора у дороги"),
    ("dump", "Выбросили бытовой мусор прямо на участке, запах"),
    ("unused", "Участок заброшен много лет, зарос бурьяном"),
    ("unused", "Никто не обрабатывает землю, сухая трава — риск пожара"),
    ("seizure", "Сосед поставил забор и занял часть общего проезда"),
    ("seizure", "Построили сарай на чужой (государственной) земле"),
]

def simulate_signal(session: Session, rng: random.Random | None = None) -> Signal:
    rng = rng or random.Random()
    parcels = session.exec(select(Parcel).where(Parcel.lifecycle == "none")).all() or session.exec(select(Parcel)).all()
    if parcels:
        lat, lon = geo.random_point_in(rng.choice(parcels).geometry, rng)
    else:
        lat, lon = 42.9 + rng.uniform(-0.02, 0.02), 71.37 + rng.uniform(-0.03, 0.03)
    kind, text = rng.choice(DESCRIPTIONS)
    return signals.create_signal(session, lat=lat, lon=lon, description=text, source="demo",
                                 photos=[demo_photo(kind, rng)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8000")
    args = parser.parse_args()
    req = urllib.request.Request(f"{args.url}/api/demo/signal", method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)
    parcel = data["parcel"]["cadastral_no"] if data["parcel"] else "вне участков"
    print(f"Создан {data['code']} ({data['lat']:.5f}, {data['lon']:.5f}) → {parcel}")


if __name__ == "__main__":
    main()
