import unittest

from order_status_service.transport.fivepost_client import FivePostClient


class FivePostTrackingUrlTests(unittest.TestCase):
    def test_tracking_url_uses_public_order_number_not_cargo_barcode(self) -> None:
        client = FivePostClient(login="login", password="password")
        result = client._build_result(
            "450236FPerp",
            {
                "order": {
                    "senderOrderId": "450236FPerp",
                    "clientOrderId": "450236FPerp",
                },
                "cargoes": [{"omniBarcode": "10000224944799"}],
            },
        )

        self.assertEqual(result.carrier_track_number, "10000224944799")
        self.assertEqual(
            result.payload["trackingUrl"],
            "https://fivepost.ru/tracking/?id=450236FPerp",
        )

    def test_tracking_url_uses_order_number_from_details(self) -> None:
        client = FivePostClient(login="login", password="password")
        result = client._build_result(
            "10000224944799",
            {
                "order": {},
                "details": {"clientOrderId": "450236FPerp"},
                "cargoes": [{"omniBarcode": "10000224944799"}],
            },
        )

        self.assertEqual(
            result.payload["trackingUrl"],
            "https://fivepost.ru/tracking/?id=450236FPerp",
        )

    def test_tracking_url_preserves_upstream_url(self) -> None:
        client = FivePostClient(login="login", password="password")
        result = client._build_result(
            "450236FPerp",
            {
                "order": {
                    "senderOrderId": "450236FPerp",
                    "trackingUrl": "https://tracking.example/order/450236FPerp",
                },
                "cargoes": [{"omniBarcode": "10000224944799"}],
            },
        )

        self.assertEqual(
            result.payload["trackingUrl"],
            "https://tracking.example/order/450236FPerp",
        )


if __name__ == "__main__":
    unittest.main()
