"""Which dragged things are workflow files (drag and drop to open, Qt only).

A ``.tds`` file dropped on the editor opens like File > Open. Only local
workflow files count: a web link, a folder, a data file or a file that no longer
exists is not opened, and the drop is refused so the pointer shows it.
"""

from __future__ import annotations

import os
from typing import Any

#: The file types a drop can open (the same as File > Open).
WORKFLOW_SUFFIXES = (".tds",)


def workflow_paths(mime: Any) -> list[str]:
    """The existing local workflow files in dragged ``mime`` data, in order.

    Paths are normalised and each file appears once.
    """
    if mime is None or not mime.hasUrls():
        return []
    paths: list[str] = []
    seen: set[str] = set()
    for url in mime.urls():
        if not url.isLocalFile():
            continue
        path = os.path.normpath(url.toLocalFile())
        if not path.lower().endswith(WORKFLOW_SUFFIXES) or not os.path.isfile(path):
            continue
        key = os.path.normcase(path)
        if key not in seen:
            seen.add(key)
            paths.append(path)
    return paths
