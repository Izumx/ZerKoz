"""ИИ-подсказка инспектору: тип нарушения по фото и описанию жителя (Claude, анализ изображений).

Включается, если задан ANTHROPIC_API_KEY. Работает в фоне и не задерживает приём сигнала;
результат — только подсказка, решение всегда принимает инспектор.
"""
import base64
import json
import logging
import threading

from sqlmodel import select

from app.config import settings
from app.events import bus
from app.models import Photo, PhotoBlob, Signal

log = logging.getLogger(__name__)

MAX_IMAGES = 3
SYSTEM = (
    "Ты помощник земельного инспектора Жамбылской области (Казахстан). По фото и описанию жителя "
    "определи тип возможного нарушения земельного законодательства:\n"
    "- dump: стихийная свалка, строительный или бытовой мусор, отходы;\n"
    "- unused: заброшенный, не обрабатываемый, заросший участок;\n"
    "- seizure: самовольный захват — забор, постройка, огород на чужой или государственной земле;\n"
    "- none: нарушения на фото не видно.\n"
    "Оцени уверенность и кратко (одно предложение) опиши, что видно на фото — на русском и казахском."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "violation_type": {"type": "string", "enum": ["dump", "unused", "seizure", "none"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary_ru": {"type": "string"},
        "summary_kz": {"type": "string"},
    },
    "required": ["violation_type", "confidence", "summary_ru", "summary_kz"],
    "additionalProperties": False,
}


def enabled() -> bool:
    return bool(settings.anthropic_api_key)


def classify(images: list[tuple[bytes, str]], description: str) -> dict | None:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=60.0)
    content: list[dict] = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                     "data": base64.standard_b64encode(data).decode("ascii")}}
        for data, media_type in images[:MAX_IMAGES]
    ]
    content.append({"type": "text", "text": f"Описание жителя: {description or '(нет)'}"})
    try:
        response = client.beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=2000,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError:
        log.warning("ИИ-анализ: превышен лимит запросов")
        return None
    except anthropic.APIStatusError as exc:
        log.warning("ИИ-анализ: ошибка API %s: %s", exc.status_code, exc.message)
        return None
    except anthropic.APIConnectionError:
        log.warning("ИИ-анализ: нет соединения с API")
        return None
    if response.stop_reason == "refusal":
        log.info("ИИ-анализ: модель отказалась анализировать фото")
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        return None
    result = json.loads(text)
    result["model"] = response.model
    return result


def analyze(signal_id: int) -> None:
    from app import db

    with db.new_session() as session:
        signal = session.get(Signal, signal_id)
        if signal is None:
            return
        rows = session.exec(
            select(PhotoBlob.data, Photo.content_type).join(Photo, Photo.id == PhotoBlob.photo_id)
            .where(Photo.signal_id == signal_id)
        ).all()
        if not rows:
            return
        try:
            result = classify([(r[0], r[1]) for r in rows], signal.description)
        except Exception:
            log.exception("ИИ-анализ сигнала %s не удался", signal.code)
            return
        if not result:
            return
        signal.ai = result
        if result["violation_type"] != "none" and result["confidence"] != "low":
            signal.suggested_violation = result["violation_type"]
        session.add(signal)
        session.commit()
        bus.publish("signal.updated", {"id": signal.id, "code": signal.code, "status": signal.status, "ai": True})


def schedule(signal_id: int) -> None:
    if enabled():
        threading.Thread(target=analyze, args=(signal_id,), daemon=True, name=f"ai-{signal_id}").start()
