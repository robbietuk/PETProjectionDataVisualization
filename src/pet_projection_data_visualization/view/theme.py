# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""Colour scheme and style tokens (no Qt import, so palettes and stylesheet are unit-tested anywhere).

Every colour in the UI comes from a ``Palette``; no widget hard-codes a colour. ``build_stylesheet``
turns a palette into one Qt stylesheet, and the plots read the same palette.
"""
from __future__ import annotations

from dataclasses import dataclass, fields


@dataclass(frozen=True)
class Palette:
    name: str
    # surfaces, darkest/lowest to highest
    canvas: str        # window background
    surface: str       # cards / panels, and the plot backgrounds inside them
    raised: str        # inputs, buttons, tiles
    border: str        # control outlines (inputs, buttons, tracks)
    border_subtle: str  # card and tile outlines, dividers
    # text
    text: str
    text_muted: str
    # accent and states
    accent: str
    accent_hover: str
    on_accent: str     # text on accent fills
    accent_subtle: str  # tinted fill behind ``text`` (chips, hovered menu items)
    danger: str
    on_danger: str
    success: str
    # plots
    plot_axis: str
    plot_grid: str
    curve: str
    marker: str


DARK = Palette(
    name="dark", canvas="#0d1117", surface="#161b22", raised="#1f252e", border="#363e4a",
    border_subtle="#262d37", text="#e8edf3", text_muted="#9ca7b4", accent="#58a6ff", accent_hover="#82bcff",
    on_accent="#04172d", accent_subtle="#1a2b42", danger="#ff7b72", on_danger="#2a0a08", success="#56d364",
    plot_axis="#9ca7b4", plot_grid="#262d37", curve="#58a6ff", marker="#ffb454")

LIGHT = Palette(
    name="light", canvas="#f4f6f9", surface="#ffffff", raised="#eff2f6", border="#cbd2db",
    border_subtle="#e1e6ec", text="#161b22", text_muted="#55606d", accent="#0a63c9", accent_hover="#0954aa",
    on_accent="#ffffff", accent_subtle="#e5effb", danger="#b3261e", on_danger="#ffffff", success="#1a7f37",
    plot_axis="#55606d", plot_grid="#e1e6ec", curve="#0a63c9", marker="#b45309")

PALETTES = {p.name: p for p in (DARK, LIGHT)}
DEFAULT_PALETTE = DARK

# spacing / shape tokens (px)
RADIUS = 10            # cards
RADIUS_SMALL = 6       # controls, tiles
GAP = 12               # between cards
PAD = 16               # inside cards
CHIP_HEIGHT = 24       # header chips are pills: radius CHIP_HEIGHT / 2
FONT_FAMILY = '"Inter", "Segoe UI Variable Text", "Segoe UI", "SF Pro Text", "Helvetica Neue", Arial, sans-serif'
MONO_FAMILY = '"JetBrains Mono", "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace'
# type scale (px)
FONT_SIZE_SMALL = 11   # captions: card titles, tile labels
FONT_SIZE = 13         # body
FONT_SIZE_LARGE = 15   # tile values
FONT_SIZE_TITLE = 17   # the data set title
FONT_SIZE_DISPLAY = 22  # empty-state heading
TYPE_SCALE = (FONT_SIZE_SMALL, FONT_SIZE, FONT_SIZE_LARGE, FONT_SIZE_TITLE, FONT_SIZE_DISPLAY)

# (foreground, background) pairs that must stay readable; checked by the tests
TEXT_PAIRS = (("text", "canvas"), ("text", "surface"), ("text", "raised"), ("text_muted", "canvas"),
              ("text_muted", "surface"), ("text_muted", "raised"), ("on_accent", "accent"),
              ("on_accent", "accent_hover"), ("text", "accent_subtle"), ("on_danger", "danger"),
              ("accent", "surface"), ("danger", "surface"), ("plot_axis", "surface"))


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"expected #rrggbb, got {hex_colour!r}")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _srgb_to_linear(r) + 0.7152 * _srgb_to_linear(g) + 0.0722 * _srgb_to_linear(b)


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two ``#rrggbb`` colours (1 .. 21)."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def palette_colours(p: Palette) -> dict[str, str]:
    return {f.name: getattr(p, f.name) for f in fields(p) if f.name != "name"}


def build_stylesheet(p: Palette) -> str:
    """One application-wide stylesheet. Widgets opt into variants through the dynamic property
    ``variant`` (``primary``, ``danger``, ``ghost``) and object names (``Card``, ``Chip``, ``Tile``...).

    The look is flat: surfaces are told apart by fill and a subtle 1 px outline, never by shadows, and
    the accent is the only saturated colour (selection, primary action, focus, checked state)."""
    return f"""
