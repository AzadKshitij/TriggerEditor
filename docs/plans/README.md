# Bug and evaluation plans

Planning documents from the bug-hunt passes. Each plan lists reproducible
findings with file and line references, a suggested fix, and the tests that
should pin the fix. They are proposals: no source files were changed when they
were written.

| Date | Plan | Scope | Findings |
|---|---|---|---|
| 2026-10-31 | [Trigger Designer bug hunt](2026-10-31-trigger-designer-bug-hunt.md) | Core shaping, audit, workpaper, input/output, Qt models, undo, CLI | 4 High, 10 Medium, 6 Low |
| 2026-11-01 | [Node evaluation and LazyFrame](2026-11-01-node-evaluation-and-laziness.md) | Config Dock apply timing, audit deferral, SQL focus-out, lazy-first execution | 10-step implementation plan |
| 2026-11-04 | [Second-pass bug hunt](2026-11-04-second-pass-bug-hunt.md) | Join, SQL rewriting, input discovery, headless CLI, layout persistence | 4 High, 6 Medium, 8 Low |

The 2026-11-04 plan is the companion to the first pass and covers areas the
first pass did not. The 2026-11-01 plan is separate: it tracks evaluation
timing and LazyFrame compliance rather than individual defects.

## Fix order

1. Make the unit suite green (first plan, H4).
2. Fix data-correctness defects with the largest blast radius (first plan H1,
   H2; second pass H1).
3. Fix silent data loss and crashes (second pass H2-H4, M1).
4. Fix the remaining Medium findings.
5. Treat the Low findings as cleanup, with a regression test for every High and
   Medium fix.

Keep data-parsing changes, Qt model/UI changes, and audit-store changes in
separate commits so each can be reviewed and reverted alone.
