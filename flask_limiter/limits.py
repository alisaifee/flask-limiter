"""

"""
from six import add_metaclass
try:
    from functools import total_ordering
except ImportError: # pragma: no cover
    from .backports.total_ordering import total_ordering # pragma: no cover

TIME_TYPES = dict(
    DAY=(60 * 60 * 24, "day"),
    MONTH=(60 * 60 * 24 * 30, "month"),
    YEAR=(60 * 60 * 24 * 30 * 12, "year"),
    HOUR=(60 * 60, "hour"),
    MINUTE=(60, "minute"),
    SECOND=(1, "second")
)

GRANULARITIES = []


class RateLimitItemMeta(type):
    def __new__(cls, name, parents, dct):
        granularity = super(RateLimitItemMeta, cls).__new__(cls, name, parents,
                                                   dct)
        if 'granularity' in dct:
            GRANULARITIES.append(granularity)
        return granularity


#pylint: disable=no-member
@add_metaclass(RateLimitItemMeta)
@total_ordering
class RateLimitItem(object):
    """
    defines a Rate limited resource which contains characteristics
     namespace, amount and granularity of rate limiting window.
    """
    __metaclass__ = RateLimitItemMeta
    __slots__ = ["namespace", "amount", "multiples", "granularity"]
    def __init__(self, amount, multiples=1, namespace='LIMITER'):
        self.namespace = namespace
        self.amount = int(amount)
        self.multiples = int(multiples or 1)

    @classmethod
    def check_granularity_string(cls, granularity_string):
        """
        checks if this instance matches a granularity string
        of type 'n per hour' etc.

        :return: True/False
        """
        return granularity_string.lower() in cls.granularity[1:]

    def get_expiry(self):
        """
        :return: the size of the window in seconds.
        """
        return self.granularity[0] * self.multiples

    def key_for(self, *identifiers):
        """
        :param identifiers: a list of strings to append to the key
        :return: a string key identifying this resource with
         each identifier appended with a '/' delimiter.
        """
        remainder = "/".join(
            identifiers + (
                str(self.amount), str(self.multiples), self.granularity[1]
            )
        )
        return "%s/%s" % (self.namespace, remainder)

    def __eq__(self, other):
        return (self.amount == other.amount
                and self.granularity == other.granularity
        )

    def __repr__(self):
        return "%d per %d %s" % (
            self.amount, self.multiples, self.granularity[1]
        )

    def __lt__(self, other):
        return self.granularity[0] < other.granularity[0]

#pylint: disable=invalid-name
class PER_YEAR(RateLimitItem):
    granularity = TIME_TYPES["YEAR"]


class PER_MONTH(RateLimitItem):
    granularity = TIME_TYPES["MONTH"]


class PER_DAY(RateLimitItem):
    granularity = TIME_TYPES["DAY"]


class PER_HOUR(RateLimitItem):
    granularity = TIME_TYPES["HOUR"]


class PER_MINUTE(RateLimitItem):
    granularity = TIME_TYPES["MINUTE"]


class PER_SECOND(RateLimitItem):
    granularity = TIME_TYPES["SECOND"]

