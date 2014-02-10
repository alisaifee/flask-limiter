import unittest
from flask_ratelimits import parser, limits

class RatelimitParserTests(unittest.TestCase):
	def test_singles(self):
		for rl_string in ["1 per hour", "1/HOUR", "1/Hour"]:
			self.assertEqual(
				parser.parse( rl_string),
			    limits.PER_HOUR("1")
			)
		for rl_string in ["1 per minute", "1/MINUTE", "1/Minute"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_MINUTE("1")
			)
		for rl_string in ["1 per second", "1/SECOND", "1 / Second"]:
			self.assertEqual(
				parser.parse( rl_string),
				limits.PER_SECOND("1")
			)
