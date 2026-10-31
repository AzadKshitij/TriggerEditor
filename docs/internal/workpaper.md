# Audit workpapers (Excel)

This page has moved. The documentation of the Excel workpaper is now in two pages:

| For | Read |
|---|---|
| Auditors and analysts: what a workpaper is, the Workpaper Output node and its settings, File > Export Workpaper..., the sheets, versions, formula protection, Excel limits, the audit trail, the command line, a worked example | [guide/workpaper.md](guide/workpaper.md) |
| Developers: module map, data flow, streaming in 50,000-row batches, the run-record provider, the generated-code contract, headless use, tests and benchmarks, how to add a sheet | [dev/workpaper-internals.md](dev/workpaper-internals.md) |

The node's reference entry is in [guide/nodes/input-output.md](guide/nodes/input-output.md#workpaper-output).
The feature plan (background only) is [plan/06-workpaper-export.md](plan/06-workpaper-export.md).

This file is kept as a pointer because the docstring of `src/trigger_designer/core/workpaper/writer.py`
still names it.
