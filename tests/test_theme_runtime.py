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
