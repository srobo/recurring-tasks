import contextlib
import json
from pathlib import Path
from types import TracebackType
from typing import (
    Callable,
    Dict,
    Iterator,
    MutableMapping,
    Optional,
    Set,
    Type,
)


class ElementsCache:
    """
    Load and cache the tasks that have been created in a file.

    Use like:
    ```
    with ElementsCache(Path('cache.json')) as elements:
        elements['key'] = 14
    """

    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self.elements: Dict[str, int] = {}

        try:
            self.elements = json.loads(cache_path.read_text())
        except IOError:
            pass

    def __enter__(self) -> MutableMapping[str, int]:
        return self.elements

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.cache_path.write_text(json.dumps(self.elements, sort_keys=True, indent=2))


class ElementsInProgress:
    """
    Keep track of the tasks as they're being imported.

    This checks for cyclic dependencies and provides a way to consume existing
    mappings of tasks that are known to be equivalent to those in this repo.
    """

    def __init__(self, known_elements: MutableMapping[str, int]) -> None:
        # Note: it's important that we use the mapping the user passes in so
        # that they can pass an object that will keep track of the elements that
        # have been processed (either a `shelve` or the mapping yielded by an
        # `ElementsCache` instance work well).
        self.known_elements = known_elements
        self._current: Set[str] = set()

    def get(self, key: str) -> Optional[int]:
        if key in self._current:
            raise RuntimeError(f"Cyclic dependency on {key}")

        return self.known_elements.get(key)

    @contextlib.contextmanager
    def process(self, key: str) -> Iterator[Callable[[int], None]]:
        if key in self._current:
            raise RuntimeError(
                f"Re-entrant processing not supported (attempted {key})",
            )

        def done(x: int) -> None:
            self.known_elements[key] = x

        self._current.add(key)
        try:
            yield done
        finally:
            self._current.remove(key)
