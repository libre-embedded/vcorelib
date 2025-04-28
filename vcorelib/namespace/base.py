"""
A module implementing a base namespace interface.
"""

# built-in
from contextlib import contextmanager as _contextmanager
from re import compile as _compile
from typing import Iterator as _Iterator
from typing import Optional as _Optional

DEFAULT_DELIM = "."
CPP_DELIM = "::"


class Namespace:
    """A class for implementing a basic namespace interface."""

    def __init__(
        self,
        *names: str,
        delim: str = DEFAULT_DELIM,
        parent: "Namespace" = None,
    ) -> None:
        """Initialize this namespace."""

        self.stack: list[str] = [*names]
        self.names: set[str] = set()
        self.delim = delim
        self.parent: _Optional["Namespace"] = parent

        # Use this attribute from preventing this namespace from colliding with
        # its parent namespace.
        self.root_size = len(self.stack)

    def child(self, *names: str) -> "Namespace":
        """Create a child namespace from this one."""
        return Namespace(*self.stack, *names, delim=self.delim, parent=self)

    def suggestions(self, data: str, delta: bool = True) -> _Iterator[str]:
        """
        Iterate over un-ordered suggestions for a data string that is a
        sub-string of one or more names in this namespace.
        """

        data_length = len(data)

        for name in self.names:
            if name.startswith(data):
                found = name
                if delta:
                    found = found[data_length:]
                if found:
                    yield found

    def length_sorted_suggestions(
        self, data: str, delta: bool = True
    ) -> list[str]:
        """Get suggestions (based on data) sorted by length."""
        return sorted(set(self.suggestions(data, delta=delta)), key=len)

    def suggest(self, data: str, delta: bool = True) -> _Optional[str]:
        """Find the shortest name suggestion."""

        if data in self.names:
            return None if delta else data

        result = None

        suggestions = self.length_sorted_suggestions(data, delta=delta)
        if suggestions and suggestions[0]:
            result = suggestions[0]

        return result

    def push(self, name: str) -> None:
        """Push a name onto the stack."""
        self.stack.append(name)

    def pop(self, name: str = None) -> str:
        """Pop the latest name off the stack."""

        # Ensure that the namespace can't be traversed beyond its
        # initialization path.
        curr_size = len(self.stack)
        if curr_size <= self.root_size:
            raise IndexError(
                (
                    f"Root namespace has {self.root_size} and this "
                    f"namespace currently has {curr_size}!"
                )
            )

        val = self.stack.pop()

        assert (
            val == name if name is not None else True
        ), f"'{val}' != '{name}'!"
        return val

    @_contextmanager
    def pushed(self, *names: str) -> _Iterator[None]:
        """
        Provide this namespace with some names pushed onto the stack as a
        context.
        """

        to_push = [*names]
        for name in to_push:
            self.push(name)

        yield

        for name in reversed(to_push):
            self.pop(name=name)

    def namespace(
        self, name: str = None, delim: str = None, track: bool = True
    ) -> str:
        """
        Get the current namespace string with or without an additional name
        applied.
        """
        if delim is None:
            delim = self.delim

        # Skip empty names.
        result = delim.join(x for x in self.stack if x)

        if name is not None:
            if result:
                result += delim
            result += name

        # Keep track of all names added to this namespace.
        if track:
            self.names.add(result)
        return result

    @property
    def parents(self) -> _Iterator["Namespace"]:
        """Iterate over parents."""

        curr: _Optional["Namespace"] = self
        while curr is not None:
            if curr.parent is not None:
                yield curr.parent
            curr = curr.parent

    def search(
        self,
        *names: str,
        pattern: str = ".*",
        recursive: bool = True,
        exact: bool = False,
    ) -> _Iterator[str]:
        """
        Iterate over names in this namespace that match a given pattern.
        """

        to_search = [self]

        if recursive:
            to_search.extend(list(self.parents))

        seen = set()
        while to_search:
            current = to_search.pop()

            # Push provided names onto the stack while yielding matches.
            with current.pushed(*names):
                start = current.namespace(track=False)

                # Add a trailing delimeter if we land on a non-empty name. Also
                # enforce that the namespaced portion is at the beginning.
                if start:
                    start = "^" + start + current.delim

                # Ensure that dots are escaped to match literally.
                if start and current.delim == ".":
                    start = start.replace(".", "\\.")

                # Allow the provided search string to appear anywhere in the
                # name.
                if start and not exact:
                    start += ".*"

                compiled = _compile(start + pattern)
                for name in current.names:
                    if name not in seen and compiled.search(name) is not None:
                        seen.add(name)
                        if not exact or name == pattern:
                            yield name
