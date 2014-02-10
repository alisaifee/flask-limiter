import unittest
from flask_ratelimits import parser, limits

class RatelimitParserTests(unittest.TestCase):
	def test_singles(self):
		for rl_string in ["1 per hour", "1/HOUR", "1/Hour"]:
			self.assertEqual(
				parser.parse( rl_string),
			    limits.PER_HOUR(1)
			)
		for rl_string in ["1 per minute", "1/MINUTE", "1/Minute"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_MINUTE(1)
			)
		for rl_string in ["1 per second", "1/SECOND", "1 / Second"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_SECOND(1)
			)
		for rl_string in ["1 per day", "1/DAY", "1 / Day"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_DAY(1)
			)
		for rl_string in ["1 per month", "1/MONTH", "1 / Month"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_MONTH(1)
			)
		for rl_string in ["1 per year", "1/Year", "1 / year"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_YEAR(1)
			)
	def test_invalid_string(self):
		self.assertRaises(ValueError, parser.parse, "1 per millienium")
		self.assertRaises(ValueError, limits.granularity_from_string, "millenium")

