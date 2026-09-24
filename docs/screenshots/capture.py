"""Скриншоты и GIF для README и презентации.

Нужен запущенный сервер (python -m app.main) со свежими демо-данными и без INSPECTOR_PASSWORD.
Запуск: backend\\.venv\\Scripts\\python docs\\screenshots\\capture.py  (pip install playwright; браузер — Microsoft Edge)
"""
import io
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).parent
TILES_WAIT = 2500


def shot(page: Page, name: str) -> None:
    page.screenshot(path=OUT / f"{name}.png")
    print("saved", name)


def frame(page: Page, frames: list[Image.Image], width: int = 1000) -> None:
    img = Image.open(io.BytesIO(page.screenshot())).convert("RGB")
    frames.append(img.resize((width, round(img.height * width / img.width)), Image.LANCZOS))


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page(viewport={"width": 1600, "height": 960}, device_scale_factor=1)
        page.goto(f"{BASE}/?lang=ru")
        page.evaluate("localStorage.setItem('zherkoz.lang', 'ru')")
        page.reload()
        page.wait_for_timeout(TILES_WAIT)
        shot(page, "panel")

        page.locator(".list .row").first.click()  # просроченный участок
        page.wait_for_timeout(TILES_WAIT)
        shot(page, "parcel")
        parcel_url = page.locator("a.status-line__act").get_attribute("href")

        page.get_by_role("tab", name="Сигналы").click()
        page.get_by_text("SIG-0001").first.click()
        page.wait_for_timeout(TILES_WAIT)
        shot(page, "signal")

        page.get_by_role("button", name="Закрыть").click()
        page.get_by_role("tab", name="Маршрут").click()
        page.wait_for_timeout(TILES_WAIT + 500)
        shot(page, "route")

        act = browser.new_page(viewport={"width": 900, "height": 1270})
        act.goto(f"{BASE}{parcel_url}")
        act.wait_for_timeout(1500)
        shot(act, "act")

        tg = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True)
        tg.goto(f"{BASE}/?tg=1&lang=ru")
        tg.wait_for_timeout(TILES_WAIT)
        shot(tg, "tgapp")

        # GIF: сигнал жителя → карта → подтверждение
        page.get_by_role("tab", name="Участки").click()
        page.goto(f"{BASE}/?lang=ru")
        page.wait_for_timeout(TILES_WAIT)
        frames: list[Image.Image] = []
        durations: list[int] = []

        def capture(ms: int) -> None:
            frame(page, frames)
            durations.append(ms)

        capture(1200)
        page.get_by_role("button", name="Демо: сигнал жителя").click()
        for _ in range(4):
            page.wait_for_timeout(250)
            capture(300)
        capture(1400)
        page.get_by_role("button", name="Показать").click()
        for _ in range(4):
            page.wait_for_timeout(300)
            capture(300)
        capture(1500)
        page.get_by_role("button", name="Подтвердить нарушение").click()
        page.wait_for_timeout(900)
        capture(2500)
        frames[0].save(OUT / "loop.gif", save_all=True, append_images=frames[1:], duration=durations, loop=0,
                       optimize=True)
        print("saved loop.gif")
        browser.close()


if __name__ == "__main__":
    main()
