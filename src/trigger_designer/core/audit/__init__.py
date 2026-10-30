"""Qt-free audit tests (docs/plan/04-audit-test-nodes.md).

Each test is one pure function ``run_<name>(frame, params) -> AuditResult`` in its
own module; ``common`` holds the shared parameter, validation and summary
building blocks and ``test_summary`` the record other features read.

Nothing is imported here on purpose: importing the package must stay free, and
the modules may only depend on the standard library, polars and numpy (a unit
test fails if one imports Qt).
"""
