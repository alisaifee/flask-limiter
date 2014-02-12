import unittest
from flask_limiter import limits


class GranularityTests(unittest.TestCase):
    def test_seconds_value(self):
        self.assertEqual(limits.PER_HOUR(1).expiry, 60*60)
        self.assertEqual(limits.PER_MINUTE(1).expiry, 60)
        self.assertEqual(limits.PER_SECOND(1).expiry, 1)
        self.assertEqual(limits.PER_DAY(1).expiry, 60*60*24)
        self.assertEqual(limits.PER_MONTH(1).expiry, 60*60*24*30)
        self.assertEqual(limits.PER_YEAR(1).expiry, 60*60*24*30*12)

    def test_representation(self):
        self.assertTrue("1 per 1 hour" in str(limits.PER_HOUR(1)))
        self.assertTrue("1 per 1 minute" in str(limits.PER_MINUTE(1)))
        self.assertTrue("1 per 1 second" in str(limits.PER_SECOND(1)))
        self.assertTrue("1 per 1 day" in str(limits.PER_DAY(1)))
        self.assertTrue("1 per 1 month" in str(limits.PER_MONTH(1)))
        self.assertTrue("1 per 1 year" in str(limits.PER_YEAR(1)))
