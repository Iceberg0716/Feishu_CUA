"""Action type definitions for agent operations."""

from dataclasses import dataclass
from typing import Union


@dataclass
class ClickAction:
    x: int
    y: int
    button: str = "left"


@dataclass
class DoubleClickAction:
    x: int
    y: int


@dataclass
class TypeAction:
    text: str


@dataclass
class HotkeyAction:
    keys: list[str]


@dataclass
class ScrollAction:
    dy: int


Action = Union[ClickAction, DoubleClickAction, TypeAction, HotkeyAction, ScrollAction]
