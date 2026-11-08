# SPDX-License-Identifier: Apache-2.0
"""Reusable components under real PySide6 (offscreen). Skipped where Qt is not installed."""
import os

import pytest

pytest.importorskip("PySide6")
pytest.importorskip("pyqtgraph")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from pet_projection_data_visualization.model import SliceMode  # noqa: E402
from pet_projection_data_visualization.view import components as ui  # noqa: E402
from pet_projection_data_visualization.view.styling import apply_theme  # noqa: E402
from pet_projection_data_visualization.view.theme import CHIP_HEIGHT, DARK, LIGHT  # noqa: E402
from pet_projection_data_visualization.viewmodel import COLORMAP_OPTIONS, SLICE_MODE_OPTIONS  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize("make", [lambda: ui.SegmentedControl(SLICE_MODE_OPTIONS),
                                  lambda: ui.ChoiceCombo(SLICE_MODE_OPTIONS)], ids=["segmented", "combo"])
def test_choice_controls_share_one_contract(app, make):
    ctrl = make()
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl.set_choice(SliceMode.VIEWGRAM)
    assert ctrl.choice() is SliceMode.VIEWGRAM and seen == []      # programmatic updates never emit


def test_segmented_click_emits_the_value(app):
    ctrl = ui.SegmentedControl(SLICE_MODE_OPTIONS)
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl._buttons[2].click()
    assert seen == [SliceMode.TANGENTIAL] and ctrl.choice() is SliceMode.TANGENTIAL
    ctrl.set_choice_enabled(SliceMode.SINOGRAM, False)
    assert not ctrl._buttons[0].isEnabled()


def test_combo_activation_emits_the_value(app):
    ctrl = ui.ChoiceCombo(COLORMAP_OPTIONS)
    seen = []
    ctrl.choiceChanged.connect(seen.append)
    ctrl._combo.activated.emit(1)
    assert seen == [COLORMAP_OPTIONS.values[1]]


def test_chip_row_grows_shrinks_and_reuses_widgets(app):
    row = ui.ChipRow()
    row.set_chips(["a", "b", "c"])
    assert row.texts() == ["a", "b", "c"]
    first = row._chips[0]
    row.set_chips(["x"])
    assert row.texts() == ["x"] and row._chips[0] is first and len(row._chips) == 3


def test_metric_grid_fills_wraps_and_hides_extras(app):
    grid = ui.MetricGrid(columns=3)
    grid.set_metrics([("Min", "1"), ("Max", "2"), ("Mean", "3"), ("Std", "4")])
    assert grid.pairs() == [("Min", "1"), ("Max", "2"), ("Mean", "3"), ("Std", "4")]
    grid.set_metrics([("Only", "9")])
    assert grid.pairs() == [("Only", "9")]


def test_banner_shows_hides_and_emits_dismissed(app):
    b = ui.Banner()
    assert b.isHidden()
    b.show_message("boom")
    assert not b.isHidden() and b.label.text() == "boom"
    fired = []
    b.dismissed.connect(lambda: fired.append(1))
    b.findChild(QtWidgets.QPushButton).click()
    assert fired == [1]
    b.show_message(None)
    assert b.isHidden()


def test_card_title_and_body(app):
    assert ui.Card("Slice").title_label.text() == "SLICE" and ui.Card().title_label.isHidden()
    card = ui.Card("x")
    card.body.addWidget(QtWidgets.QLabel("hi"))
    assert card.body.count() == 1


def test_empty_state_actions_call_back(app):
    es = ui.EmptyState("t", "h")
    hits = []
    btn = es.add_action("Go", lambda: hits.append(1), primary=True)
    btn.click()
    assert hits == [1] and btn.property("variant") == "primary"


def test_empty_state_keeps_qwidget_actions(app):
    """The button row must not shadow QWidget.actions() (it used to be stored as ``self.actions``)."""
    es = ui.EmptyState("t", "h")
    btn = es.add_action("Go", lambda: None)
    assert es.actions() == [] and es.action_row.indexOf(btn) == 0


def test_dimension_control_emits_only_for_user_edits(app):
    ctrl = ui.DimensionControl()
    seen = []
    ctrl.userChanged.connect(seen.append)
    ctrl.show_state("Axial", 0, 7, 3, True)
    assert seen == [] and ctrl._spin.value() == 3 and ctrl._range.text().startswith("0")
    ctrl._spin.setValue(5)
    assert seen == [5] and ctrl._slider.value() == 5


