ORDER_PRODUCTION_HISTORY_STATUS_LABELS = {
    "ru": {
        "preproduction_started": "Пред-производство начато",
        "preproduction_finished": "Пред-производство закончено",
        "preproduction_canceled": "Пред-производство отменено",
        "production_started": "Производство начато",
        "production_finished": "Производство закончено",
        "production_canceled": "Производство отменено",
        "picking_started": "Комплектация начата",
        "picking_finished": "Комплектация закончена",
        "picking_canceled": "Комплектация отменена",
        "post_production_started": "Пост-производство начато",
        "post_production_finished": "Пост-производство закончено",
        "post_production_phase": "Этап пост-производства",
        "post_production_canceled": "Пост-производство отменено",
    },
    "en": {
        "preproduction_started": "Pre-production started",
        "preproduction_finished": "Pre-production finished",
        "preproduction_canceled": "Pre-production canceled",
        "production_started": "Production started",
        "production_finished": "Production finished",
        "production_canceled": "Production canceled",
        "picking_started": "Picking started",
        "picking_finished": "Picking finished",
        "picking_canceled": "Picking canceled",
        "post_production_started": "Post-production started",
        "post_production_finished": "Post-production finished",
        "post_production_phase": "Post-production phase",
        "post_production_canceled": "Post-production canceled",
    },
}


ORDER_ITEM_PRODUCTION_HISTORY_STATUS_LABELS = {
    "ru": {
        "preproduction-start": "Старт пред-производства",
        "preproduction-step": "Пред-производство",
        "preproduction-finish": "Финиш пред-производства",
        "preproduction-canceled": "Отмена пред-производства",
        "production-start": "Старт производства",
        "batchization-in-bucket": "Группировка в бакете",
        "grouped-in-batch": "Группировка в партии",
        "extracted-from-batch": "Извлечение из партии",
        "production-phase": "Этап производства",
        "defect": "Дефект",
        "reprint": "Перепечатка",
        "production-finish": "Финиш производства",
        "production-canceled": "Отмена производства",
        "picking-start": "Старт комплектации",
        "picking-in-cell": "Комплектация в ячейке",
        "picking-finish": "Финиш комплектации",
        "picking-canceled": "Отмена комплектации",
    },
    "en": {
        "preproduction-start": "Pre-production start",
        "preproduction-step": "Pre-production",
        "preproduction-finish": "Pre-production finish",
        "preproduction-canceled": "Pre-production canceled",
        "production-start": "Production start",
        "batchization-in-bucket": "Batchization in bucket",
        "grouped-in-batch": "Grouping in a batch",
        "extracted-from-batch": "Extracted from batch",
        "production-phase": "Production phase",
        "defect": "Defect",
        "reprint": "Reprint",
        "production-finish": "Production finish",
        "production-canceled": "Production canceled",
        "picking-start": "Picking start",
        "picking-in-cell": "Picking in cell",
        "picking-finish": "Picking finish",
        "picking-canceled": "Picking canceled",
    },
}


ORDER_ITEM_PREPRODUCTION_STEP_LABELS = {
    "ru": {
        "transfer-to-erp-agent": "Передача в ERP-агент",
        "moderation": "Модерация изделий",
        "photo-book-uploader-compilation": "Загрузчик фото-книг",
    },
    "en": {
        "transfer-to-erp-agent": "Transfer to ERP-agent",
        "moderation": "Product moderation",
        "photo-book-uploader-compilation": "Photo-book uploader",
    },
}


def history_status_map(locale: str = "ru") -> dict:
    selected = locale if locale in ORDER_PRODUCTION_HISTORY_STATUS_LABELS else "ru"
    return {
        "order": ORDER_PRODUCTION_HISTORY_STATUS_LABELS[selected],
        "item": ORDER_ITEM_PRODUCTION_HISTORY_STATUS_LABELS[selected],
        "preproduction_step": ORDER_ITEM_PREPRODUCTION_STEP_LABELS[selected],
    }