* {{ font-family: {FONT_FAMILY}; font-size: {FONT_SIZE}px; color: {p.text}; }}
QMainWindow, QDialog {{ background: {p.canvas}; }}
QWidget#Root, QWidget#Content {{ background: {p.canvas}; }}
QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 6px 8px; }}

QMenuBar {{ background: {p.canvas}; color: {p.text}; padding: 4px 8px; border-bottom: 1px solid {p.border_subtle}; }}
QMenuBar::item {{ background: transparent; padding: 5px 10px; border-radius: {RADIUS_SMALL}px; }}
QMenuBar::item:selected {{ background: {p.raised}; }}
QMenu {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL + 2}px; padding: 6px; }}
QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: {RADIUS_SMALL}px; }}
QMenu::item:selected {{ background: {p.accent_subtle}; color: {p.text}; }}
QMenu::separator {{ height: 1px; background: {p.border_subtle}; margin: 6px 8px; }}

QStatusBar {{ background: {p.canvas}; color: {p.text_muted}; border-top: 1px solid {p.border_subtle}; }}
QStatusBar QLabel {{ color: {p.text_muted}; padding: 0 8px; }}
QStatusBar::item {{ border: none; }}

QFrame#Card, QFrame#Sidebar {{ background: {p.surface}; border: 1px solid {p.border_subtle}; border-radius: {RADIUS}px; }}
QFrame#Card QLabel, QFrame#Sidebar QLabel {{ background: transparent; }}
QLabel#CardTitle {{ color: {p.text_muted}; font-size: {FONT_SIZE_SMALL}px; font-weight: 600; }}
QLabel#Muted {{ color: {p.text_muted}; }}
QLabel#Title {{ font-size: {FONT_SIZE_TITLE}px; font-weight: 600; }}
QLabel#PixelReadout {{ color: {p.text_muted}; font-family: {MONO_FAMILY}; }}
QPlainTextEdit#Mono {{ font-family: {MONO_FAMILY}; font-size: {FONT_SIZE - 1}px; }}
QLabel:disabled, QCheckBox:disabled, QMenu::item:disabled {{ color: {p.text_muted}; }}

QFrame#Chip {{ background: {p.accent_subtle}; border: 1px solid {p.border_subtle}; border-radius: {CHIP_HEIGHT // 2}px; }}
QFrame#Chip QLabel {{ background: transparent; color: {p.text}; font-size: {FONT_SIZE_SMALL + 1}px; padding: 0; }}

QFrame#Tile {{ background: {p.surface}; border: 1px solid {p.border_subtle}; border-radius: {RADIUS_SMALL + 2}px; }}
QFrame#Tile QLabel {{ background: transparent; }}
QLabel#TileLabel {{ color: {p.text_muted}; font-size: {FONT_SIZE_SMALL}px; }}
QLabel#TileValue {{ font-size: {FONT_SIZE_LARGE}px; font-weight: 600; }}

QFrame#Banner {{ background: {p.danger}; border-radius: {RADIUS_SMALL + 2}px; }}
QFrame#Banner QLabel {{ background: transparent; color: {p.on_danger}; font-weight: 600; }}
QFrame#Banner QPushButton {{ background: transparent; color: {p.on_danger}; border: none; font-weight: 700; padding: 2px 8px; }}

QWidget#EmptyState {{ background: transparent; }}
QLabel#EmptyTitle {{ font-size: {FONT_SIZE_DISPLAY}px; font-weight: 600; }}
QLabel#EmptyHint {{ color: {p.text_muted}; }}

