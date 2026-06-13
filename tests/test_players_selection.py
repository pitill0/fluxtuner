import pytest

from fluxtuner.players import (
    PLAYER_BACKENDS,
    available_players,
    create_player,
    selected_player_name,
)
from fluxtuner.players.base import PlayerError


def set_availability(
    monkeypatch,
    *,
    mpv: bool,
    ffplay: bool,
    mpg123: bool = False,
    ogg123: bool = False,
) -> None:
    monkeypatch.setattr(PLAYER_BACKENDS["mpv"], "is_available", classmethod(lambda cls: mpv))
    monkeypatch.setattr(
        PLAYER_BACKENDS["ffplay"],
        "is_available",
        classmethod(lambda cls: ffplay),
    )
    monkeypatch.setattr(PLAYER_BACKENDS["mpg123"], "is_available", classmethod(lambda cls: mpg123))
    monkeypatch.setattr(PLAYER_BACKENDS["ogg123"], "is_available", classmethod(lambda cls: ogg123))


def test_available_players_returns_available_backend_names(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=True, ffplay=False)

    assert available_players() == ["mpv"]


def test_selected_player_name_auto_prefers_mpv(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=True, ffplay=True)

    assert selected_player_name("auto") == "mpv"


def test_selected_player_name_auto_falls_back_to_ffplay(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=True)

    assert selected_player_name("auto") == "ffplay"


def test_selected_player_name_auto_falls_back_to_mpg123_after_general_backends(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=False, mpg123=True)

    assert selected_player_name("auto") == "mpg123"


def test_selected_player_name_auto_falls_back_to_ogg123_last(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=False, mpg123=False, ogg123=True)

    assert selected_player_name("auto") == "ogg123"


def test_selected_player_name_raises_when_no_backend_available(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=False)

    with pytest.raises(PlayerError, match="No supported player backend available"):
        selected_player_name("auto")


def test_selected_player_name_rejects_unknown_backend() -> None:
    with pytest.raises(PlayerError, match="Unsupported player backend"):
        selected_player_name("unknown")


def test_selected_player_name_rejects_unavailable_requested_backend(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=True)

    with pytest.raises(PlayerError, match="Player backend 'mpv' is not available"):
        selected_player_name("mpv")


def test_create_player_uses_selected_backend(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=True)

    player = create_player("auto")

    assert player.name == "ffplay"


def test_create_player_uses_explicit_available_backend(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=True)

    player = create_player("ffplay")

    assert player.name == "ffplay"


def test_create_player_rejects_unavailable_backend(monkeypatch) -> None:
    set_availability(monkeypatch, mpv=False, ffplay=True)

    with pytest.raises(PlayerError, match="Player backend 'mpv' is not available"):
        create_player("mpv")
