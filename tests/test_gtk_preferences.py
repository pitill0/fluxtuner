"""Preferences contract tests without a required GTK display."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.gui.appearance import AppearanceMode
from fluxtuner.gui.gtk_preferences import (
    _appearance_selected,
    _dialog_close_request,
    _dialog_response,
    _open_storage_directory,
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
        button = FakeWidget(label=label)
        self.children.append((label, response))
        self.action_button = button
        return button

    def set_markup(self, markup):
        self.markup = markup

    def set_margin_end(self, value):
        self.margin_end = value

    def set_margin_top(self, value):
        self.margin_top = value

    def set_margin_bottom(self, value):
        self.margin_bottom = value

    def connect(self, signal, callback, *args):
        self.connections.append((signal, callback, args))

    def set_selectable(self, value):
        self.selectable = value

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


def test_dialog_storage_controls_restore_independent_defaults(tmp_path):
    on_storage = Mock()
    recordings = tmp_path / "recordings"
    rips = tmp_path / "rips"

    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        storage_directories={
            "recordings_directory": recordings,
            "rips_directory": rips,
        },
        storage_defaults={
            "recordings_directory": tmp_path / "default-recordings",
            "rips_directory": tmp_path / "default-rips",
        },
        on_storage_changed=on_storage,
        gtk=FAKE_GTK,
    )

    notebook = dialog.children[-1]
    storage_page = notebook.pages[2][0]

    # For each destination: heading, controls row, error label.
    assert len(storage_page.children) == 6

    first_row = storage_page.children[1]
    second_row = storage_page.children[4]

    for row in (first_row, second_row):
        assert row.children[1].children[0].kwargs["label"] == "Browse…"
        assert row.children[1].children[1].kwargs["label"] == "Open folder"
        assert row.children[1].children[2].kwargs["label"] == "Restore default"

    for row in (first_row, second_row):
        reset = row.children[1].children[2]
        signal, callback, args = reset.connections[0]
        assert signal == "clicked"
        callback(reset, *args)

    assert on_storage.call_args_list == [
        (("recordings_directory", None),),
        (("rips_directory", None),),
    ]


def test_open_storage_directory_uses_file_uri(tmp_path):
    error_label = Mock()
    launcher = Mock()

    _open_storage_directory(
        tmp_path,
        error_label=error_label,
        launcher=launcher,
    )

    launcher.assert_called_once_with(tmp_path.as_uri())
    error_label.set_text.assert_called_once_with("")


def test_open_storage_directory_rejects_missing_folder(tmp_path):
    error_label = Mock()
    launcher = Mock()
    missing = tmp_path / "missing"

    _open_storage_directory(
        missing,
        error_label=error_label,
        launcher=launcher,
    )

    launcher.assert_not_called()
    error_label.set_text.assert_called_once_with(f"Storage directory is not available: {missing}")
    assert not missing.exists()


def test_open_storage_directory_reports_launch_error(tmp_path):
    error_label = Mock()
    launcher = Mock(side_effect=OSError("No file manager"))

    _open_storage_directory(
        tmp_path,
        error_label=error_label,
        launcher=launcher,
    )

    error_label.set_text.assert_called_once_with(
        "Could not open storage directory: No file manager"
    )


def test_storage_open_button_tracks_reset(tmp_path, monkeypatch):
    from fluxtuner.gui import gtk_preferences

    custom = tmp_path / "custom"
    default = tmp_path / "default"
    custom.mkdir()
    default.mkdir()

    opened = []
    monkeypatch.setattr(
        gtk_preferences,
        "_open_storage_directory",
        lambda path, *, error_label: opened.append(path),
    )

    on_storage = Mock()
    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        storage_directories={"recordings_directory": custom},
        storage_defaults={"recordings_directory": default},
        on_storage_changed=on_storage,
        gtk=FAKE_GTK,
    )

    notebook = dialog.children[-1]
    storage_page = notebook.pages[2][0]
    row = storage_page.children[1]

    open_button = row.children[1].children[1]
    reset_button = row.children[1].children[2]

    signal, callback, args = open_button.connections[0]
    assert signal == "clicked"
    callback(open_button, *args)

    signal, callback, args = reset_button.connections[0]
    assert signal == "clicked"
    callback(reset_button, *args)

    signal, callback, args = open_button.connections[0]
    callback(open_button, *args)

    assert opened == [custom, default]
    on_storage.assert_called_once_with("recordings_directory", None)


def test_open_storage_directory_contains_desktop_error(tmp_path):
    error_label = Mock()

    class DesktopPortalError(Exception):
        pass

    launcher = Mock(side_effect=DesktopPortalError("Portal unavailable"))

    _open_storage_directory(
        tmp_path,
        error_label=error_label,
        launcher=launcher,
    )

    launcher.assert_called_once_with(tmp_path.as_uri())
    error_label.set_text.assert_called_once_with(
        "Could not open storage directory: Portal unavailable"
    )


def test_storage_open_button_tracks_browse(tmp_path, monkeypatch):
    from fluxtuner.gui import gtk_preferences

    original = tmp_path / "original"
    chosen = tmp_path / "chosen"
    original.mkdir()
    chosen.mkdir()

    opened = []

    def capture_open(path, *, error_label):
        opened.append(path)

    def fake_browse(_button, *, key, on_change, **_kwargs):
        on_change(key, chosen)

    monkeypatch.setattr(gtk_preferences, "_open_storage_directory", capture_open)
    monkeypatch.setattr(gtk_preferences, "_storage_browse", fake_browse)

    on_storage = Mock()
    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        storage_directories={"recordings_directory": original},
        storage_defaults={"recordings_directory": tmp_path / "default"},
        on_storage_changed=on_storage,
        gtk=FAKE_GTK,
    )

    notebook = dialog.children[-1]
    storage_page = notebook.pages[2][0]
    row = storage_page.children[1]

    browse_button = row.children[1].children[0]
    open_button = row.children[1].children[1]

    signal, callback, args = open_button.connections[0]
    assert signal == "clicked"
    callback(open_button, *args)

    signal, callback, args = browse_button.connections[0]
    assert signal == "clicked"
    callback(browse_button, *args)

    signal, callback, args = open_button.connections[0]
    callback(open_button, *args)

    assert opened == [original, chosen]
    on_storage.assert_called_once_with("recordings_directory", chosen)


def test_storage_layout_places_path_above_buttons(tmp_path):
    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        storage_directories={
            "recordings_directory": tmp_path / "recordings",
            "rips_directory": tmp_path / "rips",
        },
        storage_defaults={
            "recordings_directory": tmp_path / "default-recordings",
            "rips_directory": tmp_path / "default-rips",
        },
        on_storage_changed=Mock(),
        gtk=FAKE_GTK,
    )

    notebook = dialog.children[-1]
    storage_page = notebook.pages[2][0]

    assert len(storage_page.children) == 6

    for index in (1, 4):
        row = storage_page.children[index]

        assert row.kwargs["orientation"] == FAKE_GTK.Orientation.VERTICAL
        assert len(row.children) == 2

        path_label, button_row = row.children
        assert path_label.selectable is False

        assert path_label.kwargs["label"]
        assert button_row.kwargs["orientation"] == FAKE_GTK.Orientation.HORIZONTAL

        assert [child.kwargs["label"] for child in button_row.children] == [
            "Browse…",
            "Open folder",
            "Restore default",
        ]


def test_storage_polish_bold_headings_and_close_spacing(tmp_path):
    dialog = create_preferences_dialog(
        object(),
        appearance="system",
        on_appearance_changed=Mock(),
        storage_directories={
            "recordings_directory": None,
            "rips_directory": None,
        },
        storage_defaults={
            "recordings_directory": tmp_path / "recordings",
            "rips_directory": tmp_path / "rips",
        },
        on_storage_changed=Mock(),
        gtk=FAKE_GTK,
    )

    notebook = dialog.children[-1]
    storage_page = notebook.pages[2][0]

    assert storage_page.children[0].markup == ("<b>Continuous recordings</b>")
    assert storage_page.children[3].markup == ("<b>Ripped tracks</b>")

    assert dialog.action_button.kwargs["label"] == "Close"
    assert dialog.action_button.margin_end == 12
    assert dialog.action_button.margin_top == 12
    assert dialog.action_button.margin_bottom == 12
