import unittest

from order_status_service.transport.saferoute_client import SafeRouteClient


class SafeRouteOrderSelectionTests(unittest.TestCase):
    def test_rejects_unrelated_search_result(self) -> None:
        client = SafeRouteClient(email="login", password="password")
        payload = {
            "data": [
                {
                    "id": "unrelated-shipment",
                    "cmsId": "460170-elend",
                    "trackNumber": "10000227956273",
                }
            ]
        }

        self.assertIsNone(client._select_order_search_result(payload, "6243383"))

    def test_selects_exact_result_instead_of_first_result(self) -> None:
        client = SafeRouteClient(email="login", password="password")
        expected = {
            "id": "matching-shipment",
            "cmsId": "6243383-print",
            "trackNumber": "10000227956274",
        }
        payload = {
            "data": [
                {
                    "id": "unrelated-shipment",
                    "cmsId": "460170-elend",
                    "trackNumber": "10000227956273",
                },
                expected,
            ]
        }

        self.assertIs(
            client._select_order_search_result(payload, "6243383"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
