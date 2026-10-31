# Internal documentation

Nothing in this folder is published. `mkdocs.yml` excludes `docs/internal/` from
the site, so these notes are for maintainers only.

| Folder or file | What it is |
|---|---|
| `legacy-guide-nodes/` | The original family-based node guide, archived when the site moved to one page per node. The content was split into `docs/nodes/<family>/`, but these copies are kept unchanged so nothing was lost. |
| `legacy-assets/` | Images that used to sit in `docs/assets/` and are no longer referenced by a published page. |
| `audit-nodes.md` | The older audit guide, superseded by `docs/nodes/audit/`. |
| `nodes-plan.md` | The earlier lazy-processing plan for nodes. |
| `NODE_REFERENCE.md` | A stale palette inventory, kept for reference. It predates the current node set; do not treat it as accurate. |
| `dev/` | Engineering notes: architecture, conventions, error system, internals. |
| `plan/` | Historical implementation plans. |
| Everything else | Reports, changelogs and design notes moved out of `docs/` so the published tree stays user-facing. |

## Why keep them

They record how the app works internally and why decisions were made. A reader of
the published site never needs them, and some of them are out of date. Keeping
them in a separate, excluded folder means the published tree stays clean without
losing the history.
