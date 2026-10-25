# Alpha dependency modernization — progress record

Branch `alpha/deps-modernization`, from `main` @ `8e557fc` (identical to
`origin/main` as of 2026-10-25). Plan: 10 phases (0–9), one commit per phase,
no push. Phases 1–5 (the measured upgrade) execute first; phases 6–9 follow.

## Machine + session state (every comparison must match this)

| | |
|---|---|
| Date | 2026-10-25 (all Phase 0 runs, same session) |
| CPU | AMD Ryzen 5 3500U (4c/8t, 2.1 GHz base) — budget laptop |
| RAM | 9.9 GB |
| OS | Windows 11 x64 |
| Python (pre) | 3.13.12 (uv managed); 3.14.8 installed via uv 0.13.4, ready for Phase 1 |
| uv | 0.13.4 (7456b60bc 2026-10-20) |
| Other load | OpenChamber + this session running; no other heavy process during measurement |

## Noise band (the number that gates every later claim)

`docs/PERFORMANCE_PROFILING_FINDINGS.md` warns ±10–25%. Measured today with a
same-tree, same-session baseline+after pair (5 runs each, fixed path-remap
harness — see below):

| workflow | baseline avg | after avg | same-tree speedup |
|---|---|---|---|
| small_2node | 0.006 s | 0.006 s | 1.00x |
| medium_14node | 0.059 s | 0.056 s | 1.06x |
| large_105node | 5.201 s | 4.868 s | 1.07x |

**Rule adopted:** post-upgrade deltas below ~7% on `large_105node`, ~10% on
`medium_14node`, or any delta on sub-10 ms workloads are reported as
*within noise*, never as wins. Per-run spread on `small_2node` (0.004–0.011 s)
is timer-dominated; only its mean-to-mean is meaningful.

Pre-upgrade artefacts (all committed):
`scripts/benchmark_results/pre_deps_baseline.json`, `pre_deps_after.json`,
`canvas_deps_baseline_20261025_193404.json`.

Canvas key medians (120 nodes, 119 edges, repeats=3, defaults):
zoomed-out pan 35.15 ms/step, viewport repaint 42.18 ms, node drag 14.16 ms/
step; full table in the JSON. Post-upgrade canvas run must use the identical
command and be compared with
`benchmark_canvas_perf.py --compare <pre> <post>`.

## Phase 0 — Baseline — DONE 2026-10-25

1. Tree synced: `alpha/deps-modernization` reset --hard to `origin/main`;
   uncommitted app-resave churn in `savedfiles/*.tds` discarded (approved).
2. **Measurement fix (committed `c09c635`):** the committed sample workflows
   bake the authoring machine's absolute paths
   (`C:/Users/KASHVINCHANDRASAN/...`, `docs/bugs.md` documents 16 files).
   Before this fix the benchmark measured **failures**: `large_105node` ran
   29 nodes in 0.08 s (File Inputs gave up after 5 retries → "no incoming
   data"), and `small_2node`'s 1.01 s `last_execution_time` was the retry
   sleep against a missing `check.csv`. Harness now localizes paths in a
   scratch copy (foreign repo-root rewrite + repo-root basename→`data/`
   fallback, same idea as `tests/support/corpus.py`); saved workflows are
   never touched. Verified: 105/105 nodes, 4.9–5.5 s, +667 MB first-run RSS.
3. Workflow pair + `--compare` captured (numbers above).
4. Canvas `--label deps_baseline` captured (defaults; JSON committed).
5. This doc committed.

Session profile (`profile_app.py`, plan Phase 0 step 3) is **deferred**: it
needs an interactive app close (or the Phase 8 `--profile-seconds` flag that
does not exist yet); cProfile data across the upgrade without an automated
diff is noise we do not need twice. Phase 8 captures profile evidence
properly, before and after, with the self-exit flag.

## Phase 1 — Python 3.14 — pending

## Phase 2 — Unused runtime deps — pending

## Phase 3 — Dev deps cleanup (pandas→polars etc.) — pending

## Phase 4 — Clean-venv proof + nodeeditor 0.8.2 — pending

## Phase 5 — Remaining bumps + duckdb <2 cap + version 0.1.0 — pending

## Post-upgrade measurement — pending

(Sections above get their numbers filled in as each phase lands.)
