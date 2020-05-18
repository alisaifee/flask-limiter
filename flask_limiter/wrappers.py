from flask import request
from limits import parse_many


class Limit(object):
    """
    simple wrapper to encapsulate limits and their context
    """

    def __init__(
        self, limit, key_func, scope, per_method, methods, error_message,
        exempt_when, override_defaults, deduct_when
    ):
        self.limit = limit
        self.key_func = key_func
        self.__scope = scope
        self.per_method = per_method
        self.methods = methods
        self.error_message = error_message
        self.exempt_when = exempt_when
        self.override_defaults = override_defaults
        self.deduct_when = deduct_when

    @property
    def is_exempt(self):
        """Check if the limit is exempt."""
        return self.exempt_when and self.exempt_when()

    @property
    def scope(self):
        return self.__scope(request.endpoint) if callable(
            self.__scope
        ) else self.__scope

    @property
    def method_exempt(self):
        """Check if the limit is not applicable for this method"""
        return (
            self.methods is not None
            and request.method.lower() not in self.methods
        )


class LimitGroup(object):
    """
    represents a group of related limits either from a string or a callable
    that returns one
    """

    def __init__(
        self, limit_provider, key_function, scope, per_method, methods,
        error_message, exempt_when, override_defaults, deduct_when
    ):
        self.__limit_provider = limit_provider
        self.__scope = scope
        self.key_function = key_function
        self.per_method = per_method
        self.methods = methods and [m.lower() for m in methods] or methods
        self.error_message = error_message
        self.exempt_when = exempt_when
        self.override_defaults = override_defaults
        self.deduct_when = deduct_when

    def __iter__(self):
        limit_items = parse_many(
            self.__limit_provider()
            if callable(self.__limit_provider) else self.__limit_provider
        )
        for limit in limit_items:
            yield Limit(
                limit, self.key_function, self.__scope, self.per_method,
                self.methods, self.error_message, self.exempt_when,
                self.override_defaults, self.deduct_when
            )
