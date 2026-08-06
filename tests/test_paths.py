"""Tests for install data path resolution."""

from __future__ import annotations

from pathlib import Path

import paths


def test_get_data_dir_dev_is_package_dir(monkeypatch):
    monkeypatch.delattr(paths.sys, "frozen", raising=False)
    data = paths.get_data_dir()
    assert data == Path(__file__).resolve().parent.parent


def test_is_portable_false_when_not_frozen(monkeypatch):
    monkeypatch.delattr(paths.sys, "frozen", raising=False)
    assert paths.is_portable_install() is False
