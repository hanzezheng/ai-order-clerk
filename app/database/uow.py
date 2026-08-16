from __future__ import annotations

from collections.abc import Callable

from app.services.ports import UnitOfWork


class InMemoryUnitOfWork(UnitOfWork):
    """内存：只控制 Outbox 可见性。其它 InMemory 仓仍立即写入。"""

    def __init__(self) -> None:
        self._active = False
        self._on_commit: list[Callable[[], None]] = []
        self._on_rollback: list[Callable[[], None]] = []

    def on_commit(self, hook: Callable[[], None]) -> None:
        self._on_commit.append(hook)

    def on_rollback(self, hook: Callable[[], None]) -> None:
        self._on_rollback.append(hook)

    def active(self) -> bool:
        return self._active

    def begin(self) -> None:
        self._active = True

    def commit(self) -> None:
        for hook in self._on_commit:
            hook()
        self._active = False

    def rollback(self) -> None:
        for hook in self._on_rollback:
            hook()
        self._active = False
