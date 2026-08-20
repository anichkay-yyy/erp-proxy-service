import unittest
from unittest.mock import Mock

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


class FivePostOrderSelectionTests(unittest.TestCase):
    def test_rejects_unrelated_search_result(self) -> None:
        client = FivePostClient(login="login", password="password")
        payload = {
            "content": [
                {
                    "orderId": "1a703443-37b9-35c0-8fb1-8b945cc07064",
                    "senderOrderId": "460170-elend",
                    "clientOrderId": "460170-elend",
                }
            ]
        }

        self.assertIsNone(client._select_order(payload, "6243383"))

    def test_selects_exact_result_instead_of_first_result(self) -> None:
        client = FivePostClient(login="login", password="password")
        expected = {
            "orderId": "matching-order",
            "senderOrderId": "6243383-print",
        }
        payload = {
            "content": [
                {"orderId": "unrelated-order", "senderOrderId": "460170-elend"},
                expected,
            ]
        }

        self.assertIs(client._select_order(payload, "6243383"), expected)

    def test_find_by_number_ignores_unrelated_results_from_all_queries(self) -> None:
        client = FivePostClient(login="login", password="password")
        unrelated_payload = {
            "content": [
                {
                    "orderId": "1a703443-37b9-35c0-8fb1-8b945cc07064",
                    "senderOrderId": "460170-elend",
                    "clientOrderId": "460170-elend",
                }
            ]
        }
        client._post_order_query = Mock(return_value=unrelated_payload)
        client._enrich_order = Mock()

        self.assertIsNone(client.find_by_number("6243383"))
        self.assertEqual(client._post_order_query.call_count, 2)
        client._enrich_order.assert_not_called()

    def test_query_variants_use_verifiable_order_identifiers_only(self) -> None:
        client = FivePostClient(login="login", password="password")

        self.assertEqual(
            client._query_variants("6243383"),
            [
                {"senderOrderId": "6243383"},
                {"clientOrderId": "6243383"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
