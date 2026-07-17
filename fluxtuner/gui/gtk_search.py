from __future__ import annotations


class SearchLifecycle:
    """Own GTK search request identity without depending on GTK or threads."""

    def __init__(self) -> None:
        self.generation = 0

    def begin(self) -> int:
        self.generation += 1
        return self.generation

    def is_current(self, generation: int) -> bool:
        return generation == self.generation
