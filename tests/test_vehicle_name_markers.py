"""Game font markers should not leak into ordinary vehicle labels."""
import unittest
from unittest.mock import patch

import app


class VehicleNameMarkersTest(unittest.TestCase):
    def test_special_prefixes_are_removed_from_vehicle_display(self):
        self.assertEqual(app.display_vehicle_name("␗Su-30MKK"), "Su-30MKK")
        self.assertEqual(app.display_vehicle_name("▄F-100D"), "F-100D")
        self.assertEqual(app.display_vehicle_name("F-16A"), "F-16A")
        wiki = {"su_30mkk": {"name": "␗Su-30MKK", "research_country_code": "china",
                             "research_country": "China", "operator_country": "China"}}
        with patch.object(app, "wiki_catalog", return_value=wiki):
            self.assertEqual(app.vehicle("su_30mkk")["name"], "Su-30MKK")


if __name__ == "__main__":
    unittest.main()
