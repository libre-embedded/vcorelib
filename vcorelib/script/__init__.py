"""
A module for working with external scripts.
"""

# built-in
import importlib.machinery
import importlib.util
from pathlib import Path as _Path
from sys import path as _path
from typing import Any as _Any

# internal
from vcorelib.paths import Pathlike as _Pathlike
from vcorelib.paths import normalize as _normalize


def invoke_script(script: _Pathlike, method: str, *args, **kwargs) -> _Any:
    """Invoke a method from an external script."""

    path = _normalize(script)

    # Add the parent directory to the system path so that the external script
    # can load adjacent modules.
    parent = str(path.parent.resolve())
    if parent not in _path:
        _path.append(parent)

    loader = importlib.machinery.SourceFileLoader("script", str(path))
    spec = importlib.util.spec_from_loader("script", loader)
    assert spec is not None
    script_module = importlib.util.module_from_spec(spec)
    loader.exec_module(script_module)

    # Invoke the script method.
    return getattr(script_module, method)(*args, **kwargs)


class ScriptableMixin:
    """
    A mixin for classes to pass themselves to external scripts that may
    update their state.
    """

    def __init__(self) -> None:
        """Initialize this scriptable object."""
        self._invoked: set[_Path] = set()

    def script(
        self, script: _Path, method: str, *args, once: bool = True, **kwargs
    ) -> _Any:
        """Invoke a script while passing this object reference."""
        if once:
            assert script not in self._invoked, f"Already invoked '{script}'!"
            self._invoked.add(script)
        return invoke_script(script, method, self, *args, **kwargs)

    def invoked(self, script: _Path) -> bool:
        """Determine if a script has been invoked or not."""
        return script in self._invoked
