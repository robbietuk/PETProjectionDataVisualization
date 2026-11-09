# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Choice lists shared by every control that offers the same choices (Qt-free).

One ``ChoiceOptions`` describes a closed set of choices: what the user sees, what the view model
stores, and how to convert between them. The view's segmented controls and combo boxes are built
from it, so labels and ordering exist in exactly one place.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Generic, Hashable, Mapping, Sequence, TypeVar

from ..model import SliceMode, TofMode
from .playback import PlayMode
from .profiles import LineMode

T = TypeVar("T", bound=Hashable)
E = TypeVar("E", bound=Enum)

COLORMAPS: Final = ("viridis", "inferno", "magma", "plasma", "cividis", "grey")


class LevelMode(Enum):
    """How the colour levels (Min/Max, the colour bar) behave while navigating.

    ADAPTIVE: recomputed from every slice shown. LOCKED: frozen at one (Min, Max) pair until the user
    edits them or unlocks; "global range" is an action that locks at the whole data set's range."""
    ADAPTIVE = "Adaptive (per slice)"
    LOCKED = "Locked (constant)"


@dataclass(frozen=True)
class ChoiceOptions(Generic[T]):
    """An ordered, immutable set of ``(value, label)`` choices."""

    values: tuple[T, ...]
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.values) != len(self.labels):
            raise ValueError("values and labels must have the same length")
        if not self.values:
            raise ValueError("a choice set needs at least one choice")
        if len(set(self.values)) != len(self.values):
            raise ValueError("choice values must be unique")

    @classmethod
    def from_enum(cls, enum_type: type[E], labels: Mapping[E, str] | None = None) -> ChoiceOptions[E]:
        members = tuple(enum_type)
        return cls(members, tuple((labels or {}).get(m, m.value) for m in members))

    @classmethod
    def from_values(cls, values: Sequence[T], labels: Sequence[str] | None = None) -> ChoiceOptions[T]:
        items = tuple(values)
        return cls(items, tuple(labels) if labels is not None else tuple(str(v) for v in items))

    def __len__(self) -> int:
        return len(self.values)

    def index_of(self, value: T) -> int:
        try:
            return self.values.index(value)
        except ValueError:
            raise KeyError(f"{value!r} is not one of {self.values}") from None

    def value_at(self, index: int) -> T:
        if not 0 <= index < len(self.values):
            raise IndexError(f"choice index {index} out of range 0..{len(self.values) - 1}")
        return self.values[index]

    def label_of(self, value: T) -> str:
        return self.labels[self.index_of(value)]


SLICE_MODE_OPTIONS = ChoiceOptions.from_enum(
    SliceMode, {SliceMode.SINOGRAM: "Sinogram", SliceMode.VIEWGRAM: "Viewgram", SliceMode.TANGENTIAL: "Tangential"})
TOF_MODE_OPTIONS = ChoiceOptions.from_enum(
    TofMode, {TofMode.BIN: "Bin", TofMode.SUM: "Sum", TofMode.MEAN: "Mean", TofMode.MAX: "Max"})
LEVEL_MODE_OPTIONS = ChoiceOptions.from_enum(
    LevelMode, {LevelMode.ADAPTIVE: "Adaptive", LevelMode.LOCKED: "Locked"})
COLORMAP_OPTIONS = ChoiceOptions.from_values(COLORMAPS)
PLAY_MODE_OPTIONS = ChoiceOptions.from_enum(PlayMode)
LINE_MODE_OPTIONS = ChoiceOptions.from_enum(LineMode)

# (keys, what they do), listed in the Profiles and settings flyout
KEYBOARD_SHORTCUTS: Final = (
    ("Space", "Play or pause the axis played last"),
    ("Left / Right", "Step the fixed axis (axial, view or tangential)"),
    ("Page Up / Page Down", "Next or previous segment"),
    ("L", "Lock or unlock the colour levels"),
    ("F", "Freeze the profiles at the cursor, or release them (like a click on the image)"),
    ("Esc", "Close the open flyout; otherwise release frozen profiles"),
)
