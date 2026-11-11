"""Preferences contract tests without a required GTK display."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui.appearance import AppearanceMode
from fluxtuner.gui.gtk_preferences import (
    _appearance_selected,
    _dialog_close_request,
    _dialog_response,
    appearance_from_index,
    appearance_index,
    create_preferences_dialog,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("system", 0),
        ("dark", 1),
        ("light", 2),
        ("invalid", 0),
        (None, 0),
    ],
)
def test_appearance_index(value, expected):
    assert appearance_index(value) == expected


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, AppearanceMode.SYSTEM),
        (1, AppearanceMode.DARK),
        (2, AppearanceMode.LIGHT),
        (3, None),
        (-1, None),
        (2**32 - 1, None),
    ],
)
def test_appearance_from_index(index, expected):
    assert appearance_from_index(index) == expected


def test_appearance_callback_ignores_invalid_selection():
    notify = Mock()
    dropdown = SimpleNamespace(get_selected=lambda: 2)
    _appearance_selected(dropdown, object(), notify)
    notify.assert_called_once_with(AppearanceMode.LIGHT)

    notify.reset_mock()
    dropdown = SimpleNamespace(get_selected=lambda: 2**32 - 1)
    _appearance_selected(dropdown, object(), notify)
    notify.assert_not_called()


def test_response_hides_dialog_without_destroying_it():
    dialog = Mock()
    _dialog_response(dialog, 0)
    dialog.hide.assert_called_once_with()
    dialog.destroy.assert_not_called()


def test_titlebar_close_hides_dialog_and_prevents_destruction():
    dialog = Mock()
    assert _dialog_close_request(dialog) is True
    dialog.hide.assert_called_once_with()
    dialog.destroy.assert_not_called()


class FakeWidget:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.children = []
        self.pages = []
        self.connections = []
        self.selected = None
        self.destroyed = False
        self.hidden = False
        self.titlebar = None
        self.css_classes = []

    def __getattr__(self, name):
        if name.startswith("set_") or name == "add_css_class":
            return Mock()
        raise AttributeError(name)

    def append(self, child):
        self.children.append(child)

    def pack_end(self, child):
        self.children.append(child)

    def set_titlebar(self, titlebar):
        self.titlebar = titlebar

    def add_css_class(self, name):
        self.css_classes.append(name)

    def append_page(self, page, label):
        self.pages.append((page, label))

    def get_content_area(self):
        return self

    def add_button(self, label, response):
        self.children.append((label, response))

    def connect(self, signal, callback, *args):
        self.connections.append((signal, callback, args))

    def set_selected(self, value):
        self.selected = value

    def get_selected(self):
        return self.selected

    def destroy(self):
        self.destroyed = True

    def hide(self):
        self.hidden = True


class FakeDropDown(FakeWidget):
    @classmethod
    def new_from_strings(cls, values):
        return cls(values=values)


FAKE_GTK = SimpleNamespace(
    Dialog=FakeWidget,
    HeaderBar=FakeWidget,
    Button=FakeWidget,
    Notebook=FakeWidget,
    Box=FakeWidget,
    Label=FakeWidget,
    DropDown=FakeDropDown,
    ResponseType=SimpleNamespace(CLOSE=1),
    Orientation=SimpleNamespace(VERTICAL=1, HORIZONTAL=2),
)


def test_dialog_builds_three_pages_and_appearance_control():
    parent = object()
    on_change = Mock()

    dialog = create_preferences_dialog(
        parent,
        appearance="dark",
        on_appearance_changed=on_change,
        gtk=FAKE_GTK,
    )

    assert dialog.kwargs["transient_for"] is parent
    assert dialog.kwargs["modal"] is False

    notebook = dialog.children[-1]
    assert [label.kwargs["label"] for _, label in notebook.pages] == [
        "General",
        "Appearance",
        "Storage",
    ]

    appearance_page = notebook.pages[1][0]
    row = appearance_page.children[0]
    dropdown = row.children[1]

    assert dropdown.selected == 1
    signal, callback, args = dropdown.connections[0]
    assert signal == "notify::selected"

    dropdown.set_selected(2)
    callback(dropdown, object(), *args)
    on_change.assert_called_once_with(AppearanceMode.LIGHT)

    assert not dialog.destroyed
    assert [item[0] for item in dialog.connections] == [
        "response",
        "close-request",
    ]

    response_handler = dialog.connections[0][1]
    response_handler(dialog, 1)

    assert dialog.hidden
    assert not dialog.destroyed

    dialog.hidden = False
    close_handler = dialog.connections[1][1]
    assert close_handler(dialog) is True
    assert dialog.hidden
    assert not dialog.destroyed


def test_preferences_dialog_has_scoped_css_class():
    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        gtk=FAKE_GTK,
    )
    assert dialog is not None


@pytest.mark.parametrize(
    "filename",
    [
        "light.css",
        "dark.css",
    ],
)
def test_preferences_palette_has_scoped_notebook_rules(filename):
    from fluxtuner.gui.appearance import THEMES_DIR

    css = (THEMES_DIR / filename).read_text()

    assert "window.fluxtuner-preferences headerbar" in css
    assert "window.fluxtuner-preferences notebook > header" in css
    assert ("window.fluxtuner-preferences notebook > header > tabs > tab:checked") in css
    assert "window.fluxtuner-preferences notebook > stack" in css


def test_custom_titlebar_close_hides_reusable_dialog():
    dialog = create_preferences_dialog(
        object(),
        appearance="light",
        on_appearance_changed=Mock(),
        gtk=FAKE_GTK,
    )

    assert dialog.titlebar is not None

    header = dialog.titlebar
    close_button = header.children[-1]

    assert close_button.kwargs["label"] == "×"
    assert "fluxtuner-preferences-close" in close_button.css_classes

    signal, callback, args = close_button.connections[0]
    assert signal == "clicked"

    callback(close_button, *args)

    assert dialog.hidden
    assert not dialog.destroyed
