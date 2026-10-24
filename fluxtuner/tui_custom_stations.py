"""Modal form for adding a personal station through the shared core."""

from __future__ import annotations

from collections.abc import Callable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from fluxtuner.core import db
from fluxtuner.core.custom_stations import add_custom_station


class CustomStationScreen(ModalScreen[bool | None]):
    """Capture one station without changing the underlying application view."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    CustomStationScreen {
        align: center middle;
        background: $background 80%;
    }
    CustomStationScreen #custom-station-form {
        width: 64;
        max-width: 95%;
        height: auto;
        max-height: 95%;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }
    CustomStationScreen Input {
        margin-bottom: 1;
    }
    CustomStationScreen #custom-station-error {
        color: $error;
        height: auto;
        min-height: 1;
        margin-bottom: 1;
    }
    CustomStationScreen #custom-station-actions {
        height: 3;
    }
    CustomStationScreen Button {
        margin-right: 1;
    }
    """

    def __init__(
        self,
        *,
        profile_id: int,
        profile_is_current: Callable[[], bool],
    ) -> None:
        super().__init__()
        self._profile_id = profile_id
        self._profile_is_current = profile_is_current

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="custom-station-form"):
            yield Label("Add station")
            yield Static("Saved to favorites in the current profile.")
            yield Label("Station name")
            yield Input(placeholder="My radio", id="custom-station-name")
            yield Label("Stream URL")
            yield Input(
                placeholder="https://example.org/live",
                id="custom-station-url",
            )
            yield Static("", id="custom-station-error", markup=False)
            with Horizontal(id="custom-station-actions"):
                yield Button("Add", id="custom-station-save", variant="primary")
                yield Button("Cancel", id="custom-station-cancel")

    def on_mount(self) -> None:
        self.query_one("#custom-station-name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#custom-station-cancel")
    def cancel_from_button(self) -> None:
        self.action_cancel()

    @on(Input.Submitted, "#custom-station-name")
    def focus_stream_url(self, event: Input.Submitted) -> None:
        event.stop()
        self.query_one("#custom-station-url", Input).focus()

    @on(Input.Submitted, "#custom-station-url")
    def save_from_input(self, event: Input.Submitted) -> None:
        event.stop()
        self.save_station()

    @on(Button.Pressed, "#custom-station-save")
    def save_station(self) -> None:
        try:
            if not self._profile_is_current():
                raise ValueError("The profile changed. Reopen this dialog.")
            with db.connect() as conn:
                added = add_custom_station(
                    conn,
                    profile_id=self._profile_id,
                    name=self.query_one("#custom-station-name", Input).value,
                    url=self.query_one("#custom-station-url", Input).value,
                    record_manual_provenance=True,
                )
                conn.commit()
        except Exception as exc:  # noqa: BLE001 - contained form/storage failure.
            self.query_one("#custom-station-error", Static).update(str(exc))
            return
        self.dismiss(added)
