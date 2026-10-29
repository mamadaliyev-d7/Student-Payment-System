"""Понятные сообщения об ошибках валидации на русском языке."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_FIELD_LABELS = {
    "name": "Имя",
    "phone": "Телефон",
    "group_name": "Группа",
    "monthly_fee": "Стоимость обучения",
    "student_id": "ID ученика",
    "amount": "Сумма оплаты",
    "payment_date": "Дата оплаты",
    "month": "Месяц",
}
_IGNORED_LOC_PARTS = {"body", "query", "path"}
_DATE_MESSAGE = "Некорректная дата. Используйте формат ГГГГ-ММ-ДД, например 2026-10-05"


def _translate(error: dict, has_field: bool) -> str:
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}

    if kind == "missing":
        return "Обязательное поле" if has_field else "Не передано тело запроса"
    if kind == "string_too_short":
        return "Поле не может быть пустым" if ctx.get("min_length") == 1 else (
            f"Слишком короткое значение (минимум {ctx.get('min_length')} симв.)"
        )
    if kind == "string_too_long":
        return f"Слишком длинное значение (максимум {ctx.get('max_length')} симв.)"
    if kind == "greater_than":
        return f"Значение должно быть больше {ctx.get('gt')}"
    if kind == "greater_than_equal":
        return f"Значение должно быть не меньше {ctx.get('ge')}"
    if kind == "less_than_equal":
        return f"Значение должно быть не больше {ctx.get('le')}"
    if kind in {"int_parsing", "int_type", "int_from_float"}:
        return "Значение должно быть целым числом"
    if kind == "string_type":
        return "Значение должно быть строкой"
    if kind.startswith("date"):
        return _DATE_MESSAGE
    if kind == "json_invalid":
        return "Некорректный JSON в теле запроса"
    if kind in {"model_attributes_type", "dict_type"}:
        return "Тело запроса должно быть JSON-объектом"
    if kind == "value_error":
        return str(error.get("msg", "")).removeprefix("Value error, ")
    return str(error.get("msg", "Некорректное значение"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        items = []
        for error in exc.errors():
            parts = [
                str(part)
                for part in error.get("loc", ())
                if part not in _IGNORED_LOC_PARTS and not isinstance(part, int)
            ]
            field = ".".join(parts)
            items.append({"field": field, "message": _translate(error, bool(field))})

        detail = "; ".join(
            f"{_FIELD_LABELS.get(item['field'], item['field'])}: {item['message']}"
            if item["field"]
            else item["message"]
            for item in items
        )
        return JSONResponse(status_code=422, content={"detail": detail, "errors": items})
