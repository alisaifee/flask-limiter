"""
rate limiting strategies
"""

from abc import ABCMeta, abstractmethod
import weakref
import six


@six.add_metaclass(ABCMeta)
class RateLimiter(object):
    def __init__(self, storage):
        self.storage = weakref.ref(storage)

    @abstractmethod
    def hit(self, item, *identifiers):
        """
        """
        raise NotImplementedError

    @abstractmethod
    def check(self, item, *identifiers):
        """
        """
        raise NotImplementedError


class MovingWindowRateLimiter(RateLimiter):
    def __init__(self, storage):
        if not hasattr(storage, "acquire_entry"):
            raise NotImplementedError("MovingWindowRateLimiting is not implemented for storage of type %s" % storage.__class__)
        super(MovingWindowRateLimiter, self).__init__(storage)

    def hit(self, item, *identifiers):
        """
        """
        return self.storage().acquire_entry(item.key_for(*identifiers), item.amount, item.expiry)

    def check(self, item, *identifiers):
        """
        """
        return self.storage().acquire_entry(item.key_for(*identifiers), item.amount, item.expiry, True)


class FixedWindowRateLimiter(RateLimiter):
    def hit(self, item, *identifiers):
        """
        """
        return (
            self.storage().incr(item.key_for(*identifiers), item.expiry)
            <= item.amount
        )
    def check(self, item, *identifiers):
        """
        """
        return self.storage().get(item.key_for(*identifiers)) <= item.amount


class FixedWindowElasticExpiryRateLimiter(FixedWindowRateLimiter):
    def hit(self, item, *identifiers):
        """
        """
        return (
            self.storage().incr(item.key_for(*identifiers), item.expiry, True)
            <= item.amount
        )

STRATEGIES = {
    "fixed-window": FixedWindowRateLimiter,
    "fixed-window-elastic": FixedWindowElasticExpiryRateLimiter,
    "moving-window": MovingWindowRateLimiter
}