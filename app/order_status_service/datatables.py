def datatables_order_params(
    by_date: str,
    query: str = "",
    query_type: str = "number",
    start: int = 0,
    length: int = 25,
    draw: int = 1,
    filters: dict | None = None,
) -> dict:
    columns = [
        "number",
        "created_at",
        "number",
        "status",
        "price",
        "payment_status",
        "delivery_system_id",
        "buyer_id",
        "number",
        "showcase_id",
        "status_updated_at",
    ]
    params = {
        "draw": str(draw),
        "order[0][column]": "0",
        "order[0][dir]": "desc",
        "start": str(start),
        "length": str(length),
        "search[value]": "",
        "search[regex]": "false",
        "by_showcase": "",
        "by_status": "",
        "by_payment_status": "",
        "by_payment_system": "",
        "by_delivery": "",
        "by_track_status": "",
        "by_date": by_date,
        "by_query_type": query_type,
        "by_query": query,
    }
    if filters:
        for key, value in filters.items():
            params[key] = "" if value is None else str(value)
    for index, data in enumerate(columns):
        params[f"columns[{index}][data]"] = data
        params[f"columns[{index}][name]"] = ""
        params[f"columns[{index}][searchable]"] = "true"
        params[f"columns[{index}][orderable]"] = "false" if index in (2, 8) else "true"
        params[f"columns[{index}][search][value]"] = ""
        params[f"columns[{index}][search][regex]"] = "false"
    return params

