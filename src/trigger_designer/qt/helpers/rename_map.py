"""Rename maps advertised by upstream content widgets."""

from __future__ import annotations


def upstream_rename_map(upstream_node) -> dict:
    """Column renames advertised by an upstream node (``{old: new}``).

    Lets a downstream node follow a rename instead of treating it as a
    drop + add: a config referencing ``old`` can be remapped to ``new``
    when ``new`` is present in the live upstream schema. Nodes that do
    not rename report ``{}``.
    """
    content = getattr(upstream_node, "content", None)
    if content is None:
        return {}
    # New Select stores its renames in settings["columns"].
    settings = getattr(content, "settings", None)
    if isinstance(settings, dict):
        columns = settings.get("columns")
        if isinstance(columns, list):
            mapping = {
                str(column.get("name")): str(column.get("rename"))
                for column in columns
                if isinstance(column, dict)
                and column.get("rename")
                and column.get("rename") != column.get("name")
            }
            if mapping:
                return mapping
    # Old Select stored its renames in ``changes["rename_mapping"]``.
    changes = getattr(content, "changes", None)
    if isinstance(changes, dict):
        mapping = changes.get("rename_mapping")
        if isinstance(mapping, dict):
            return {str(old): str(new) for old, new in mapping.items() if new}
    # Normalize derives its mapping from its rules.
    current_mapping = getattr(content, "_current_mapping", None)
    if callable(current_mapping):
        try:
            mapping = current_mapping()
        except Exception:  # noqa: BLE001 - any upstream error means no map
            return {}
        if isinstance(mapping, dict):
            return {str(old): str(new) for old, new in mapping.items() if new}
    return {}
