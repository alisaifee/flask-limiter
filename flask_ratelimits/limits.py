"""

"""
from six import add_metaclass

TIME_TYPES = dict(
    DAY=(60 * 60 * 24, "day"),
    MONTH=(60 * 60 * 24 * 30, "month"),
    YEAR=(60 * 60 * 24 * 30 * 12, "year"),
    HOUR=(60 * 60, "hour"),
    MINUTE=(60, "minute"),
    SECOND=(1, "second")
)

GRANULARITIES = []


class GranularityMeta(type):
    def __new__(cls, name, parents, dct):
        granularity = super(GranularityMeta, cls).__new__(cls, name, parents,
                                                          dct)
        if 'granularity' in dct:
            GRANULARITIES.append(granularity)
        return granularity

#pylint: disable=no-member
@add_metaclass(GranularityMeta)
class Granularity(object):
    __metaclass__ = GranularityMeta

    def __init__(self, amount):
        self.amount = int(amount)

    @classmethod
    def check_granularity_string(cls, granularity_string):
        return granularity_string.lower() in cls.granularity[1:]

    @property
    def seconds(self):
        return self.granularity[0]

    def __eq__(self, other):
        return (self.amount == other.amount
                and self.granularity == other.granularity
        )

    def __repr__(self):
        return "%d per %s" % (self.amount, self.granularity[1])

#pylint: disable=invalid-name
class PER_YEAR(Granularity):
    granularity = TIME_TYPES["YEAR"]


class PER_MONTH(Granularity):
    granularity = TIME_TYPES["MONTH"]


class PER_DAY(Granularity):
    granularity = TIME_TYPES["DAY"]


class PER_HOUR(Granularity):
    granularity = TIME_TYPES["HOUR"]


class PER_MINUTE(Granularity):
    granularity = TIME_TYPES["MINUTE"]


class PER_SECOND(Granularity):
    granularity = TIME_TYPES["SECOND"]


def granularity_from_string(granularity_string):
    for granularity in GRANULARITIES:
        if granularity.check_granularity_string(granularity_string):
            return granularity
    raise ValueError("no granularity matched for %s" % granularity_string)
