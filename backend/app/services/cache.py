"""Local TTL cache for scholarly paper search responses."""

from collections import OrderedDict
import json
import logging
from pathlib import Path
import time

from app.config import CACHE_FILE_PATH, CACHE_MAX_ENTRIES, CACHE_TTL_SECONDS
from app.schemas import Paper

logger = logging.getLogger(__name__)


class SearchCache:
    """Bounded TTL cache for normalized Paper lists with optional local JSON file persistence."""

    def __init__(
        self,
        *,
        ttl_seconds: int = CACHE_TTL_SECONDS,
        max_entries: int = CACHE_MAX_ENTRIES,
        cache_file_path: Path | None = CACHE_FILE_PATH,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._cache_file_path = cache_file_path
        self._store: OrderedDict[str, tuple[float, list[Paper]]] = OrderedDict()
        if self._cache_file_path is not None:
            self._load_from_disk()

    @staticmethod
    def make_key(query: str, limit: int) -> str:
        """Create a normalized cache key for a query and result limit."""
        normalized_query = " ".join(query.strip().lower().split())
        return f"{normalized_query}::{limit}"

    def get(self, query: str, limit: int) -> list[Paper] | None:
        """Retrieve cached Paper list if present and not expired."""
        key = self.make_key(query, limit)
        entry = self._store.get(key)
        if entry is None:
            return None

        expires_at, papers = entry
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None

        self._store.move_to_end(key)
        return [paper.model_copy(deep=True) for paper in papers]

    def set(self, query: str, limit: int, papers: list[Paper]) -> None:
        """Cache a list of normalized Paper objects for the given query and limit."""
        key = self.make_key(query, limit)
        expires_at = time.time() + self._ttl_seconds
        self._store[key] = (expires_at, [paper.model_copy(deep=True) for paper in papers])
        self._store.move_to_end(key)

        while len(self._store) > self._max_entries:
            self._store.popitem(last=False)

        if self._cache_file_path is not None:
            self._save_to_disk()

    def clear(self) -> None:
        """Clear all in-memory and persisted cache entries."""
        self._store.clear()
        if self._cache_file_path is not None and self._cache_file_path.exists():
            try:
                self._cache_file_path.unlink()
            except OSError as exc:
                logger.warning("Failed to remove local cache file: %s", type(exc).__name__)

    def _load_from_disk(self) -> None:
        """Load unexpired cache entries from disk if the cache file exists."""
        if self._cache_file_path is None or not self._cache_file_path.exists():
            return

        try:
            raw_text = self._cache_file_path.read_text(encoding="utf-8")
            raw_data = json.loads(raw_text)
            if not isinstance(raw_data, dict):
                return

            now = time.time()
            for key, value in raw_data.items():
                if not isinstance(key, str) or not isinstance(value, dict):
                    continue
                expires_at = value.get("expires_at")
                items = value.get("results")
                if not isinstance(expires_at, (int, float)) or expires_at <= now:
                    continue
                if not isinstance(items, list):
                    continue
                papers = [Paper.model_validate(item) for item in items if isinstance(item, dict)]
                self._store[key] = (float(expires_at), papers)
        except (OSError, ValueError) as exc:
            logger.warning("Could not load local search cache: %s", type(exc).__name__)

    def _save_to_disk(self) -> None:
        """Persist current cache entries to disk safely."""
        if self._cache_file_path is None:
            return

        try:
            self._cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            serializable = {
                key: {
                    "expires_at": expires_at,
                    "results": [paper.model_dump() for paper in papers],
                }
                for key, (expires_at, papers) in self._store.items()
            }
            self._cache_file_path.write_text(
                json.dumps(serializable, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("Could not persist local search cache: %s", type(exc).__name__)
