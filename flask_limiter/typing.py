from __future__ import annotations

from collections.abc import Sequence
from typing import (
    Callable,
    TypeVar,
    cast,
)

from typing_extensions import ParamSpec

R = TypeVar("R")
P = ParamSpec("P")


__all__ = [
    "R",
    "P",
    "Callable",
    "cast",
    "Sequence",
    "TypeVar",
]
