"""

"""
from uuid import uuid4
import weakref

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


class ItemMeta(type):
    def __new__(cls, name, parents, dct):
        granularity = super(ItemMeta, cls).__new__(cls, name, parents,
                                                   dct)
        if 'granularity' in dct:
            GRANULARITIES.append(granularity)
        return granularity


#pylint: disable=no-member
@add_metaclass(ItemMeta)
class Item(object):
    __metaclass__ = ItemMeta

    def __init__(self, amount, multiples=1, namespace=None, uuid=None):
        self.key = "%s%s" % (namespace + "/" if namespace else "", uuid or uuid4().hex)
        self.amount = int(amount)
        self.multiples = int(multiples or 1)

    @classmethod
    def check_granularity_string(cls, granularity_string):
        return granularity_string.lower() in cls.granularity[1:]

    @property
    def expiry(self):
        return self.granularity[0] * self.multiples

    def key_for(self, *identifiers):
        return self.key if not identifiers else "%s/%s" % (self.key, "/".join(identifiers))

    def __eq__(self, other):
        return (self.amount == other.amount
                and self.granularity == other.granularity
        )

    def __repr__(self):
        return "%d per %s (namespace: %s)" % (self.amount, self.granularity[1], self.key)


#pylint: disable=invalid-name
class PER_YEAR(Item):
    granularity = TIME_TYPES["YEAR"]


class PER_MONTH(Item):
    granularity = TIME_TYPES["MONTH"]


class PER_DAY(Item):
    granularity = TIME_TYPES["DAY"]


class PER_HOUR(Item):
    granularity = TIME_TYPES["HOUR"]


class PER_MINUTE(Item):
    granularity = TIME_TYPES["MINUTE"]


class PER_SECOND(Item):
    granularity = TIME_TYPES["SECOND"]


class Limiter(object):
    def __init__(self, storage):
        self.storage = weakref.ref(storage)

    def hit(self, item, *identifiers):
        return (
            self.storage().set_and_get(item.key_for(*identifiers), item.expiry)
            <= item.amount
        )

    def check(self, item):
        return self.storage().get(item.key) <= item.amount
