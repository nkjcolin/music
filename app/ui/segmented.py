"""A small inline selector that shows all its options as buttons.

Used on the Download page so short option sets (bitrate, codec, resolution)
are visible at a glance instead of hidden behind a dropdown.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QPushButton, QWidget


class SegmentedSelector(QWidget):
    """Exclusive set of checkable pills. ``options`` is a list of (label, data)."""

    changed = Signal()

    def __init__(self, options: list[tuple[str, object]], parent=None) -> None:
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        for index, (label, data) in enumerate(options):
            btn = QPushButton(label)
            btn.setObjectName("segOption")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("optionData", data)
            self._group.addButton(btn, index)
            lay.addWidget(btn)
            self._buttons.append(btn)
        if self._buttons:
            self._buttons[0].setChecked(True)
        # Only a user click counts as a change (programmatic set stays quiet).
        self._group.buttonClicked.connect(lambda _b: self.changed.emit())

    def current_data(self):
        btn = self._group.checkedButton()
        return btn.property("optionData") if btn else None

    def current_text(self) -> str:
        btn = self._group.checkedButton()
        return btn.text() if btn else ""

    def set_current_data(self, data) -> bool:
        for btn in self._buttons:
            if btn.property("optionData") == data:
                btn.setChecked(True)
                return True
        return False
