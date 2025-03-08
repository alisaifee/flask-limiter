from __future__ import annotations

from collections.abc import Sequence
from typing import (
    Callable,
    Optional,
    TypeVar,
    Union,
    cast,
)

from typing_extensions import ParamSpec

R = TypeVar("R")
P = ParamSpec("P")


__all__ = [
    "R",
    "P",
    "Callable",
    "Optional",
    "Union",
    "cast",
    "Sequence",
    "TypeVar",
]
