from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

from flask import request
from flask.wrappers import Response
from limits import RateLimitItem

from .typing import Callable, Sequence

if TYPE_CHECKING:
    from .extension import RequestLimit


@dataclasses.dataclass(eq=True, unsafe_hash=True)
class Limit:
    """
    simple wrapper to encapsulate limits and their context
    """

    limit: RateLimitItem
    key_func: Callable[[], str]
    _scope: str | Callable[[str], str] | None
    per_method: bool = False
    methods: Sequence[str] | None = None
    error_message: str | Callable[[], str] | None = None
    exempt_when: Callable[[], bool] | None = None
    override_defaults: bool | None = False
    deduct_when: Callable[[Response], bool] | None = None
    on_breach: Callable[[RequestLimit], Response | None] | None = None
    _cost: Callable[[], int] | int = 1
    shared: bool = False

    def __post_init__(self) -> None:
        if self.methods:
            self.methods = tuple([k.lower() for k in self.methods])

    @property
    def is_exempt(self) -> bool:
        """Check if the limit is exempt."""

        if self.exempt_when:
            return self.exempt_when()

        return False

    @property
    def scope(self) -> str | None:
        return (
            self._scope(request.endpoint or "")
            if callable(self._scope)
            else self._scope
        )

    @property
    def cost(self) -> int:
        if isinstance(self._cost, int):
            return self._cost

        return self._cost()

    @property
    def method_exempt(self) -> bool:
        """Check if the limit is not applicable for this method"""

        return self.methods is not None and request.method.lower() not in self.methods

    def scope_for(self, endpoint: str, method: str | None) -> str:
        """
        Derive final bucket (scope) for this limit given the endpoint
        and request method. If the limit is shared between multiple
        routes, the scope does not include the endpoint.
        """
        limit_scope = self.scope

        if limit_scope:
            if self.shared:
                scope = limit_scope
            else:
                scope = f"{endpoint}:{limit_scope}"
        else:
            scope = endpoint

        if self.per_method:
            assert method
            scope += f":{method.upper()}"

        return scope
