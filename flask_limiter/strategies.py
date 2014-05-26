"""
rate limiting strategies
"""

from abc import ABCMeta, abstractmethod
import weakref
import six
import time


@six.add_metaclass(ABCMeta)
class RateLimiter(object):
    def __init__(self, storage):
        self.storage = weakref.ref(storage)

    @abstractmethod
    def hit(self, item, *identifiers):
        """
        creates a hit on the rate limit and returns True if successful.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: True/False
        """
        raise NotImplementedError

    @abstractmethod
    def get_remaining(self, item, *identifiers):
        """
        returns the number of requests remaining within this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        raise NotImplementedError

    @abstractmethod
    def get_refresh(self, item, *identifiers):
        """
        returns the UTC time when the window will be refreshed

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        raise NotImplementedError


class MovingWindowRateLimiter(RateLimiter):

    def __init__(self, storage):
        if not hasattr(storage, "acquire_entry"):
            raise NotImplementedError("MovingWindowRateLimiting is not implemented for storage of type %s" % storage.__class__)
        super(MovingWindowRateLimiter, self).__init__(storage)

    def hit(self, item, *identifiers):
        """
        creates a hit on the rate limit and returns True if successful.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: True/False
        """
        return self.storage().acquire_entry(item.key_for(*identifiers), item.amount, item.expiry)


    def get_remaining(self, item, *identifiers):
        """
        returns the number of requests remaining within this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        return self.storage().get_acquirable(item.key_for(*identifiers), item.amount, item.expiry)

    def get_refresh(self, item, *identifiers):
        """
        returns the UTC time when the window will be refreshed

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        return int(time.time() + 1)

class FixedWindowRateLimiter(RateLimiter):
    def hit(self, item, *identifiers):
        """
        creates a hit on the rate limit and returns True if successful.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: True/False
        """
        return (
            self.storage().incr(item.key_for(*identifiers), item.expiry)
            <= item.amount
        )

    def get_remaining(self, item, *identifiers):
        """
        returns the number of requests remaining within this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        return max(0, item.amount - self.storage().get(item.key_for(*identifiers)))

    def get_refresh(self, item, *identifiers):
        """
        returns the UTC time when the window will be refreshed

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: int
        """
        return self.storage().get_expiry(item.key_for(*identifiers))

class FixedWindowElasticExpiryRateLimiter(FixedWindowRateLimiter):
    def hit(self, item, *identifiers):
        """
        creates a hit on the rate limit and returns True if successful.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: True/False
        """
        return (
            self.storage().incr(item.key_for(*identifiers), item.expiry, True)
            <= item.amount
        )

STRATEGIES = {
    "fixed-window": FixedWindowRateLimiter,
    "fixed-window-elastic-expiry": FixedWindowElasticExpiryRateLimiter,
    "moving-window": MovingWindowRateLimiter
}