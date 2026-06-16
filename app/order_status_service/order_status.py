def latest_production_history_status(items: list[dict]) -> dict | None:
    if not items:
        return None

    def item_order(item: dict) -> tuple[str, int]:
        timestamp = str(item.get("finish_at") or item.get("start_at") or "")
        item_id = item.get("id")
        try:
            numeric_id = int(item_id)
        except (TypeError, ValueError):
            numeric_id = 0
        return (timestamp, numeric_id)

    latest = max(items, key=item_order)
    return {
        "status": latest.get("type"),
        "changed_at": latest.get("finish_at") or latest.get("start_at"),
    }


def latest_platform_order_status(order: dict | None) -> dict | None:
    if not order:
        return None
    for status, field in (
        ("post_production_finished", "post_production_finished_at"),
        ("post_production_started", "post_production_started_at"),
        ("production_finished", "produced_at"),
        ("picking_finished", "picking_completed_at"),
        ("picking_started", "picking_in_cells_at"),
    ):
        changed_at = order.get(field)
        if changed_at:
            return {
                "status": status,
                "changed_at": changed_at,
            }
    return None
