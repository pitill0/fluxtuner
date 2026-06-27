from __future__ import annotations

from fluxtuner.core import profiles


def test_active_profile_round_trip(monkeypatch) -> None:
    stored_config: dict[str, object] = {}

    monkeypatch.setattr(profiles.config, "load_config", lambda: dict(stored_config))

    def fake_save_config(value: dict[str, object]) -> None:
        stored_config.clear()
        stored_config.update(value)

    monkeypatch.setattr(profiles.config, "save_config", fake_save_config)

    assert profiles.get_active_profile_name() is None

    assert profiles.set_active_profile_name(" Work ") == "Work"
    assert profiles.get_active_profile_name() == "Work"
    assert profiles.resolve_effective_profile_name() == "Work"
    assert profiles.resolve_effective_profile_name(" Office ") == "Office"

    profiles.clear_active_profile_name()
    assert profiles.get_active_profile_name() is None
    assert profiles.ACTIVE_PROFILE_CONFIG_KEY not in stored_config


def test_get_active_profile_ignores_non_string_config(monkeypatch) -> None:
    monkeypatch.setattr(
        profiles.config,
        "get_config_value",
        lambda _key: 123,
    )

    assert profiles.get_active_profile_name() is None


def test_resolve_effective_profile_name_prefers_explicit_profile(monkeypatch) -> None:
    monkeypatch.setattr(
        profiles,
        "get_active_profile_name",
        lambda: "work",
    )

    assert profiles.resolve_effective_profile_name(" Office ") == "Office"
