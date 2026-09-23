class ServiceError(ValueError):
    """Ошибка бизнес-правила (API отвечает 409/400)."""


class TransitionError(ServiceError):
    """Недопустимый переход статуса."""


class NotFound(LookupError):
    """Объект не найден (API отвечает 404)."""
