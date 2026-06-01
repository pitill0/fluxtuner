import asyncio
from typing import Any

from fluxtuner import tui


class FakeTask:
    def __init__(self, *, done: bool = False) -> None:
        self._done = done
        self.cancelled = False

    def done(self) -> bool:
        return self._done

    def cancel(self) -> None:
        self.cancelled = True


class FakeInput:
    def __init__(self, value: str) -> None:
        self.value = value


class LiveSearchApp:
    def __init__(self) -> None:
        self._search_task = None
        self.status_messages: list[str] = []
        self.query_value = ""
        self.search_calls: list[tuple[str, bool]] = []

    def cancel_pending_search(self) -> None:
        tui.FluxTunerTUI.cancel_pending_search(self)  # type: ignore[arg-type]

    def schedule_live_search(self, query: str) -> None:
        tui.FluxTunerTUI.schedule_live_search(self, query)  # type: ignore[arg-type]

    async def _debounced_search(self, query: str) -> None:
        await tui.FluxTunerTUI._debounced_search(self, query)  # type: ignore[arg-type]

    def set_status(self, message: str) -> None:
        self.status_messages.append(message)

    def query_one(self, selector: str, _widget_type: Any = None) -> FakeInput:
        assert selector == "#query"
        return FakeInput(self.query_value)

    async def search(self, query: str, live: bool = False) -> None:
        self.search_calls.append((query, live))


async def immediate_sleep(_seconds: float) -> None:
    return None


async def cancelled_sleep(_seconds: float) -> None:
    raise asyncio.CancelledError


def test_cancel_pending_search_cancels_active_task() -> None:
    app = LiveSearchApp()
    task = FakeTask(done=False)
    app._search_task = task

    app.cancel_pending_search()

    assert task.cancelled is True
    assert app._search_task is None


def test_cancel_pending_search_ignores_finished_task() -> None:
    app = LiveSearchApp()
    task = FakeTask(done=True)
    app._search_task = task

    app.cancel_pending_search()

    assert task.cancelled is False
    assert app._search_task is None


def test_schedule_live_search_empty_query_does_not_create_task() -> None:
    app = LiveSearchApp()

    app.schedule_live_search("   ")

    assert app._search_task is None
    assert app.status_messages == [
        "Type at least 3 characters to search, or press Enter for an exact short search."
    ]


def test_schedule_live_search_short_query_does_not_create_task() -> None:
    app = LiveSearchApp()

    app.schedule_live_search("ro")

    assert app._search_task is None
    assert app.status_messages == ["Keep typing... live search starts at 3 characters."]


def test_schedule_live_search_cancels_previous_task_before_scheduling(monkeypatch) -> None:
    app = LiveSearchApp()
    old_task = FakeTask(done=False)
    new_task = FakeTask(done=False)
    created_coroutines = []

    app._search_task = old_task

    def fake_create_task(coro):
        created_coroutines.append(coro)
        coro.close()
        return new_task

    monkeypatch.setattr(asyncio, "create_task", fake_create_task)

    app.schedule_live_search("rock")

    assert old_task.cancelled is True
    assert app._search_task is new_task
    assert len(created_coroutines) == 1


def test_debounced_search_runs_when_query_is_still_current(monkeypatch) -> None:
    app = LiveSearchApp()
    app.query_value = "rock"

    monkeypatch.setattr(tui.asyncio, "sleep", immediate_sleep)

    asyncio.run(app._debounced_search("rock"))

    assert app.search_calls == [("rock", True)]


def test_debounced_search_ignores_stale_query(monkeypatch) -> None:
    app = LiveSearchApp()
    app.query_value = "jazz"

    monkeypatch.setattr(tui.asyncio, "sleep", immediate_sleep)

    asyncio.run(app._debounced_search("rock"))

    assert app.search_calls == []


def test_debounced_search_swallows_cancellation(monkeypatch) -> None:
    app = LiveSearchApp()
    app.query_value = "rock"

    monkeypatch.setattr(tui.asyncio, "sleep", cancelled_sleep)

    asyncio.run(app._debounced_search("rock"))

    assert app.search_calls == []
