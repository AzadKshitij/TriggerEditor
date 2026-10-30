# Run history and the audit trail

Every time you press **Run**, the app writes a **run record**: a small file that says what ran, on which files, with which settings, and what came out. Records are numbered, linked to each other in a chain, and can be checked later. They contain **no data rows**.

This is the evidence trail for the work: "this workflow, in this state, ran on this file (this fingerprint) at this time, by this person, and produced these results".

[Back to the guide index](README.md)

## On this page

- [What a run record is](#what-a-run-record-is)
- [Where records are stored](#where-records-are-stored)
- [The Run History dock](#the-run-history-dock)
- [What each field means](#what-each-field-means)
- [The hash chain and tamper evidence](#the-hash-chain-and-tamper-evidence)
- [Row counting and the preferences that control it](#row-counting-and-the-preferences-that-control-it)
- [Audit-node test results in the record](#audit-node-test-results-in-the-record)
- [Example: a real record](#example-a-real-record)
- [If something goes wrong](#if-something-goes-wrong)

## What a run record is

One record is one JSON file, written when a Run ends, whether it completed, failed or was cancelled. A record holds:

- **who and when:** start and end time, user name and computer name (you can turn the names off),
- **what ran:** the workflow file's fingerprint, every node with its settings, the generated code (or at least its fingerprint),
- **on what:** every input file and output file with its size, modified time and **SHA-256 fingerprint**,
- **what happened:** each node's status, row counts in and out, column names and types, warnings, and the error of a failed node,
- **the result of any audit test** (Duplicates, Benford and so on),
- **its place in the chain:** its number, the previous record's hash, and its own hash.

A record is written once and never rewritten. The file is also marked read-only on disk.

A record is **not** a copy of your data: no rows, no cell values. It does contain what you typed into node settings (for example the text of a Filter condition or a Find and Replace rule), file paths, column names, and, for a failed node, the error with up to a few offending values unless you have turned on [hiding of data values](errors-and-problems.md#privacy-hiding-data-values-in-messages). See [Security and privacy](security-and-privacy.md).

You can switch recording off in Preferences (**Record every run**), but the default is on.

## Where records are stored

Each workflow has its own **store**, a folder of records.

| Situation | Store folder |
|---|---|
| Default, workflow saved on disk | Next to the workflow, in a folder named after it: for `C:\Work\Orders\orders_check.tds`, the folder `C:\Work\Orders\orders_check.runs\` |
| You set a **Run log folder** in Preferences | `<that folder>\<workflow name>-<8 characters>\` (the 8 characters come from the workflow's full path, so two workflows with the same name in different folders do not collide) |
| The workflow has never been saved | `%APPDATA%\Trigger Designer\runs\_unsaved\` (or `<Run log folder>\_unsaved\` if you set one) |
| The workflow's folder is read-only, or the store is locked | A fallback folder `%APPDATA%\Trigger Designer\runs\<workflow name>-<8 characters>\`, and the record carries a warning saying so |

Inside a store folder you will find:

| File | What it is |
|---|---|
| `<run id>.json` | One run record. The run id is 32 hex characters. |
| `index.jsonl` | One line per sealed record: its number, run id, start time, status and hashes. This is what the Run History list reads, so it opens fast. |
| `hash_cache.json` | A speed-up cache of file fingerprints. It is not part of the evidence; you may delete it. |
| `<run id>.started` | A marker that exists only while a Run is in progress. A marker that is left behind means the app or computer stopped during a Run. |
| `.lock` | Exists for moments while a record is being written. |

Records follow the **path** of the workflow. If you move or rename a workflow, its history stays behind in the old `.runs` folder and the next Run starts a new store. Move the `.runs` folder with it to keep one continuous history.

## The Run History dock

Open **Window > Run History**. It lists the runs of the workflow in front, from the primary store folder **and** from the fallback folder (used when the primary one was read-only), newest first. The status line says how many runs came from the fallback folder. The two folders keep separate chains, so run numbers can repeat; **Verify run log** checks both.

### The list

| Column | Meaning |
|---|---|
| # | Run number in this store (1, 2, 3...). The newest run is at the top. |
| Started | Local start time. |
| Status | `ok`, `failed` or `cancelled`. |
| Duration | Wall-clock time of the whole Run. |
| Nodes | Number of nodes in the run. |
| Rows out | Rows written to output files, when counted. |
| Chain | Empty until you press **Verify run log**; then `ok`, or the first kind of problem found for that run. |

The numbers in the last columns are loaded in the background for the 500 most recent runs.

When nothing is recorded yet, the dock says "No runs recorded yet".

### The toolbar

All buttons are icons; hover to read their tooltips.

| Button (tooltip) | What it does |
|---|---|
| Refresh run list | Reads the index again. |
| Verify run log | Checks the whole chain (see below). The status line then says "chain verified at HH:MM - head xxxxxxxx", or "chain verification FAILED (n)" and a dialog lists the problems. |
| Open run log folder | Opens the store folder in Explorer. |
| Check inputs against selected run | Re-fingerprints the input files recorded in the selected run and compares them with what the record says (see below). |
| Compare two selected runs | Select **exactly two** runs (click one, then `Ctrl`+click another), then press this toggle. The bottom-right table switches to differences. |
| Export selected run as JSON | Saves a copy of the record (file name `run-0001-xxxxxxxx.json`). |
| Export selected run as HTML report | Saves a self-contained web page with the summary, integrity details, inputs, outputs, steps, a **Tests** section (the result of each Audit node), errors, settings and generated code, and opens it. If you have verified the chain in this session, the report says whether it passed. The page embeds the record's JSON. |

### The panes under the list

- **Summary** for the selected run: run id, number, status, start and end, duration, workflow name and its fingerprint (or "unsaved"), a note when the workflow had unsaved changes at the time, how many inputs and outputs and whether they were all hashed, number of nodes (with failed and skipped counts), the row-count mode used, who ran it, program versions, how many inputs changed since the previous run, number of warnings and the start of the record hash.
- **Nodes** table, one row per node: Node, Operation, Status, In, Out, Cols, Time, Test, Problem. **Test** is filled for Audit nodes, for example `fail: 12 of 1,000 (1.2%)` (the node's `test_summary`); it is empty for other nodes.
- **Differences** table instead of Nodes when comparing: Kind, Node, Field, Old, New.

### Check inputs

The result dialog has one row per recorded input file:

| State | Meaning |
|---|---|
| unchanged | The file on disk has the same fingerprint as the one in the record. |
| MODIFIED | The file exists but differs from the record. Hover the row to see the recorded and the current fingerprint. |
| MISSING | The file is no longer where the record says. |
| not checked | The record has no fingerprint for it (hashing was off, or the file was above the size limit). |
| unreadable | The file could not be read. |

### Compare two runs

The differences that matter to a reviewer, in a fixed order:

| Kind | Examples |
|---|---|
| environment | The app, Polars, Python or DuckDB version changed. |
| input | An input file's fingerprint changed, or an input appeared or disappeared. |
| parameter | A node setting changed (the field is shown as `settings.<name>`). |
| row_count | A node produced a different number of rows. |
| status | A node's status changed. |
| output | An output file's fingerprint or row count changed. |
| node_set | A node was added or removed. |

Times, durations and run ids are never compared, so two runs of the same workflow on the same data show **no differences**.

## What each field means

### Run level

| Field | Meaning |
|---|---|
| `run_id` | Unique id of this run (32 hex characters). Also the file name. |
| `seq` | Number in the store's chain, starting at 1. |
| `status` | `ok`, `failed` or `cancelled`. |
| `started_at`, `finished_at`, `duration_s` | UTC times (ISO 8601, ending in `Z`) and the total in seconds. |
| `app_name`, `app_version`, `workflow_schema_version`, `python_version`, `polars_version`, `duckdb_version`, `os_name` | The environment. |
| `user`, `machine` | Who ran it and on what computer. Empty if you turned off **Record the user and machine name**. |
| `workflow_path` | Where the workflow was, or `null` if unsaved. |
| `workflow_sha256` | Fingerprint of the saved `.tds` file at the start of the Run. |
| `workflow_uuid` | The workflow's identity; it stays the same across saves and renames. |
| `graph_sha256` | Fingerprint of the nodes, settings and connections as they were in memory. It exists even for unsaved workflows. |
| `workflow_modified_since_save` | `true` if the window had unsaved changes: the file on disk is then not exactly what ran. Compare `graph_sha256`, not only the file hash. |
| `options` | The effective recording options and the row-count mode that was actually used. |
| `inputs`, `outputs` | File fingerprints (below). |
| `nodes` | One entry per node, in run order (below). |
| `baseline` | The previous run and the list of input files that changed since it. `null` on the first run. |
| `warnings` | Notes such as "run log stored in fallback folder" or an input that changed. |
| `generated_code`, `generated_code_sha256` | The Python code that ran, and its fingerprint. The text is left out if you turned off **Store the generated code**; the fingerprint is always there. |
| `schema_version`, `hash_algo` | Version of this record layout and of the hashing method. |
| `prev_record_hash`, `record_hash` | Chain links (below). |

### Each input and output file

| Field | Meaning |
|---|---|
| `role` | `input` or `output`. |
| `node_id` | The File Input or File Output node. |
| `path`, `sheet` | Where it is, and the Excel sheet when relevant. |
| `size_bytes`, `modified_time`, `mtime_ns` | Size and modified time at the moment it was read or written. |
| `sha256` | The file's SHA-256 fingerprint: change one byte and it changes completely. |
| `sha256_status` | `computed` (hashed now), `cached` (same size and modified time as an earlier hash), `skipped_size_limit` (above the size limit), `disabled` (switched off), `missing`, `error`, `cancelled`. |
| `row_count`, `row_count_method` | Rows in the file and how that was found (for example `materialized` for an input counted while reading, `output_file` for an output counted by reading it back). |

### Each node

| Field | Meaning |
|---|---|
| `node_id`, `op`, `title`, `label` | Which node. `op` is a stable name such as `audit.duplicates`. |
| `seq` | Its position in the run order. |
| `status` | `ok`, `failed` or `skipped`. |
| `started_at`, `duration_s`, `peak_memory_mb` | Timing and memory. `duration_s` is the node's wall time (code plus row counting). `peak_memory_mb` is empty (`null`): memory is not measured. Records written by earlier builds show `0` for both. |
| `settings` | The node's settings as they were. |
| `seed` | The random seed, for nodes that use one (Sample, Split). |
| `code_sha256` | Fingerprint of the node's generated code. |
| `rows_in` | For each input socket: the node it came from, the row count and the variable name. |
| `rows_out`, `columns_out`, `dtypes_out`, `count_method` | For each output: row count, column names and types, and how the count was obtained. Column lists are capped at 500. |
| `warnings` | Node-level warnings. |
| `error` | For a failed node: code, title, detail, hint, technical text (capped at 8,000 characters), and where known the row and values. |
| `test_summary` | The result of an audit test, or `null` (see below). |

A `status` of `ok` for an Audit node means that the **node ran**. Whether the audit **test** passed is in `test_summary.status`.

## The hash chain and tamper evidence

Each record carries two hashes:

- `record_hash`: a fingerprint of the whole record (with the `record_hash` field left out), made from a canonical form of the JSON so that spacing and key order cannot matter.
- `prev_record_hash`: the `record_hash` of the record before it (all zeros for run 1).

So each record "points at" the previous one. If anyone edits a record afterwards, its own hash no longer matches. If anyone deletes or swaps a record in the middle, the next record no longer points at what comes before it. **Verify run log** walks the whole store and reports:

| Problem | Meaning |
|---|---|
| `record_hash_mismatch` | A record was changed after it was written. |
| `prev_hash_mismatch` | A record does not follow the previous one in the chain. |
| `missing_record` | A record listed in the index is not on disk. |
| `index_mismatch` | A record does not match its line in the index. |
| `seq_gap` | A run number is skipped. |
| `schema_invalid` | A record is missing required fields or has wrong values. |
| `unreadable` | A record file cannot be read. |
| `index_corrupt` | The index is damaged, or records exist without an index. |

It also gives non-fatal warnings: an `orphan_record` (a record file that the index does not list), an `incomplete_run` (a `.started` marker with no record, meaning a run that never finished), a `clock_skew` and an unfinished last index line.

**What this does not protect against, and what to do about it:**

- **Removing the newest records.** If the last record or records, and their index lines, are deleted, what is left is still a perfectly valid chain. Verification cannot know they ever existed. After a significant Run, note the **head hash** shown after Verify ("head xxxxxxxx", full value in the report and the failure dialog) somewhere outside the folder: in your workpaper, an email, or the engagement file. Later, a verified chain whose head hash differs from your note, or that is shorter, has been truncated.
- **A determined rewrite.** The chain proves that records were not changed *piecemeal*. It is a fingerprint chain, not a digital signature. Someone with full write access who recomputes every hash can produce a different valid chain. Keep the store on a protected location, and keep the head hash elsewhere.
- **The files themselves.** Records say what the input fingerprint was. They cannot stop an input file being replaced afterwards. Use **Check inputs** to see that.

A verified chain means: "these records are exactly as written, in this order, with nothing missing before the last one I know of".

## Row counting and the preferences that control it

Counting rows costs time and memory, because a lazy node's result must be computed to know its size. You choose how much to count in **Edit > Settings > General > Audit trail**.

| Mode (**Row counts**) | What it does |
|---|---|
| **Auto** (default) | Looks at the combined size of all input files. If it is at most **Count every node up to (MB)** (default 256), behaves as "All nodes"; otherwise as "Sinks only". |
| **All nodes** | Every node's output is computed once and held in memory, so every node has exact row counts. Fastest overall for small data; needs memory for big data. |
| **Sinks only** | Nothing is held. Input files are counted with one cheap pass; outputs are counted by reading the written file. |
| **Off** | No row counts. |

The mode that was actually used is in `options.row_count_mode_effective` (and the Summary pane's "Row counts"); the one you asked for is in `row_count_mode_requested`.

All the Audit-trail preferences:

| Preference (Preferences label) | Default | Effect |
|---|---|---|
| Record every run (run history) | On | Off = no records at all. |
| Run log folder | empty (next to each workflow) | Keep every store under one folder instead. |
| Record the user and machine name | On | Off leaves `user` and `machine` empty. |
| Fingerprint input files (SHA-256) | On | Off sets `sha256_status` to `disabled`. |
| Fingerprint output files (SHA-256) | On | Same for outputs. |
| Skip hashing files above (MB) | 2048 | Larger files get `skipped_size_limit`. |
| Row counts | Auto | See above. |
| Count every node up to (MB) | 256 | The Auto threshold. |
| Store the generated code in each record | On | Off keeps only `generated_code_sha256`. |
| Warn when an input changed since the previous run | On | Adds a line to the Logs for each input file that changed. Never blocks a Run. |

Details of each are in [Preferences](preferences.md).

Hashing a large input takes time on every Run the first time; a repeat Run on an unchanged file reuses the earlier hash (`cached`) when the size and modified time are the same.

## Audit-node test results in the record

Audit nodes (Benford, Duplicates, Gaps, Risk Filters, Sample) do two things. They produce tables, and they produce a **test summary**: one structured result. In the record, the node's `test_summary` holds:

| Field | Meaning |
|---|---|
| `test_id`, `test_name` | For example `audit.duplicates#<node id>` and "Duplicates". |
| `status` | `pass`, `warn`, `fail` or `error`. |
| `population_rows`, `exception_rows`, `exception_rate` | How many rows were tested, how many were exceptions, and the proportion. |
| `population_value`, `exception_value` | The same in amount terms, when the test has an amount column. |
| `criteria` | The rule in plain words. |
| `parameters` | The settings used, so the result can be repeated. |
| `message` | The one-sentence outcome, as shown in the node's **Result** section. |
| `code` | `TD-AUDIT-101`, `-102` or `-103` when a warning applies. |
| `details` | Test-specific extras (for Duplicates: number of groups). |
| `exceptions_var` | The internal name of the exceptions table. |

The summary is recorded when the Run executes the node on the whole data. The sample-based number you see in a node while editing is not the one that is recorded.

The Run History dock shows the result in the **Test** column of the Nodes table, and the HTML report has a **Tests** section with the test name, result, population, exceptions, rate, criteria and message. The full summary is in the record itself (**Export selected run as JSON**).

## Example: a real record

This record was produced by running a small workflow: **File Input** (a 42-row orders file with two planted duplicate rows), **Normalize**, **Duplicates** (key column `Order_ID`), and two **File Output** nodes. It is trimmed: some nodes and files are replaced by a "..." line, and the user, machine and paths were replaced. The hashes, counts and times are real.

```json
{
  "app_name": "TriggerDesigner",
  "app_version": "0.1.0",
  "baseline": null,
  "duckdb_version": "2.0.0",
  "duration_s": 0.127313,
  "finished_at": "2026-10-30T16:53:47.749637Z",
  "generated_code": "import polars as pl\n... (the embedded script, trimmed)",
  "generated_code_sha256": "a72812e40e2a26d398071f6e2070a264cb801bebdf35dfe67c21f31aac5346b7",
  "graph_sha256": "c4b6ef82b83bb7e61f00eea41e06e0b404d653dd95714d66348e84e34a66bfd5",
  "hash_algo": "sha256-canonical-json-v1",
  "inputs": [
    {
      "error": null,
      "modified_time": "2026-10-30T16:53:47.236906Z",
      "mtime_ns": 1793379227236906100,
      "node_id": 1,
      "path": "C:/Work/Orders/orders.csv",
      "role": "input",
      "row_count": 42,
      "row_count_method": "materialized",
      "sha256": "09b697dafd5ccb54fa371158f7a3960bdae4066e69a9972aea8fb353a300cbfc",
      "sha256_status": "computed",
      "sheet": null,
      "size_bytes": 4715
    }
  ],
  "machine": "AUDIT-LT-07",
  "nodes": [
    "... four more nodes",
    {
      "code_sha256": "a6c9d463b88f0591ee013756268160253f5a8ec78b3337041df6918020854aa3",
      "count_method": {
        "var_dup_...": "materialized",
        "var_dupsum_...": "eager",
        "var_uniq_...": "materialized"
      },
      "duration_s": 0.0,
      "error": null,
      "node_id": 3,
      "op": "audit.duplicates",
      "rows_in": [
        {
          "from_node_id": 2,
          "from_socket": 0,
          "rows": 42,
          "socket": 0,
          "variable": "var_normalize_..."
        }
      ],
      "rows_out": {
        "var_dup_...": 4,
        "var_dupsum_...": 1,
        "var_uniq_...": 38
      },
      "seq": 2,
      "settings": {
        "ignore_case": false,
        "key_columns": [
          "Order_ID"
        ],
        "mode": "exact",
        "trim_text": true
      },
      "started_at": "2026-10-30T16:53:47.696313Z",
      "status": "ok",
      "test_summary": {
        "code": null,
        "criteria": "Rows with the same Order_ID are duplicates (spaces around text trimmed, case-sensitive).",
        "details": {
          "groups": 2,
          "skipped_rows": 0,
          "unparseable_rows": 0
        },
        "exception_rate": 0.09523809523809523,
        "exception_rows": 4,
        "exception_value": null,
        "exceptions_var": "var_dup_...",
        "message": "4 of 42 rows are in 2 duplicate groups.",
        "node_id": 3,
        "parameters": {
          "amount_column": "",
          "date_column": "",
          "date_format": "%Y-%m-%d",
          "ignore_case": false,
          "key_columns": [
            "Order_ID"
          ],
          "mode": "exact",
          "tolerance": 0.0,
          "tolerance_kind": "absolute",
          "trim_text": true,
          "value_column": "",
          "window_days": 0
        },
        "population_rows": 42,
        "population_value": null,
        "status": "fail",
        "test_id": "audit.duplicates#3",
        "test_name": "Duplicates"
      },
      "title": "Duplicates",
      "warnings": []
    }
  ],
  "options": {
    "embed_code": true,
    "exact_counts_max_mb": 256,
    "hash_inputs": true,
    "hash_max_mb": 2048,
    "hash_outputs": true,
    "record_identity": true,
    "row_count_mode_effective": "all",
    "row_count_mode_requested": "auto",
    "total_input_bytes": 4715
  },
  "os_name": "Windows-11-10.0.26100-SP0",
  "outputs": [
    "... one of two output files shown",
    {
      "error": null,
      "modified_time": "2026-10-30T16:53:47.732486Z",
      "mtime_ns": 1793379227732486300,
      "node_id": 5,
      "path": "C:/Work/Orders/out/summary.csv",
      "role": "output",
      "row_count": 1,
      "row_count_method": "output_file",
      "sha256": "bb280bc1c01be23c9cf52a56fb2b09df44d7db97e06801556625235707de0281",
      "sha256_status": "computed",
      "sheet": null,
      "size_bytes": 626
    }
  ],
  "polars_version": "2.0.0",
  "prev_record_hash": "0000000000000000000000000000000000000000000000000000000000000000",
  "python_version": "3.14.8",
  "record_hash": "8921ad22afaa149980133ca0b288a27b9503eadf63d73f893eff884b8570ade8",
  "run_id": "0aa46878f0d745179ef7d2d74f55bf03",
  "schema_version": 1,
  "seq": 1,
  "started_at": "2026-10-30T16:53:47.622353Z",
  "status": "ok",
  "user": "jsmith",
  "warnings": [],
  "workflow_modified_since_save": false,
  "workflow_path": "C:/Work/Orders/orders_check.tds",
  "workflow_schema_version": 2,
  "workflow_sha256": "9601e741b1760ca971e140b916b0e75c1542a07819824b37862cdd7b29ea30a1",
  "workflow_uuid": "b591d0f6-4a82-4eb7-961a-9f9b789262c1"
}
```

Read it like this:

- `status: "ok"`, `seq: 1`, and `prev_record_hash` all zeros: this is the first record in the chain.
- The input has a `sha256` and 42 rows. The Duplicates node's `test_summary.status` is `"fail"` because 4 of 42 rows are in 2 duplicate groups, while the node itself ran fine (`"status": "ok"`).
- `baseline` is `null`: there was no earlier run to compare with.
- `row_count_mode_effective: "all"`: the input was far below the 256 MB threshold, so every node was counted.
- `duration_s: 0.0` for the node is the known limitation noted above.

## If something goes wrong

| Symptom | What to do |
|---|---|
| "No runs recorded yet" after a Run | Recording is off (check **Record every run**), the workflow was moved since (its history is in the old `.runs` folder), or the record went to the fallback folder. Look at the Logs for "Run log saved: <path>". |
| The Logs say "The run log could not be saved" | The run itself was not affected. Check disk space and whether you may write to the workflow's folder, or set a **Run log folder** you own. |
| Verification FAILED | Read the dialog. `record_hash_mismatch` or `prev_hash_mismatch` mean files were edited or replaced. Keep the folder as it is and tell the engagement lead; do not delete anything. |
| Verification reports `incomplete_run` | A Run was interrupted (crash, power loss). It is a note, not tampering. |
| "chain not verified" in the status line | You have not pressed Verify in this session. |
| Check inputs says MODIFIED | The input file changed after the Run. Either that was intended (a refreshed extract) or the file was replaced; compare with the HTML report's fingerprint. |
| Compare is greyed out | Select exactly two runs. |
| An export fails | The status line says "Export failed: ..." and gives the reason, usually a locked or read-only target. |
| Run times in the Nodes table are all 0 ms | Known: per-node timing is not recorded yet. The run total is correct. |
