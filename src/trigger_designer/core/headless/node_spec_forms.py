"""The ``FORM`` of every registered node, for ``node_spec.apply_form``.

This is the one module in the spec export that needs Qt: a node's ``FORM``
lives on its content class, next to the widgets. The registry holds lazy
references until a node module is imported, so reading every form loads every
node. ``ops --forms`` pays that cost and plain ``ops`` does not.
"""

from __future__ import annotations


def op_of_registered(family, code) -> str:
    from trigger_designer.core import node_configuration as nc

    return f"{family.value}.{nc._OPCODE_ENUMS[family](code).name.lower()}"


def registered_nodes() -> list[tuple[str, type]]:
    """``(op, node class)`` for every registered node, lazy ones loaded."""
    from trigger_designer.core import node_configuration as nc

    found = []
    for family, registry in nc.NODE_REGISTRIES.items():
        for code, cls in list(registry.items()):
            if isinstance(cls, nc.LazyNodeReference):
                cls = cls.load()
            found.append((op_of_registered(family, code), cls))
    return found


def load_forms() -> dict[str, tuple]:
    """``op -> FORM sections`` for each registered node that declares a form."""
    forms: dict[str, tuple] = {}
    for op, cls in registered_nodes():
        content_class = getattr(cls, "content_class", None)
        form = tuple(getattr(content_class, "FORM", ()) or ())
        if form:
            forms[op] = form
    return forms
