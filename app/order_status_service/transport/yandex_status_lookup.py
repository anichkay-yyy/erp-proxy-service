from __future__ import annotations


YANDEX_STATUS_MODEL_SOURCE = "https://yandex.ru/support/delivery-profile/ru/api/other-day/status-model"

YANDEX_SCHEME_STATUS_GROUPS = {
    "Создание заказа": [
        "DRAFT",
        "VALIDATING",
        "CREATED",
    ],
    "Обработка заказа": [
        "DELIVERY_PROCESSING_STARTED",
        "DELIVERY_TRACK_RECIEVED",
        "DELIVERY_TRACK_RECEIVED",
        "SORTING_CENTER_PROCESSING_STARTED",
        "SORTING_CENTER_TRACK_RECEIVED",
        "SORTING_CENTER_TRACK_RECIEVED",
        "SORTING_CENTER_TRACK_LOADED",
        "DELIVERY_LOADED",
        "SORTING_CENTER_LOADED",
    ],
    "Обработка заказа в принимающем сортировочном центре": [
        "SORTING_CENTER_AT_START",
        "SORTING_CENTER_PREPARED",
        "SORTING_CENTER_TRANSMITTED",
    ],
    "Доставка до ПВЗ/постамата": [
        "DELIVERY_AT_START",
        "DELIVERY_TRANSPORTATION",
        "DELIVERY_ARRIVED_PICKUP_POINT",
    ],
    "Выдача заказа": [
        "DELIVERY_TRANSMITTED_TO_RECIPIENT",
        "CONFIRMATION_CODE_RECEIVED",
        "DELIVERY_DELIVERED",
        "PARTICULARLY_DELIVERED",
    ],
    "Отмена и старт процедуры возврата": [
        "CANCELLED",
        "SORTING_CENTER_RETURN_PREPARING",
        "RETURN_TRANSPORTATION_STARTED",
    ],
    "Возврат заказа в сортировочный центр": [
        "SORTING_CENTER_RETURN_PREPARING_SENDER",
        "RETURN_ARRIVED_DELIVERY",
        "RETURN_READY_FOR_PICKUP",
    ],
    "Возврат заказа отправителю": [
        "SORTING_CENTER_RETURN_ARRIVED",
    ],
    "Возврат завершен": [
        "SORTING_CENTER_RETURN_RETURNED",
        "RETURN_RETURNED",
    ],
    "Срок хранения": [
        "DELIVERY_STORAGE_PERIOD_EXTENDED",
        "DELIVERY_STORAGE_PERIOD_EXPIRED",
    ],
}

YANDEX_OUTSIDE_SCHEME_STATUSES = {
    "VALIDATING_ERROR": "Ошибка проверки заказа",
    "DELIVERY_AT_START_SORT": "Заказ находится в городе получателя и готовится к отправке",
    "DELIVERY_TIME_INTERVALS_UPDATED": "Срок доставки изменён",
    "DELIVERY_DATE_UPDATED_BY_SHOP": "Доставка перенесена отправителем",
    "DELIVERY_DATE_UPDATED_BY_DELIVERY": "Доставка перенесена службой доставки",
    "DELIVERY_UPDATED_BY_SHOP": "Доставка перенесена отправителем",
    "DELIVERY_UPDATED_BY_RECIPIENT": "Доставка перенесена получателем",
    "DELIVERY_UPDATED_BY_DELIVERY": "Доставка перенесена службой доставки",
    "CANCELED_IN_PLATFORM": "Заказ отменен службой доставки",
}

YANDEX_CANCEL_REASON_LABELS = {
    "DELIVERY_PROBLEMS": "Возникли проблемы во время доставки",
    "PICKUP_EXPIRED": "Срок хранения в пункте выдачи истёк",
    "CANCELLED_BY_RECIPIENT": "Заказ отменён по просьбе клиента",
    "CANCELLED_USER": "Заказ отменён пользователем",
    "SORTING_CENTER_CANCELLED": "Заказ отменён сортировочным центром",
}


def yandex_status_map_response() -> dict:
    return {
        "source": YANDEX_STATUS_MODEL_SOURCE,
        "scheme_status_groups": YANDEX_SCHEME_STATUS_GROUPS,
        "outside_scheme_statuses": YANDEX_OUTSIDE_SCHEME_STATUSES,
        "cancel_reasons": YANDEX_CANCEL_REASON_LABELS,
    }


def lookup_yandex_status(status: str | None, reason: str | None = None) -> dict:
    code = str(status or "").strip().upper()
    reason_code = str(reason or "").strip().upper()
    if not code:
        return {
            "status": None,
            "reason": reason_code or None,
            "stage": None,
            "kind": "unknown",
            "reason_text": YANDEX_CANCEL_REASON_LABELS.get(reason_code),
        }

    for stage, statuses in YANDEX_SCHEME_STATUS_GROUPS.items():
        if code in statuses:
            return {
                "status": code,
                "reason": reason_code or None,
                "stage": stage,
                "kind": "scheme",
                "reason_text": YANDEX_CANCEL_REASON_LABELS.get(reason_code),
            }

    label = YANDEX_OUTSIDE_SCHEME_STATUSES.get(code)
    if label:
        return {
            "status": code,
            "reason": reason_code or None,
            "stage": label,
            "kind": "outside_scheme",
            "reason_text": YANDEX_CANCEL_REASON_LABELS.get(reason_code),
        }

    if code.startswith("RETURN_"):
        return {
            "status": code,
            "reason": reason_code or None,
            "stage": "Возврат",
            "kind": "return_fallback",
            "reason_text": YANDEX_CANCEL_REASON_LABELS.get(reason_code),
        }

    return {
        "status": code,
        "reason": reason_code or None,
        "stage": None,
        "kind": "unknown",
        "reason_text": YANDEX_CANCEL_REASON_LABELS.get(reason_code),
    }
