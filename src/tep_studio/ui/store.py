"""Server-side cache of ``RunResult`` objects keyed by run id.

Heavy run artifacts live here (not in the browser's ``dcc.Store``). Backed by a
``diskcache.Cache`` when one is supplied -- required so results computed inside a
Dash background-callback worker are visible to the main process -- with an
in-memory ``OrderedDict`` LRU fallback for tests and the synchronous app. This
module is Dash-free; diskcache is optional.
"""

from __future__ import annotations

from collections import OrderedDict

from tep_studio.ui.results import RunResult

_INDEX_KEY = "__run_index__"


class RunStore:
    def __init__(self, *, cache=None, capacity: int = 50) -> None:
        self._cache = cache  # diskcache.Cache | None
        self._capacity = int(capacity)
        self._mem: "OrderedDict[str, RunResult]" = OrderedDict()

    def put(self, result: RunResult) -> str:
        run_id = result.run_id
        if self._cache is not None:
            index = [i for i in self._cache.get(_INDEX_KEY, []) if i != run_id]
            index.append(run_id)
            self._cache.set(f"run:{run_id}", result)
            while len(index) > self._capacity:
                evicted = index.pop(0)
                self._cache.delete(f"run:{evicted}")
            self._cache.set(_INDEX_KEY, index)
        else:
            self._mem[run_id] = result
            self._mem.move_to_end(run_id)
            while len(self._mem) > self._capacity:
                self._mem.popitem(last=False)
        return run_id

    def get(self, run_id: str) -> RunResult | None:
        if self._cache is not None:
            return self._cache.get(f"run:{run_id}")
        result = self._mem.get(run_id)
        if result is not None:
            self._mem.move_to_end(run_id)
        return result

    def has(self, run_id: str) -> bool:
        if self._cache is not None:
            return f"run:{run_id}" in self._cache
        return run_id in self._mem

    def evict(self, run_id: str) -> None:
        if self._cache is not None:
            self._cache.delete(f"run:{run_id}")
            index = [i for i in self._cache.get(_INDEX_KEY, []) if i != run_id]
            self._cache.set(_INDEX_KEY, index)
        else:
            self._mem.pop(run_id, None)

    def ids(self) -> list[str]:
        if self._cache is not None:
            return list(self._cache.get(_INDEX_KEY, []))
        return list(self._mem)
