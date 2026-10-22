"""Thread-safe in-memory cache with expiry, so repeated checks of the same forward are instant
and don't use AI quota. Nothing is written to disk."""
import hashlib
import re
import threading
import time
from collections import OrderedDict


class TTLCache:
    def __init__(self, ttl_seconds: int, max_items: int):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key_for(text: str) -> str:
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get(self, key: str):
        with self._lock:
            item = self._data.get(key)
            if not item:
                return None
            expires, value = item
            if expires < time.time():
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value) -> None:
        if self.ttl <= 0 or self.max_items <= 0:
            return
        with self._lock:
            self._data[key] = (time.time() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)
