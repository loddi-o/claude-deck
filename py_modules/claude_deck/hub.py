"""Event hub: numbers every UI event, keeps a ring buffer for re-sync and forwards to Decky."""

from __future__ import annotations

from collections import deque
from typing import Any, Awaitable, Callable, Deque, Dict, List, Tuple

Emit = Callable[..., Awaitable[None]]

# Kinds replayed to a UI that (re)connects: they are enough to rebuild the whole chat.
PERSISTENT = {"msg", "history", "perm", "perm_done", "notice", "reset"}


class Hub:
    def __init__(self, emit: Emit, log: Any, ring_size: int = 900):
        self._emit = emit
        self._log = log
        self.seq = 0
        self.ring: Deque[Tuple[int, str, Dict[str, Any]]] = deque(maxlen=ring_size)

    async def publish(self, kind: str, payload: Dict[str, Any], persist: bool | None = None) -> int:
        self.seq += 1
        if persist is None:
            persist = kind in PERSISTENT
        if persist:
            self.ring.append((self.seq, kind, payload))
        try:
            await self._emit("cd", self.seq, kind, payload)
        except Exception as exc:  # noqa: BLE001 - a dead websocket must never break the agent
            self._log.warning("emit failed (%s): %s", kind, exc)
        return self.seq

    def snapshot(self) -> List[List[Any]]:
        return [[s, k, p] for s, k, p in self.ring]

    def clear(self) -> None:
        self.ring.clear()
