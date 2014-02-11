import unittest
from flask_ratelimits import parser, limits

class GranularityTests(unittest.TestCase):
    def test_seconds_value(self):
        self.assertEqual(limits.PER_HOUR(1).seconds, 60*60)
        self.assertEqual(limits.PER_MINUTE(1).seconds, 60)
        self.assertEqual(limits.PER_SECOND(1).seconds, 1)
        self.assertEqual(limits.PER_DAY(1).seconds, 60*60*24)
        self.assertEqual(limits.PER_MONTH(1).seconds, 60*60*24*30)
        self.assertEqual(limits.PER_YEAR(1).seconds, 60*60*24*30*12)

    def test_representation(self):
        self.assertIn("1 per hour", str(limits.PER_HOUR(1)))
        self.assertIn("1 per minute", str(limits.PER_MINUTE(1)))
        self.assertIn("1 per second", str(limits.PER_SECOND(1)))
        self.assertIn("1 per day", str(limits.PER_DAY(1)))
        self.assertIn("1 per month", str(limits.PER_MONTH(1)))
        self.assertIn("1 per year", str(limits.PER_YEAR(1)))
