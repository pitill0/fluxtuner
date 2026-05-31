import logging

from fluxtuner import theme_runtime


class FailingStyles:
    def __setattr__(self, _name, _value):
        raise RuntimeError("unsupported style")


def test_set_if_supported_logs_unsupported_style(caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        theme_runtime._set_if_supported(FailingStyles(), "color", "red")

    assert "Ignoring unsupported runtime theme style property: color" in caplog.text


class FailingQueryApp:
    screen = object()

    def query(self, _target):
        raise RuntimeError("query failed")

    def refresh(self, *, layout: bool = False) -> None:
        self.refreshed = layout


def test_apply_theme_runtime_logs_failed_selector(monkeypatch, tmp_path, caplog) -> None:
    theme_file = tmp_path / "test.tcss"
    theme_file.write_text("#stations { color: red; }", encoding="utf-8")

    monkeypatch.setattr(theme_runtime, "get_theme_path", lambda _name: theme_file)

    app = FailingQueryApp()

    with caplog.at_level(logging.DEBUG):
        assert theme_runtime.apply_theme_runtime(app, "test") == theme_file

    assert "Skipping runtime theme selector that could not be applied: #stations" in caplog.text


class RecordingStyles:
    def __init__(self) -> None:
        self.values = {}

    def __setattr__(self, name, value):
        if name == "values":
            object.__setattr__(self, name, value)
            return
        self.values[name] = value


class FakeWidget:
    def __init__(self) -> None:
        self.styles = RecordingStyles()


class SuccessfulThemeApp:
    def __init__(self) -> None:
        self.screen = FakeWidget()
        self.toolbar = FakeWidget()
        self.refreshed = False

    def query(self, target):
        if target == "#toolbar":
            return [self.toolbar]
        return []

    def refresh(self, *, layout: bool = False) -> None:
        self.refreshed = layout


def test_apply_theme_runtime_applies_supported_screen_and_selector_styles(
    monkeypatch,
    tmp_path,
) -> None:
    theme_file = tmp_path / "test.tcss"
    theme_file.write_text(
        """
        Screen {
            background: black;
            color: white;
        }

        #toolbar {
            padding: 1 2;
            margin: 3;
        }

        UnknownWidget {
            color: red;
        }
        """,
        encoding="utf-8",
    )

    monkeypatch.setattr(theme_runtime, "get_theme_path", lambda _name: theme_file)

    app = SuccessfulThemeApp()

    assert theme_runtime.apply_theme_runtime(app, "test") == theme_file

    assert app.screen.styles.values["background"] == "black"
    assert app.screen.styles.values["color"] == "white"
    assert app.toolbar.styles.values["padding"] == (1, 2, 1, 2)
    assert app.toolbar.styles.values["margin"] == (3, 3, 3, 3)
    assert app.refreshed is True


def test_parse_tcss_ignores_variables_and_unsupported_selectors(tmp_path) -> None:
    theme_file = tmp_path / "test.tcss"
    theme_file.write_text(
        """
        Screen {
            background: $surface;
            color: white;
        }

        Unsupported {
            color: red;
        }
        """,
        encoding="utf-8",
    )

    assert theme_runtime.parse_tcss(theme_file) == {
        "Screen": {
            "color": "white",
        }
    }
