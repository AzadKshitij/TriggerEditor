"""Trigger Designer."""

import os

# Polars and Arrow carry their own mimalloc allocator. By default it keeps freed
# memory for a while instead of handing it back to Windows, and an idle worker
# thread never gets the chance to release it, so after a run the process sits at
# about twice what it really uses. Return freed memory at once.
#
# This must be set before polars is imported, which is why it lives here: every
# entry point (editor, ``tds``, the MCP server) imports this package first. A
# value already present in the environment wins.
os.environ.setdefault("MIMALLOC_PURGE_DELAY", "0")