QPushButton {{ background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 6px 14px; min-height: 18px; }}
QPushButton:hover {{ border-color: {p.text_muted}; }}
QPushButton:pressed {{ background: {p.border_subtle}; }}
QPushButton:disabled {{ color: {p.text_muted}; background: {p.surface}; border-color: {p.border_subtle}; }}
QPushButton:checked {{ background: {p.accent}; color: {p.on_accent}; border-color: {p.accent}; }}
QPushButton[variant="primary"] {{ background: {p.accent}; color: {p.on_accent}; border-color: {p.accent}; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; border-color: {p.accent_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: {p.border_subtle}; color: {p.text_muted}; border-color: {p.border_subtle}; }}
QPushButton[variant="ghost"] {{ background: transparent; border-color: transparent; }}
QPushButton[variant="ghost"]:hover {{ background: {p.raised}; }}
QPushButton:focus {{ border-color: {p.accent}; }}

QPushButton[segment="true"] {{ background: transparent; border: none; border-radius: {RADIUS_SMALL - 2}px; padding: 5px 8px; min-height: 16px; color: {p.text_muted}; }}
QPushButton[segment="true"]:hover {{ color: {p.text}; background: {p.surface}; }}
QPushButton[segment="true"]:checked {{ background: {p.accent}; color: {p.on_accent}; }}
QPushButton[segment="true"]:disabled {{ color: {p.border}; background: transparent; }}
QFrame#Segmented {{ background: {p.raised}; border: 1px solid {p.border_subtle}; border-radius: {RADIUS_SMALL + 1}px; }}
QPushButton[rail="true"] {{ padding: 10px 2px; font-size: {FONT_SIZE_SMALL + 1}px; }}
QPushButton[align="left"] {{ text-align: left; padding: 4px 8px; }}
QPushButton[compact="true"] {{ padding: 2px 8px; min-width: 12px; min-height: 16px; }}
QPushButton[segment="true"][compact="true"] {{ padding: 2px 8px; min-height: 14px; }}
QLabel#Peek {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px;
    padding: 8px 10px; }}
QLabel#Section {{ color: {p.text_muted}; font-size: {FONT_SIZE_SMALL}px; font-weight: 600; padding-top: 6px; }}
QLabel#Key {{ font-family: {MONO_FAMILY}; font-size: {FONT_SIZE - 1}px; }}
QLabel#StirState {{ font-weight: 600; }}
QLabel#StirState[tone="missing"] {{ color: {p.danger}; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {p.raised}; border: 1px solid {p.border}; border-radius: {RADIUS_SMALL}px; padding: 5px 8px;
    selection-background-color: {p.accent}; selection-color: {p.on_accent}; }}
QSpinBox[compact="true"] {{ padding: 2px 6px; }}
QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{ border-color: {p.text_muted}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {p.accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled, QComboBox:disabled {{ color: {p.text_muted}; background: {p.surface}; border-color: {p.border_subtle}; }}
QComboBox QAbstractItemView {{ background: {p.surface}; border: 1px solid {p.border}; selection-background-color: {p.accent_subtle}; selection-color: {p.text}; }}

QSlider::groove:horizontal {{ height: 4px; background: {p.border}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {p.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {p.surface}; width: 12px; height: 12px; margin: -6px 0; border-radius: 8px; border: 2px solid {p.accent}; }}
QSlider::handle:horizontal:hover {{ background: {p.accent_subtle}; }}
QSlider::sub-page:horizontal:disabled {{ background: {p.border}; }}
QSlider::handle:horizontal:disabled {{ background: {p.surface}; border-color: {p.border}; }}

QCheckBox {{ spacing: 10px; background: transparent; }}
QCheckBox::indicator {{ width: 32px; height: 18px; border-radius: 10px; background: {p.border}; border: 1px solid {p.border}; }}
QCheckBox::indicator:hover {{ border-color: {p.text_muted}; }}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}
QCheckBox::indicator:disabled {{ background: {p.surface}; border-color: {p.border_subtle}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 3px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QPlainTextEdit {{ background: {p.raised}; border: 1px solid {p.border_subtle}; border-radius: {RADIUS_SMALL}px; padding: 8px; }}
""".strip()
