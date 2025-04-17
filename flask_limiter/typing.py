from __future__ import annotations

from collections.abc import Callable, Generator, Iterator, Sequence
from typing import (
    ParamSpec,
    TypeVar,
    cast,
)

R = TypeVar("R")
P = ParamSpec("P")

__all__ = [
    "Callable",
    "Generator",
    "Iterator",
    "P",
    "R",
    "Sequence",
    "TypeVar",
    "cast",
]
