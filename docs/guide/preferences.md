# Preferences

Preferences are the settings that belong to **you and your computer**, not to a workflow: theme, font size, canvas behaviour, how errors are shown, and how run records are kept. They are stored in one file and apply to every workflow you open.

[Back to the guide index](README.md)

## On this page

- [Open the Preferences window](#open-the-preferences-window)
- [How changes take effect](#how-changes-take-effect)
- [Appearance](#appearance)
- [Layout](#layout)
- [Editor](#editor)
- [Node Editor](#node-editor)
- [Shortcuts](#shortcuts)
- [General](#general)
- [Complete list of stored preferences](#complete-list-of-stored-preferences)
- [Where preferences are stored and how to reset them](#where-preferences-are-stored-and-how-to-reset-them)
- [If something goes wrong](#if-something-goes-wrong)

## Open the Preferences window

Choose **Edit > Settings**. The window is titled **Preferences** and has six pages in a list on the left: **Appearance**, **Layout**, **Editor**, **Node Editor**, **Shortcuts** and **General**. The buttons at the bottom are **Cancel**, **Apply** and **OK**.

## How changes take effect

| Kind of setting | Behaviour |
|---|---|
| **Theme** | Previewed as you click. **Apply** keeps it and leaves the window open, **OK** keeps it and closes, **Cancel** goes back to the theme you had. |
| **Accent colour and font size** | Applied as you change them. **Cancel** restores the values you had when you opened the window. |
| **Everything else** (check boxes, numbers, paths, colours of nodes) | Saved **the moment you change them**. Cancel does not undo these. |
| **Shortcuts** | Validated when you press **OK**; if one is invalid the window stays open and says why. |

The values are read each time they are needed: error settings take effect on the next error, audit settings on the next Run.

## Appearance

| Setting | Default | Meaning |
|---|---|---|
| Theme | Dark | The colour scheme. **System - follow Windows appearance** switches between a light and a dark theme with Windows. Built in: Dark, Light, Catppuccin Latte, Catppuccin Mocha, Dracula, Gruvbox Dark, Gruvbox Light, Monokai, Nord, Rose Pine Dawn, Solarized Light, Tokyo Night. Built-in themes are read-only. |
| Customize... | | Makes an editable copy of the selected theme and opens the theme editor. |
| Import... / Export... / Delete | | Share a theme as a `.json` file; delete one of your own themes. |
| Accent | Theme default | The highlight colour. Choose one of seven swatches or a custom colour; **Theme Default** clears it. |
| Application text (font size) | System default | 8 to 20 pt. **Default** goes back to the system size. |

Stored as `appearance/theme`, `appearance/accent` (empty means the theme's own) and `appearance/font_size` (0 means the system size).

## Layout

| Setting | Default | Meaning |
|---|---|---|
| Restore window and dock layout on startup | On | Reopen the app with the window size, position and panel arrangement you left. (`layout/restore`) |
| Reopen files from the last session | Off | At startup, open the workflows that were open when you closed the app. Not used if you start the app with a file name. (`layout/session`) |
| Save Current Layout | | Store the arrangement now. Same as **Window > Save Current Layout**. |
| Reset Layout | | Forget the saved arrangement and restore the default. Same as **Window > Reset Layout**. |

The list of open workflows is always remembered; it is reopened only when the second check box is on.

## Editor

| Setting | Default | Range | Meaning |
|---|---|---|---|
| Grid size | 20 px | 10 to 100 | Spacing of the canvas grid and of snapping. (`editor/grid_size`) |
| Show grid | On | | Draw the grid lines. (`editor/show_grid`) |
| Snap nodes to the grid while dragging | On | | Hold `Alt` while dragging to move freely. Also the **Snap to Grid** item of **Edit > Arrange**. (`editor/snap_to_grid`) |
| Simplify below | 50 % | 0 to 100 | Below this zoom level the canvas may draw simpler nodes to stay fast. 0 % keeps every node fully drawn. (`editor/render_detail_threshold`) |
| Node card | Auto | Always / Auto / Never | Draw the full node card. (`editor/render_detail_card`) |
| Sockets | Auto | | Draw the sockets. (`editor/render_detail_sockets`) |
| Label | Always | | Draw the floating label. (`editor/render_detail_label`) |
| Status indicator | Auto | | Draw the badge on the node's bottom edge. (`editor/render_detail_indicator`) |

For each of the four elements: **Always** draws it at every zoom, **Never** hides it at every zoom, **Auto** draws it only above the threshold. These settings change drawing only.

## Node Editor

Colours of the lines and sockets on the canvas. Click a swatch to choose a colour.

| Group | Item | Default |
|---|---|---|
| Edges | Default | `#B08848` |
| Edges | Selected | `#ff00d0` |
| Edges | Hovered | `#FF37A6FF` |
| Edges | Dragging | `#333334` |
| Sockets | Outline | `#FF000000` |
| Sockets | Highlight | `#FF37A6FF` |

**Reset Node Colours** restores these. They are stored under `node_editor_colors/`.

## Shortcuts

One row per [Arrange](canvas-and-nodes.md#arrange-grid-and-snapping) command, plus **Snap to Grid**. Click the box and press the keys. A shortcut needs `Ctrl`, `Alt` or `Shift`, or must be a function key. `Backspace` clears one, and the circular arrow next to a row restores its default. **Restore Defaults** resets all of them. A shortcut that is already used elsewhere in the window is refused with a message.

Defaults: **Align Horizontal Centers** `Ctrl+Shift+H`, **Align Vertical Centers** `Ctrl+Shift+V`; the others have none. Stored as a single value `editor/shortcuts` holding only the ones you changed.

## General

### General section

| Setting | Default | Meaning |
|---|---|---|
| Show the welcome dialog on startup | On | The startup dialog with your recent files. (`show_welcome_dialog`) |
| Recent files | 10 | How many files **File > Open Recent** keeps (1 to 50). (`general/recent_limit`) |
| Clear Recent Files | | Forget every recent path. |
| Open Preferences Folder | | Opens `%APPDATA%\Trigger Designer` in Explorer. |

### Error messages

| Setting | Default | Meaning |
|---|---|---|
| Keep running independent branches after a failure | On | When on, a Run continues with the branches that do not depend on the failed node; nodes that do depend on it are skipped with `TD-RUN-008`. When off, a Run stops at the first failed node. See [Running workflows](running-workflows.md#when-a-step-fails). (`errors/continue_past_failure`) |
| Hide data values in error messages | Off | Messages, copied details and stored errors show the code, column and row but not the offending values. See [Errors and problems](errors-and-problems.md#privacy-hiding-data-values-in-messages). (`errors/redact_values`) |
| Find the offending row for conversion errors | On | Run a bounded second search to name the first bad row and a few bad values. (`errors/locate_rows`) |
| Row search limit | 5,000,000 | How many rows that search may look at (100,000 to 100,000,000). (`errors/locate_row_cap`) |

The Problems dock's **Show technical details** toggle is stored as `errors/show_technical` (default off) and is changed from the dock, not from this window.

### Audit trail

These control the [run records](run-history-and-audit-trail.md).

| Setting | Default | Meaning |
|---|---|---|
| Record every run (run history) | On | Write a tamper-evident record after each Run. (`audit/record_runs`) |
| Record the user and machine name | On | Off leaves the user and machine fields empty. (`audit/record_identity`) |
| Fingerprint input files (SHA-256) | On | Hash each input file before it is read. (`audit/hash_inputs`) |
| Fingerprint output files (SHA-256) | On | Hash each output file after it is written. (`audit/hash_outputs`) |
| Store the generated code in each record | On | The code's hash is always kept; this also keeps the text. (`audit/embed_code`) |
| Warn when an input changed since the previous run | On | One Logs line per changed input; never blocks a Run. (`audit/warn_on_input_change`) |
| Run log folder | empty | Keep every run log in this folder instead of next to each workflow. **Browse** chooses it. (`audit/run_log_dir`) |
| Row counts | Auto | Auto, All nodes, Sinks only or Off. (`audit/row_counts`) |
| Count every node up to (MB) | 256 | The input size at which Auto changes from "All nodes" to "Sinks only". (`audit/exact_counts_max_mb`) |
| Skip hashing files above (MB) | 2048 | Bigger files are not fingerprinted. (`audit/hash_max_mb`) |

### Engagement

Defaults used when you export a workpaper: **Client**, **Engagement**, **Period**, **Prepared by** (blank means your Windows user name) and a **Logo** image (PNG or JPG). They are stored as `engagement/client_name`, `engagement/engagement_name`, `engagement/period`, `engagement/preparer` and `engagement/logo_path`; the workpaper folder is `export/workpaper_dir`. See [workpaper.md](workpaper.md).

### Reset

**Reset All Preferences** (after a confirmation) puts everything back to the defaults above, resets the layout and node colours, and refreshes the open workflows. Your own themes are kept.

## Complete list of stored preferences

Every key in the program's table of defaults:

| Key | Default |
|---|---|
| `general/schema_version` | 2 (internal) |
| `appearance/theme` | `dark` |
| `appearance/accent` | empty |
| `appearance/font_size` | 0 |
| `layout/restore` | true |
| `layout/session` | false |
| `editor/grid_size` | 20 |
| `editor/show_grid` | true |
| `editor/snap_to_grid` | true |
| `editor/shortcuts` | `{}` |
| `editor/render_detail_threshold` | 50 |
| `editor/render_detail_card` | `auto` |
| `editor/render_detail_sockets` | `auto` |
| `editor/render_detail_label` | `always` |
| `editor/render_detail_indicator` | `auto` |
| `errors/continue_past_failure` | true |
| `errors/redact_values` | false |
| `errors/locate_rows` | true |
| `errors/locate_row_cap` | 5000000 |
| `errors/show_technical` | false |
| `audit/record_runs` | true |
| `audit/run_log_dir` | empty |
| `audit/record_identity` | true |
| `audit/hash_inputs` | true |
| `audit/hash_outputs` | true |
| `audit/hash_max_mb` | 2048 |
| `audit/row_counts` | `auto` |
| `audit/exact_counts_max_mb` | 256 |
| `audit/embed_code` | true |
| `audit/warn_on_input_change` | true |
| `engagement/client_name`, `engagement/engagement_name`, `engagement/period`, `engagement/preparer`, `engagement/logo_path` | empty |
| `export/workpaper_dir` | empty |

A few more values are written by the app itself and are not in that table: `show_welcome_dialog` (default on), `general/recent_limit` (default 10), `recentFiles`, the window geometry and dock state under `layout/`, the open-file list `layout/session_files` and `layout/session_active`, and the node colours under `node_editor_colors/`.

## Where preferences are stored and how to reset them

All preferences are in one text file, `preferences.ini`, in `%APPDATA%\Trigger Designer\` (set the environment variable `TRIGGER_DESIGNER_DATA_DIR` to use another folder, for a portable installation). **Edit > Settings > General > Open Preferences Folder** opens it. Your own themes are in the `themes` folder beside it.

The first time the app starts with no `preferences.ini`, it copies the theme, grid size, recent files and node colours from the settings older versions kept in the Windows registry.

To reset everything: **Reset All Preferences**, or close the app and delete `preferences.ini`.

## If something goes wrong

| Symptom | What to do |
|---|---|
| My change to a setting did not seem to apply | Theme, accent and font apply at once. Audit settings apply to the next Run. Error settings apply to the next error. |
| I pressed Cancel but a setting stayed changed | Only theme, accent and font size are undone by Cancel. Other settings are saved as you change them. |
| A shortcut is refused | It is already in use, or it has no `Ctrl`, `Alt` or `Shift` and is not a function key. |
| The window looks wrong after choosing a theme | **Theme Default** under Accent, then pick the theme again; or **Reset All Preferences**. |
| Preferences are lost between sessions | The data folder may not be writable. Check `%APPDATA%\Trigger Designer` or the folder named by `TRIGGER_DESIGNER_DATA_DIR`. |
