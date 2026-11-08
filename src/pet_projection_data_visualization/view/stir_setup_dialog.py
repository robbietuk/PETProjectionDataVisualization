# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Robert Twyman Skelly. Originally developed in STIR (https://github.com/UCL/STIR).
"""VIEW layer: the STIR setup window, bound to a ``StirSetupViewModel``.

Shown by the main window when a STIR file is opened and ``stir`` cannot be imported. It only forwards
input to the view model and shows its state; testing, saving and restarting happen behind it.
"""
from __future__ import annotations

from PySide6 import QtCore, QtWidgets

from ..viewmodel import BindingRegistry, StirSetupViewModel
from .components import silently


class StirSetupDialog(QtWidgets.QDialog):
    def __init__(self, setup: StirSetupViewModel, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setup = setup
        self.setWindowTitle("Set up STIR")
        self.setModal(True)
        self.setMinimumWidth(560)
        layout = QtWidgets.QVBoxLayout(self)

        self.explanation = QtWidgets.QLabel(setup.explanation)
        self.explanation.setWordWrap(True)
        layout.addWidget(self.explanation)

        row = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setPlaceholderText("STIR install folder or conda environment")
        self.path_edit.textEdited.connect(setup.set_path)
        self.browse_button = QtWidgets.QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse)
        row.addWidget(self.path_edit, 1)
        row.addWidget(self.browse_button)
        layout.addLayout(row)

        self.how_to = QtWidgets.QLabel(setup.how_to)
        self.how_to.setWordWrap(True)
        self.how_to.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.how_to)

        self.result_label = QtWidgets.QLabel("")
        self.result_label.setObjectName("StirSetupResult")
        self.result_label.setWordWrap(True)
        self.result_label.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.result_label)

        buttons = QtWidgets.QDialogButtonBox()
        self.test_button = buttons.addButton("Test", QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        self.save_button = buttons.addButton("Save", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = buttons.addButton(QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        # clicked, not the box's accepted/rejected: Save closes the window only when it worked
        self.test_button.clicked.connect(self._test)
        self.save_button.clicked.connect(self._save)
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(buttons)

        self.bindings = BindingRegistry(setup)
        self.bindings.bind("path", self._paint_path)
        self.bindings.bind("result", self._paint_result)
        self.bindings.bind("saved_path", lambda: self.save_button.setEnabled(setup.saved_path is None))
        self.bindings.start()
        self.finished.connect(self._on_finished)

    def _on_finished(self, _code: int) -> None:
        self.bindings.stop()

    def _browse(self) -> None:
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "STIR install folder", self.setup.path)
        if folder:
            self.setup.set_path(folder)

    def _busy(self) -> None:
        self.result_label.setText("Testing...")
        self.result_label.repaint()          # the test runs a child Python: show that something happens

    def _test(self) -> None:
        self._busy()
        self.setup.test()

    def _save(self) -> None:
        self._busy()
        if self.setup.save():
            self.accept()

    def _paint_path(self) -> None:
        if self.path_edit.text() != self.setup.path:
            silently(self.path_edit, lambda: self.path_edit.setText(self.setup.path))

    def _paint_result(self) -> None:
        result = self.setup.result
        if result is None:
            self.result_label.setText("")
            return
        mark = "\N{CHECK MARK}" if result.ok else "\N{BALLOT X}"
        self.result_label.setText(f"{mark} {result.message}")
