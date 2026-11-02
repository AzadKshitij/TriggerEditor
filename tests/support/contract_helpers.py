"""Shared contract helpers for the audit-node test modules.

These cover only the contract *every* audit node shares:

* the live outputs agree with the executed generated code, and
* feeding the summary output back through ``content.after_execution`` builds
  the ``TestSummary``.

Everything node-specific (output counts, summary values, which fields a
round-trip must preserve) stays in the node's own test module and keeps its
own assertions. A helper that hard-codes one node's shape silently weakens
the other four.
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl


def live_value_and_generated_code_agree(
    node, source
) -> tuple[list[pl.DataFrame], dict]:
    """Assert ``node.value`` agrees with the executed generated code.

    Returns the collected live frames and the execution namespace so the
    caller can add node-specific assertions (heights, columns, summary rows,
    which outputs are eagerly collected).
    """
    out = node.value
    live = [
        o["data"].collect() if isinstance(o["data"], pl.LazyFrame) else o["data"]
        for o in out
    ]
    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(out, live):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    return live, namespace


def run_after_execution(content, node, output_index: int = -1):
    """Feed one of the node's outputs back through ``after_execution``.

    Collects ``node.value[output_index]`` and hands it to the content under
    the content's own summary variable name — the same call the run pipeline
    makes. Returns ``content.test_summary`` for the caller to assert on.
    """
    frame = node.value[output_index]["data"].collect()
    content.after_execution({content.summary_variable_name: frame})
    return content.test_summary


def round_trip_settings(
    content,
    fresh_content: Callable[[], object],
    **fields,
) -> tuple[dict, object]:
    """Set ``fields`` on ``content``, serialize, restore into a fresh content.

    Returns the serialized dict and the restored content. The caller keeps
    the node-specific assertions (which serialized values must appear, that
    an empty dict falls back to defaults, list-independence, ...).
    """
    for name, value in fields.items():
        setattr(content, name, value)
    data = content.serialize()
    other = fresh_content()
    other.deserialize(dict(data))
    return data, other
