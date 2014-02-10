import unittest
from flask_ratelimits import parser, limits

class RatelimitParserTests(unittest.TestCase):
	def test_singles(self):
		for rl_string in ["1 per hour", "1/hour", "1/HOUR", "1/Hour"]:
			self.assertEqual(
				parser.parse( rl_string),
			    limits.PER_HOUR("1")
			)
