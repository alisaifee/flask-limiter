"""

"""
from six import add_metaclass

Types = dict(
	DAY=(0, "day"),
	MONTH=(1, "month"),
	YEAR=(2, "year"),
	HOUR=(3, "hour"),
	MINUTE=(4, "minute"),
	SECOND=(5, "second")
)

Granularities = []


class GranularityMeta(type):
	def __new__(cls, name, parents, dct):
		granularity = super(GranularityMeta, cls).__new__(cls, name, parents,
		                                                  dct)
		if 'granularity' in dct:
			Granularities.append(granularity)
		return granularity

@add_metaclass(GranularityMeta)
class Granularity(object):
	__metaclass__ = GranularityMeta

	def __init__(self, amount):
		self.amount = amount

	@classmethod
	def check_granularity_string(cls, granularity_string):
		return granularity_string.lower() in cls.granularity[1:]

	def __eq__(self, other):
		return (self.amount == other.amount
		        and self.granularity == other.granularity
		)

class PER_HOUR(Granularity):
	granularity = Types["HOUR"]

class PER_MINUTE(Granularity):
	granularity = Types["MINUTE"]

class PER_SECOND(Granularity):
	granularity = Types["SECOND"]

def granularity_from_string(granularity_string):
	for granularity in Granularities:
		if granularity.check_granularity_string(granularity_string):
			return granularity
