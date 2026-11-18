"""Import a heavy library when it is first used, not when a module is imported.

Polars alone takes about half a second to import and DuckDB adds more. The
editor imports a lot of modules before its first window, and several of them
only mention a library inside functions that run long after the window is up.
Binding the name to a :class:`LazyModule` keeps those modules' code unchanged
while moving the import off the startup path::

    if TYPE_CHECKING:
        import polars as pl
    else:
        pl = lazy_module("polars")

Type checkers see the real module; at run time the first attribute access
imports it. Hints written as ``pl.DataFrame`` must be strings (put
``from __future__ import annotations`` at the top of the module), and module
level code must not touch the library, or the import happens right there.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import Any

#: Names Python's own protocols (copy, pickle, introspection) probe for. Answering
#: them with an import would load the library for nothing, and answering them
#: with the real module's values would be wrong for a stand-in object.
_PROTOCOL_NAMES = frozenset(
    {
        "__wrapped__",
        "__getstate__",
        "__setstate__",
        "__copy__",
        "__deepcopy__",
        "__reduce__",
        "__reduce_ex__",
        "__class_getitem__",
        "__iter__",
        "__len__",
    }
)


class LazyModule:
    """A stand-in for a module that is imported on first attribute access."""

    def __init__(self, name: str) -> None:
        self.__dict__["_lazy_name"] = name
        self.__dict__["_lazy_module"] = None

    def _lazy_load(self) -> ModuleType:
        module = self.__dict__["_lazy_module"]
        if module is None:
            module = importlib.import_module(self.__dict__["_lazy_name"])
            self.__dict__["_lazy_module"] = module
        return module

    def __getattr__(self, attr: str) -> Any:
        # Only reached for names not already cached on the instance.
        if attr in _PROTOCOL_NAMES:
            raise AttributeError(attr)
        value = getattr(self._lazy_load(), attr)
        # Cache it: every later lookup is a plain instance attribute read, so a
        # hot loop calling ``pl.col`` pays nothing for the indirection.
        self.__dict__[attr] = value
        return value

    def __dir__(self) -> list[str]:
        return dir(self._lazy_load())

    def __repr__(self) -> str:
        state = "loaded" if self.__dict__["_lazy_module"] is not None else "not loaded"
        return f"<lazy module {self.__dict__['_lazy_name']!r} ({state})>"


def lazy_module(name: str) -> LazyModule:
    """A :class:`LazyModule` for ``name``; nothing is imported yet."""
    return LazyModule(name)
