"""An in-process least-recently-used cache.

Each worker process has its own. That is only safe for data that never changes:
nothing tells the other workers when an entry is out of date.
"""

import threading
from collections import OrderedDict

from prometheus_client import Counter

LOOKUPS = Counter(
    "read_cache_lookups_total", "Read cache lookups, by result", ["result"]
)


class LRUCache:
    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self._entries: OrderedDict[str, str] = OrderedDict()
        # Sync routes run on a thread pool, and a lookup also reorders entries
        self._lock = threading.Lock()

    def get(self, key: str) -> str | None:
        if not self.maxsize:
            return None
        with self._lock:
            value = self._entries.get(key)
            if value is not None:
                self._entries.move_to_end(key)
        LOOKUPS.labels(result="miss" if value is None else "hit").inc()
        return value

    def put(self, key: str, value: str) -> None:
        if not self.maxsize:
            return
        with self._lock:
            self._entries[key] = value
            self._entries.move_to_end(key)
            if len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)
