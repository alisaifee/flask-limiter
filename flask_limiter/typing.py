from __future__ import annotations

from collections.abc import Callable, Generator, Sequence
from typing import (
    TypeVar,
    cast,
)

from typing_extensions import ParamSpec

R = TypeVar("R")
P = ParamSpec("P")


__all__ = [
    "Callable",
    "Generator",
    "P",
    "R",
    "Sequence",
    "TypeVar",
    "cast",
]
