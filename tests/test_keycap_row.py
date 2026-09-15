"""Tests for KeyCapRow shortcut display and record mode."""

from __future__ import annotations

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QLabel

from widgets import KeyCapRow, split_portable_sequence


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_split_portable_sequence():
    assert split_portable_sequence("Ctrl+Shift+Space") == ["Ctrl", "Shift", "Space"]
    assert split_portable_sequence("") == ["Unbound"]
    assert split_portable_sequence("Escape") == ["Escape"]


def test_record_mode_clears_idle_caps(qapp):
    row = KeyCapRow("Ctrl+Alt+M")
    row.show()
    qapp.processEvents()

    visible_before = [
        c
        for c in row.findChildren(QLabel)
        if c.objectName() == "keyCap" and c.isVisible() and c.text()
    ]
    assert len(visible_before) == 3

    row._enter_record_mode()
    qapp.processEvents()

    idle_caps = [
        c
        for c in row.findChildren(QLabel)
        if c.objectName() == "keyCap" and c.isVisible() and c.text()
    ]
    assert idle_caps == []

    empty = row.findChild(QLabel, "keyCapEmpty")
    assert empty is not None
    assert empty.isVisible()

    row._exit_record_mode(cancel=True)
    qapp.processEvents()

    restored = [
        c
        for c in row.findChildren(QLabel)
        if c.objectName() == "keyCap" and c.isVisible() and c.text()
    ]
    assert len(restored) == 3


def test_record_mode_grows_with_modifier(qapp):
    row = KeyCapRow("Escape")
    row.show()
    row._enter_record_mode()
    qapp.processEvents()

    from PyQt6.QtGui import QKeyEvent
    from PyQt6.QtCore import QEvent

    mod_event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Control,
        Qt.KeyboardModifier.ControlModifier,
    )
    row.keyPressEvent(mod_event)
    qapp.processEvents()

    filled = [
        c
        for c in row.findChildren(QLabel)
        if c.objectName() == "keyCap" and c.isVisible() and c.text()
    ]
    assert [c.text() for c in filled] == ["Ctrl"]
    assert row.findChild(QLabel, "keyCapEmpty").isVisible()
