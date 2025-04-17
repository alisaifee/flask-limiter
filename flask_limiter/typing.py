from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from typing import (
    ParamSpec,
    TypeVar,
    cast,
)

from typing_extensions import Self

R = TypeVar("R")
P = ParamSpec("P")

__all__ = [
    "Callable",
    "Generator",
    "Iterable",
    "Iterator",
    "P",
    "R",
    "Sequence",
    "Self",
    "TypeVar",
    "cast",
]
