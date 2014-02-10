"""

"""
import re
from . import limits

EXPR = re.compile(
	r"\s*([0-9]+)\s*(/|\s*per\s*)\s*(hour|minute|second|day|month|year)",
	re.IGNORECASE
)


def parse(limit_string):
	if not EXPR.match(limit_string):
		raise ValueError("couldn't parse rate limit string '%s'" % limit_string)
	amount, _, granularity_string = EXPR.findall(limit_string)[0]
	granularity = limits.granularity_from_string(granularity_string)
	return granularity(amount)