def test_apply_theme_installs_stylesheet_and_palette(app):
    for pal in (DARK, LIGHT):
        apply_theme(app, pal)
        assert pal.accent in app.styleSheet()
        assert app.palette().window().color().name() == pal.canvas


def test_apply_theme_sets_disabled_text_colour(app):
    from PySide6 import QtGui
    apply_theme(app, DARK)
    c = app.palette().color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText)
    assert c.name() == DARK.text_muted


def _settle(app, widget):
    widget.show()
    for _ in range(3):
        app.processEvents()


@pytest.mark.parametrize("text", ["axial 11", "Sinogram segment -12, axial 140, TOF bin 33 of 33 (Sum)"])
def test_chip_is_never_smaller_than_its_text(app, text):
    apply_theme(app, DARK)
    chip = ui.Chip(text)
    _settle(app, chip)
    metrics = chip.label.fontMetrics()
    assert chip.sizeHint().height() >= max(CHIP_HEIGHT, metrics.height())
    assert chip.height() >= CHIP_HEIGHT
    assert chip.label.width() >= metrics.horizontalAdvance(text)
    assert chip.label.height() >= metrics.height()
    chip.close()


def test_chip_row_keeps_its_size_beside_a_long_title(app):
    apply_theme(app, DARK)
    header = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(header)
    title = ui.ElidedLabel("a very long data set title " * 8)
    chips = ui.ChipRow()
    chips.set_chips(["Sinogram", "segment 0", "axial 11", "TOF bin 4"])
    row.addWidget(title, 1)
    row.addWidget(chips)
    header.resize(500, 40)
    _settle(app, header)
    assert chips.width() >= chips.sizeHint().width()
    for chip in chips._chips:
        assert chip.label.width() >= chip.label.fontMetrics().horizontalAdvance(chip.label.text())
    assert title.is_elided() and title.toolTip() == title.text()
    header.close()


def test_elided_label_keeps_its_text_and_only_elides_when_short_of_space(app):
    label = ui.ElidedLabel("short")
    label.resize(400, 30)
    _settle(app, label)
    assert not label.is_elided() and label.toolTip() == ""
    label.setText("much longer text than fits in a few pixels")
    label.resize(60, 30)
    app.processEvents()
    assert label.is_elided() and label.text() == "much longer text than fits in a few pixels"
    assert label.minimumSizeHint().width() < label.sizeHint().width()
    label.close()


def test_metric_grid_reflows_into_balanced_rows_when_narrow(app):
    apply_theme(app, DARK)
    holder = QtWidgets.QWidget()                          # a top-level layout would pin the grid's minimum
    grid = ui.MetricGrid(columns=6, parent=holder)
    grid.set_metrics([(f"Name {i}", f"{i * 1000.5:.4g}") for i in range(6)])
    grid.resize(1200, 80)
    _settle(app, holder)
    assert grid.column_count() == 6
    narrow = grid.minimumSizeHint().width()
    assert narrow < grid.sizeHint().width()
    grid.resize(narrow, 200)
    app.processEvents()
    assert grid.column_count() == 3                       # 3 + 3, not 4 + 2
    assert [p[0] for p in grid.pairs()] == [f"Name {i}" for i in range(6)]
    grid.resize(1200, 80)
    app.processEvents()
    assert grid.column_count() == 6
    holder.close()


def test_side_panel_narrows_to_its_content_but_never_cuts_it_off(app):
    apply_theme(app, DARK)
    content = QtWidgets.QWidget()
    col = QtWidgets.QVBoxLayout(content)
    wide = QtWidgets.QPushButton("a button with a fairly long caption")
    col.addWidget(wide)
    panel = ui.SidePanel(content, max_width=500)
    assert panel.horizontalScrollBarPolicy() == QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert panel.minimumWidth() == 0 and panel.maximumWidth() == 500     # not a fixed width
    assert content.minimumSizeHint().width() < panel.minimumSizeHint().width() <= 500
    assert panel.sizeHint().width() == 500
    holder = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(holder)
    row.addWidget(panel)
    row.addWidget(QtWidgets.QWidget(), 1)
    holder.resize(100, 200)                              # narrower than the content
    _settle(app, holder)
    assert panel.width() >= panel.minimumSizeHint().width()
    assert panel.viewport().width() >= content.minimumSizeHint().width()
    holder.close()
