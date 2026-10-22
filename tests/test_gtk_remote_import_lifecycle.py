# SPDX-License-Identifier: MIT
"""Offline GTK remote import lifecycle regression tests."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui import gtk_m3u_import as importer


class FakeWidget:
    def __init__(self, **kwargs):
        self.props = kwargs
        self.handlers = {}
        self.text = ""
        self.destroyed = False

    def __getattr__(self, name):
        if name.startswith(("set_", "grab_", "present")):
            return lambda *_args: None
        raise AttributeError(name)

    def connect(self, signal, callback):
        self.handlers[signal] = callback

    def append(self, _child):
        pass

    def set_text(self, text):
        self.text = text

    def get_text(self):
        return self.text

    def destroy(self):
        self.destroyed = True
        if "destroy" in self.handlers:
            self.handlers["destroy"](self)

    def get_content_area(self):
        return self

    def add_button(self, *_args):
        return FakeWidget()


@pytest.fixture
def gtk_harness(monkeypatch):
    callbacks = []
    workers = []
    dialogs = []

    class FakeDialog(FakeWidget):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            dialogs.append(self)

    class FakeThread:
        def __init__(self, *, target, **_kwargs):
            self.target = target

        def start(self):
            workers.append(self.target)

    gtk = SimpleNamespace(
        Dialog=FakeDialog,
        Entry=FakeWidget,
        Label=FakeWidget,
        ResponseType=SimpleNamespace(CANCEL=0, ACCEPT=1),
    )
    glib = SimpleNamespace(idle_add=lambda callback, *args: callbacks.append((callback, args)))

    gi = ModuleType("gi")
    gi.require_version = lambda *_args: None
    repository = ModuleType("gi.repository")
    repository.Gtk = gtk
    repository.GLib = glib

    monkeypatch.setitem(sys.modules, "gi", gi)
    monkeypatch.setitem(sys.modules, "gi.repository", repository)
    monkeypatch.setattr(importer.threading, "Thread", FakeThread)

    return SimpleNamespace(
        callbacks=callbacks,
        workers=workers,
        dialogs=dialogs,
        gtk=gtk,
    )


def _open(harness, *, profile_is_current=lambda: True):
    parent = SimpleNamespace(
        _m3u_import_dialog=None,
        _m3u_import_remote_dialog=None,
    )
    saved = Mock()
    errors = Mock()
    importer.open_remote_m3u_import(
        parent,
        profile_id=1,
        profile_is_current=profile_is_current,
        on_saved=saved,
        on_error=errors,
    )
    dialog = harness.dialogs[-1]
    return parent, dialog, saved, errors


def _start(dialog, url="https://catalog.example/stations.m3u"):
    # Entry is the first appended content widget.
    entry = dialog.children[0]
    entry.text = url
    dialog.handlers["response"](dialog, 1)


def test_cancelled_dialog_discards_late_download(gtk_harness, monkeypatch):
    def append(self, child):
        self.children = getattr(self, "children", [])
        self.children.append(child)

    monkeypatch.setattr(FakeWidget, "append", append)
    preview = Mock()
    monkeypatch.setattr(importer, "_show_preview", preview)
    session = object()
    monkeypatch.setattr(
        importer,
        "prepare_remote_m3u_import",
        lambda *_args, **_kwargs: session,
    )

    parent, dialog, saved, _errors = _open(gtk_harness)
    _start(dialog)
    assert len(gtk_harness.workers) == 1

    dialog.handlers["response"](dialog, 0)
    assert dialog.destroyed
    assert parent._m3u_import_remote_dialog is None

    gtk_harness.workers[0]()
    assert len(gtk_harness.callbacks) == 1

    callback, args = gtk_harness.callbacks.pop()
    assert callback(*args) is False
    preview.assert_not_called()
    saved.assert_not_called()


def test_changed_profile_discards_completed_download(gtk_harness, monkeypatch):
    def append(self, child):
        self.children = getattr(self, "children", [])
        self.children.append(child)

    monkeypatch.setattr(FakeWidget, "append", append)
    state = {"current": True}
    preview = Mock()
    monkeypatch.setattr(importer, "_show_preview", preview)
    monkeypatch.setattr(
        importer,
        "prepare_remote_m3u_import",
        lambda *_args, **_kwargs: object(),
    )

    parent, dialog, saved, _errors = _open(
        gtk_harness,
        profile_is_current=lambda: state["current"],
    )
    _start(dialog)
    gtk_harness.workers[0]()

    state["current"] = False
    callback, args = gtk_harness.callbacks.pop()
    assert callback(*args) is False

    assert dialog.destroyed
    assert parent._m3u_import_remote_dialog is None
    preview.assert_not_called()
    saved.assert_not_called()
