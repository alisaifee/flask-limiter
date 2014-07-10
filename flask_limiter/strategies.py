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
    def get_window_stats(self, item, *identifiers):
        """
        returns the number of requests remaining and reset of this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: tuple (reset time (int), remaining (int))
        """
        raise NotImplementedError



class MovingWindowRateLimiter(RateLimiter):

    def __init__(self, storage):
        if not (hasattr(storage, "acquire_entry") or hasattr(storage, "get_moving_window")):
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
        return self.storage().acquire_entry(item.key_for(*identifiers), item.amount, item.get_expiry())

    def get_window_stats(self, item, *identifiers):
        """
        returns the number of requests remaining within this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: tuple (reset time (int), remaining (int))
        """
        window_start, window_items = self.storage().get_moving_window(
                item.key_for(*identifiers), item.amount, item.get_expiry()
            )
        reset = window_start + item.get_expiry()
        return (reset, item.amount - window_items)


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
            self.storage().incr(item.key_for(*identifiers), item.get_expiry())
            <= item.amount
        )

    def get_window_stats(self, item, *identifiers):
        """
        returns the number of requests remaining and reset of this limit.

        :param item: a :class:`RateLimitItem` instance
        :param identifiers: variable list of strings to uniquely identify the
         limit
        :return: tuple (reset time (int), remaining (int))
        """
        remaining = max(0, item.amount - self.storage().get(item.key_for(*identifiers)))
        reset = self.storage().get_expiry(item.key_for(*identifiers))
        return (reset, remaining)

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
            self.storage().incr(item.key_for(*identifiers), item.get_expiry(), True)
            <= item.amount
        )

STRATEGIES = {
    "fixed-window": FixedWindowRateLimiter,
    "fixed-window-elastic-expiry": FixedWindowElasticExpiryRateLimiter,
    "moving-window": MovingWindowRateLimiter
}