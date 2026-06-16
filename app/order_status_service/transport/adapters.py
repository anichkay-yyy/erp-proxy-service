from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class TransportLookupResult:
    adapter: str
    lookup_number: str
    payload: dict
    erp_order_number: str | None = None
    carrier_track_number: str | None = None
    delivery_status_code: str | None = None
    delivery_status_label: str | None = None


class TransportAdapter(Protocol):
    name: str

    def find_by_number(self, number: str) -> TransportLookupResult | None:
        """Find shipment/order data by ERP order number or carrier track number."""


class CompositeTransportAdapter:
    name = "composite"

    def __init__(self, adapters: list[TransportAdapter]):
        self.adapters = adapters

    def find_by_number(self, number: str) -> TransportLookupResult | None:
        for adapter in self._adapters_for_number(number):
            try:
                result = adapter.find_by_number(number)
            except Exception:
                result = None
            if result:
                return result
        return None

    def _adapters_for_number(self, number: str) -> list[TransportAdapter]:
        if re.match(r"^\s*\d{5,12}-[A-Za-z0-9]+\\s*$", str(number or "")):
            return sorted(self.adapters, key=lambda adapter: 0 if adapter.name == "fivepost" else 1)
        return self.adapters
