"""Собрать все казахские тексты проекта в одну таблицу для вычитки носителем языка.

Запуск из корня: backend\\.venv\\Scripts\\python docs\\kz-review\\export.py → docs/kz-review/kz-strings.md
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.bot.i18n import APPLICATION_TYPES, SIGNAL_STATUSES, STAGES, TEXTS  # noqa: E402
from app.bot.knowledge import ARTICLES  # noqa: E402
from app.bot.runner import COMMANDS  # noqa: E402
from app.seed.data import APPLICATIONS  # noqa: E402

# места, в которых автор перевода не уверен: ключ → на что посмотреть
DOUBTS = {
    "btn_cancel": "«Болдырмау» или привычнее «Бас тарту»?",
    "cancelled": "Естественно ли «Тоқтатылды» после отмены действия?",
    "btn_kb": "«Анықтамалық» — подходит ли для «База знаний»?",
    "report_need_photo": "«сурет-файл» — естественно ли звучит?",
    "baseScheme": "«Сызба» для типа подложки карты «Схема» — или лучше «Карта»?",
    "stepInProgress": "Короткая подпись шага «Жою» — понятно ли без контекста?",
    "lifecycle.in_progress": "«Жою процесінде» или «Жою үдерісінде»?",
    "purposeName.lph": "Сокращение «ЖҚШ» для ЛПХ — принято ли?",
    "stage.inspection": "«Шығу тағайындалды» — ясно ли, что это выезд инспектора?",
}


def cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def frontend_pairs() -> list[tuple[str, str, str]]:
    """Пары ключ → (рус, каз) из frontend/src/i18n.tsx (плоские строки и вложенные словари)."""
    src = (ROOT / "frontend" / "src" / "i18n.tsx").read_text(encoding="utf-8")
    ru_block = src.split("const ru = {", 1)[1].split("\ntype Dict", 1)[0]
    kz_block = src.split("const kz: Dict = {", 1)[1].split("\nconst DICTS", 1)[0]

    def parse(block: str) -> dict[str, str]:
        result: dict[str, str] = {}
        prefix = ""
        for line in block.splitlines():
            if m := re.match(r"\s{2}(\w+): \{$", line):
                prefix = m.group(1) + "."
                continue
            if re.match(r"\s{2}\},?$", line):
                prefix = ""
                continue
            for key, value in re.findall(r"(\w+): '((?:[^'\\]|\\.)*)'", line):
                result[prefix + key] = value
        return result

    ru, kz = parse(ru_block), parse(kz_block)
    return [(k, ru.get(k, ""), v) for k, v in kz.items()]


def main() -> None:
    out = ["# Казахские тексты ЖерКөз — на вычитку", "",
           "Колонка «Сомнение» — места, в которых автор перевода не уверен. Правки можно вписать в колонку «Правка».",
           ""]

    out += ["## 1. Telegram-бот (жители видят первым)", "", "| Ключ | Русский | Қазақша | Сомнение | Правка |", "|---|---|---|---|---|"]
    for key, kz in TEXTS["kz"].items():
        out.append(f"| `{key}` | {cell(TEXTS['ru'][key])} | {cell(kz)} | {DOUBTS.get(key, '')} | |")
    for code, (_, ru, kz) in STAGES.items():
        out.append(f"| `stage.{code}` | {ru} | {kz} | {DOUBTS.get('stage.' + code, '')} | |")
    for code, (_, ru, kz, hint_ru, hint_kz) in SIGNAL_STATUSES.items():
        out.append(f"| `signal.{code}` | {ru}<br>{hint_ru} | {kz}<br>{hint_kz} | | |")
    for code in APPLICATION_TYPES["kz"]:
        out.append(f"| `type.{code}` | {APPLICATION_TYPES['ru'][code]} | {APPLICATION_TYPES['kz'][code]} | | |")
    for (cmd, ru), (_, kz) in zip(COMMANDS["ru"], COMMANDS["kk"]):
        out.append(f"| `/{cmd}` | {ru} | {kz} | | |")

    out += ["", "## 2. База знаний бота", ""]
    for key, article in ARTICLES.items():
        out += [f"### {article['ru']['title']} / {article['kz']['title']}", "",
                "| Русский | Қазақша | Правка |", "|---|---|---|",
                f"| {cell(article['ru']['body'])} | {cell(article['kz']['body'])} | |", ""]

    out += ["## 3. Пояснения к тестовым заявлениям", "", "| Номер | Русский | Қазақша | Правка |", "|---|---|---|---|"]
    for track, _, _, _, note_ru, note_kz in APPLICATIONS:
        out.append(f"| {track} | {cell(note_ru)} | {cell(note_kz)} | |")

    out += ["", "## 4. Панель инспектора и мини-приложение", "", "| Ключ | Русский | Қазақша | Сомнение | Правка |", "|---|---|---|---|---|"]
    for key, ru, kz in frontend_pairs():
        out.append(f"| `{key}` | {cell(ru)} | {cell(kz)} | {DOUBTS.get(key, '')} | |")

    target = Path(__file__).with_name("kz-strings.md")
    target.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{target} — строк: {sum(1 for line in out if line.startswith('| '))}")


if __name__ == "__main__":
    main()
