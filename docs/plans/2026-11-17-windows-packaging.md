# Windows packaging: a portable zip and an installer, both with the editor, the `tds` command line and the AI (MCP) server

Status: plan, nothing built yet. Written 2026-11-17 against `main` at `ca38cb3` (version `0.1.0a2`).

## Decisions already made (2026-11-17)

| # | Decision |
|---|---|
| D1 | Portable is a **folder zip** (editor, CLI, MCP). The **single-file GUI-only editor stays** as a second, lighter download. |
| D4 | The installer is built with **Inno Setup**. |
| D9 | Builds ship **unsigned for now**, with a documented SmartScreen note. The build keeps an optional signing hook. |
| D6 | Default install scope is **per user** (an all-users option stays in the setup dialog). |
| D13 | **Short command names.** The command line is **`tds`**, and the AI-tool server is the subcommand **`tds mcp`** (one program, like `gh`). The long names `trigger-designer-cli` and `trigger-designer-mcp` stay as aliases. |

Still open (defaults used until changed): D8 creates only a default policy file, no AI workspace folder; releases are a **draft pre-release** from a GitHub Actions run on a `v*` tag.

## Goal

People can use Trigger Designer, its command-line program and its AI-tool (MCP) server **without installing Python or any developer tooling**, in one of two forms:

1. **Portable**: download one zip, unzip anywhere, run. Contains the editor and `tds.exe` (the command line, which also starts the AI-tool server with `tds mcp`). Writes nothing outside its own folder and the user's data folder, and needs no administrator rights.
2. **Installer** (Windows 10/11, 64-bit): a setup program that lets the user choose **what to install**: the editor, the command-line program, the AI-tool server. It adds Start Menu entries, optionally puts the command-line tools on `PATH`, registers `.tds` files, and uninstalls cleanly.

Non-goals for this plan: macOS or Linux builds, an automatic updater (the app stays offline by design), code-signing infrastructure beyond what is needed to sign the two artifacts, an MSI for enterprise deployment (listed under "Later").

## What exists today

| Piece | State |
|---|---|
| `trigger.spec` | PyInstaller spec. **Folder build** (`dist\TriggerEditor\`): editor exe + `trigger-designer-cli.exe`, built with `MERGE` so both share one `_internal\` runtime. **`--portable`**: a single-file, GUI-only exe (no CLI), which extracts itself to a temp folder on every start. |
| `scripts\build.bat` | Syncs locked deps, builds, smoke-tests the CLI (`--version`, `validate --deep` on a sample) and packages. |
| `scripts\package_windows.py` | Zips `dist` as `TriggerDesigner-<VERSION>-windows-folder.zip` / `-windows-portable.zip` and writes `SHA256SUMS.txt`. |
| `savedfiles\TriggerDesigner_Setup.iss` | An Inno Setup script: installs the editor, the CLI and `_internal`; a `PATH` task; the `.tds` association; per-user or all-users choice. |
| CI | Only `docs.yml`. There is **no build or release workflow**. |
| MCP server | Not in any build. |

## Gaps this plan has to close

1. **The MCP server cannot run from a frozen build as it is.** The data tools start `[sys.executable, "-m", "trigger_designer.cli", ...]`. In a PyInstaller exe `sys.executable` is the exe itself and `-m` is not understood. Nothing in `src/` branches on `sys.frozen`. (With D13 this is solved by construction: when frozen, the helper is `tds.exe` itself.)
2. **No hidden imports or smoke test for the MCP server inside the program that will carry it (`tds.exe`).** The `mcp` package pulls in `starlette`, `uvicorn`, `httpx2`, `pydantic`, `anyio`, `pyjwt`, `pywin32` and more; their PyInstaller behaviour is untested.
3. **The single-file build excludes the CLI** (and would exclude MCP) because it is GUI-only (`console=False`). A GUI-subsystem exe is the wrong host for stdio tools, which is why the full package is a folder (D1).
4. **The installer script has problems:**
   - the version (`0.1.0`) and publisher text are hard-coded and stale;
   - the `PATH` check reads `HKCU` while the entry is written under `HKA`, so an all-users install can add the folder twice;
   - the `PATH` entry is **not removed on uninstall**;
   - it has no component selection and no MCP;
   - it lives in `savedfiles\`, which holds sample data.
5. **No signing.** Unsigned executables get a SmartScreen "unrecognised app" warning, and unsigned self-extracting exes are the most likely to be flagged by antivirus.
6. **No automation and no check of the built artifacts** beyond the CLI smoke test: the editor exe is never started, and nothing exercises the packaged MCP server.

## Command names (D13)

Today's names are long to type and to put in an AI tool's configuration. One short program replaces them in everything a person types or copies:

| Today | New | Example |
|---|---|---|
| `trigger-designer-cli run flow.tds` | `tds run flow.tds` | |
| `trigger-designer-cli validate flow.tds --deep` | `tds validate flow.tds --deep` | |
| `trigger-designer-mcp --workspace D --policy P` | `tds mcp --workspace D --policy P` | AI-tool config: command `tds`, args `["mcp", "--workspace", "D", "--policy", "P"]` |
| `trigger-designer file.tds` (the editor) | `tds open file.tds` (starts the editor) and the editor exe itself | |
| `trigger-designer-mcp --print-config ...` | `tds mcp --print-config ...` | |

- `tds` is a free name on the machine checked, matches the `.tds` file type and is one word to remember.
- The long names stay for compatibility (existing scripts, the source install's `pyproject.toml` entry points, the docs written so far) and the new `tds` entry is added beside them, so nothing breaks. New documentation uses `tds`.
- `tds mcp` imports the MCP package only when that subcommand runs, so every other `tds` command stays as light as today (an existing test guards the CLI's import weight; the `mcp` subcommand must not break it).
- `tds open` is a convenience: it starts the editor exe (beside it when installed, `trigger-designer` from source) and returns immediately.

## The artifacts

```text
TriggerDesigner-0.1.0-alpha.2-windows-portable.zip     (portable: folder layout, see below)
TriggerDesigner-0.1.0-alpha.2-windows-editor-single-file.zip   (the existing single-file, editor-only exe; lighter, no CLI or MCP)
TriggerDesigner-0.1.0-alpha.2-setup.exe                (installer)
SHA256SUMS.txt
```

Portable layout (the zip contains one folder, `TriggerDesigner\`):

```text
TriggerDesigner\
  TriggerEditor.exe              the editor (GUI)
  tds.exe                        command line, and `tds mcp` for AI tools (console program)
  _internal\                     the shared runtime (one copy, used by both)
  README.txt                     a few lines: what each exe is, where the guides are
  LICENSE
```

## Decisions (recommended answer first)

**D1 (decided). Portable = a folder zip; the single-file editor stays as a second download.** All three programs share one `_internal\`, so the zip is only a little larger than the editor alone. It starts fast (no extraction to a temp folder), is less likely to be flagged by antivirus, and the MCP server can find its sibling CLI. A single-file exe cannot be both the editor and a stdio tool. The single-file GUI-only exe is kept as a lighter second download (named `-windows-editor-single-file.zip` so nobody mistakes it for the full package); it still does not include the CLI or MCP, and the download page says so.

**D2. One shared runtime via PyInstaller `MERGE` with two programs** (the editor and `tds.exe`, which carries the CLI and the MCP server). This is what the CLI already does. The CLI loads the editor's own classes headlessly (offscreen Qt), so even "CLI only" needs the Qt runtime; see D5.

**D3. The MCP server starts its helper steps through one launcher.** A small `launcher` helper decides how to start a child CLI command: in development `[sys.executable, "-m", "trigger_designer.cli"]`; when frozen, `[sys.executable]`, which is `tds.exe` itself (it runs the CLI when given a CLI command, so `tds mcp` calls `tds schema ...`). No sibling file to find, nothing to go missing, and it works from the single folder or an installed copy alike.

**D4 (decided). Installer technology: Inno Setup 6.** It already exists in the repo, supports exactly the "choose what to install" screen (components), per-user installs without administrator rights, `PATH` tasks, file associations, and a clean uninstaller, and it needs no extra runtime. *Alternatives:* WiX (an MSI, better for enterprise deployment through Intune or Group Policy, but far more authoring work; listed under "Later"), NSIS (similar to Inno, less common now), MSIX (needs signing and restricts writing to the install folder).

**D5. What the components really control.** Because of D2, the shared runtime (the large part) is always installed. Components choose:

| Component | Installs | Adds |
|---|---|---|
| **Trigger Designer (editor)** | `TriggerEditor.exe` | Start Menu entry, optional desktop icon, `.tds` association |
| **Command-line tools** | `tds.exe` | optional "add `tds` to PATH" task |
| **AI tool setup (MCP)** | the default policy file, the "AI tools setup" Start Menu entry and the guide shortcut (D8). `tds mcp` itself lives in `tds.exe`, so this component **requires** the command-line tools and selects them automatically | the same "add to PATH" task (an AI tool config can also use the full path) |
| *Runtime (hidden, always)* | `_internal\`, licence | the uninstaller |

The installer says plainly that deselecting a component removes entry points, not most of the disk space. Presets: **Full**, **Editor only**, **Command line and AI tools only**, **Custom**.

**D6 (decided). Install scope.** Default **per user** (`%LOCALAPPDATA%\Programs\Trigger Designer`, no administrator needed); an "all users" option through the standard Inno dialog (`PrivilegesRequiredOverridesAllowed=dialog`, already in the script). Portable needs no rights at all.

**D7. `PATH` and file association.** `PATH` entries are tasks, unchecked by default, written for the right scope, de-duplicated, and **removed on uninstall**. The `.tds` association registers "Open with" and the default icon, as today. A new shell entry is not needed.

**D8. AI setup helper, not automatic edits of other tools' settings.** Rewriting Claude Code, Cursor or Codex configuration files from an installer is intrusive and fragile. Instead:

- add `tds mcp --print-config --client {claude-code,cursor,codex,claude-desktop} [--workspace DIR] [--policy FILE]`, which prints the exact command or JSON/TOML snippet with the **installed, absolute paths** (or plain `tds` when it is on `PATH`);
- the installer (MCP component) creates a default policy file in `%APPDATA%\Trigger Designer\agent-policy.json` (`schema_only`, `edit` false, outside any workspace) and a Start Menu entry "AI tools setup" that opens the guide and prints the snippet;
- the final installer page offers to open the guide. No third-party configuration is touched.

**D9 (decided: unsigned for now).** Alpha builds ship unsigned, and the install page explains the SmartScreen warning (it already does for the editor). The build keeps an optional hook: when a certificate is configured it signs `TriggerEditor.exe`, the two console exes, the installer and the uninstaller with a timestamp. Choosing a certificate (OV, EV or Azure Trusted Signing) is a separate step before a non-alpha release. Because unsigned self-extracting exes are the most likely to be flagged by antivirus, the single-file editor is the artifact to scan first.

**D10. Versions and names.** One source of truth: `core/constants.VERSION`. The installer gets it from the build (`/DMyAppVersion=...`), not from a hard-coded line. A test (already added) keeps `pyproject.toml`, `uv.lock` and the constant equal. Artifact names as above.

**D11. Data, upgrade and uninstall.** Same `AppId` for upgrades in place (never downgrade without asking). User data lives outside the install folder (`%APPDATA%\Trigger Designer`: preferences, logs, optional modules; run records sit beside each workflow) and is **kept** on uninstall; the uninstaller offers to delete it. The uninstaller also removes the `PATH` entries and the file association.

**D12. No updater.** The program does not contact the internet, so an update means downloading a new installer or zip. The install page says so.

## Risks and the spikes that settle them

| Risk | Spike (first, one afternoon each) | Pass criterion |
|---|---|---|
| `mcp` and its dependencies do not freeze cleanly (hidden imports, `pydantic`, `importlib.metadata`, pywin32 DLLs) | Add the `mcp` subcommand and its imports to the CLI program in `trigger.spec`; build; run `tds.exe mcp` and drive it with the SDK's stdio client | `initialize`, `list_tools`, `get_policy` and `list_ops` succeed from the built exe |
| MCP bundles HTTP server libraries (`uvicorn`, `starlette`, `httpx2`) although it uses stdio only | Try excluding the HTTP transports; otherwise accept and document | Either excluded, or documented that they are present but never used; the network guard test still passes |
| Child CLI process from a frozen MCP | Implement the launcher (D3); run `get_schema` through the built `tds.exe mcp` | A data tool returns a schema in the built folder, from a path containing spaces and non-ASCII characters |
| Size and startup with the MCP packages added to `tds.exe` | Build and measure; also confirm the other `tds` commands still start as fast (the MCP imports must stay lazy) | Zip size and cold start reported; `tds --version` is no slower than today |
| Antivirus false positives | Scan the portable zip and installer (VirusTotal, Windows Defender) | No detections, or the vendors are contacted before release |
| Installer component logic | Prototype the Inno `[Components]` and `[Tasks]` with each preset | Each preset installs exactly its files; uninstall leaves nothing behind |

## Work plan

**Phase 0: spikes (above).** Output: a short findings note and go/no-go on D1 to D3.

**Phase 1: build the portable folder.**
1. **Names (D13):** add `mcp` and `open` subcommands to the CLI (`mcp` imports the server lazily); add the `tds` entry point to `pyproject.toml` beside the long names; rename the frozen CLI exe to `tds.exe` in `trigger.spec`; add the MCP package's hidden imports. Tests: the subcommands exist, `tds mcp --help` works, the import-weight test still passes.
2. `agent/launcher.py`: choose how to start a child CLI (D3); `AgentTools` uses it. Unit tests for both modes.
3. `tds mcp --print-config` (D8) with tests for every client.
4. `scripts/smoke_dist.py`: runs against `dist\`, never against source: `tds --version`, `tds validate --deep`, a headless `tds run`; the editor exe started offscreen with a `--smoke-test` flag that opens a sample workflow and exits 0; `tds mcp` driven over stdio (list tools, `get_policy`, `list_files`, `get_schema` on a sample, a refused call).
5. `package_windows.py`: the portable zip is the folder layout with a `README.txt`; the single-file editor is packaged separately under its own name.
6. `build.bat` runs the smoke script and fails the build if it fails.

**Phase 2: the installer.**
1. Move the script to `installer\TriggerDesigner.iss`; take the version, publisher and file list from the build.
2. Components, presets and tasks (D5, D7); fix the `PATH` check and add `PATH` removal on uninstall.
3. MCP component: default policy file and the "AI tools setup" entry (D8); final page with a link to the guide.
4. Silent install switches (`/VERYSILENT /COMPONENTS=...`) for administrators; document them.
5. Signing hook (D9), optional.
6. `scripts/smoke_installer.ps1`: silent install into a temp folder, run the smoke script against it, uninstall, check that nothing is left (files, `PATH`, registry).

**Phase 3: release automation.** A GitHub Actions workflow on `v*` tags (Windows runner): `uv sync --frozen`, tests, build, smoke the folder, build the installer, smoke the installer, checksums, a draft pre-release with the artifacts and the release notes. Allow a manual run to produce artifacts without a release. (The repo has no test workflow today; add a lightweight one for pull requests at the same time.)

**Phase 4: documentation and release checklist.**
- `docs/install.md`: two downloads, how to pick, the installer pages, silent install, uninstall, antivirus note.
- `docs/guide/mcp-server.md`: configuration with `tds mcp`, the installed-path variant, and the source variant.
- `docs/guide/cli.md` and every guide that shows `trigger-designer-cli`: use `tds`, and note that the long names still work.
- `docs/release-notes/v0.1.0-alpha.2.md` and the navigation entry.
- A release checklist in `docs/contributing/` (version bump, build, smoke, sign, scan, publish).

## Verification matrix (before any release)

| Check | How |
|---|---|
| Clean Windows 10 and 11 virtual machines, standard (non-admin) user | portable run; per-user install; all-users install |
| Paths with spaces and non-ASCII characters in the user name and install folder | install, run the editor, CLI and MCP |
| Each installer preset installs exactly its files | file listing against the expected set |
| Upgrade over the previous version; downgrade is refused or asked | install old, then new |
| Uninstall leaves no files, `PATH` entry or association; user data kept unless chosen | automated in `smoke_installer.ps1` |
| An AI tool (Claude Code) configured from the printed snippet builds a workflow with the installed MCP server | manual, once per release |
| `SHA256SUMS.txt` matches; the antivirus scan is clean | scripted |

## Open questions for the project owner

1. Should the installer **create a default AI workspace folder** as well as the default policy file (it creates only the policy file in this plan)?
2. Release flow: GitHub Actions on tags producing a **draft** pre-release for approval (recommended)?
3. Is an MSI for managed deployment needed soon, or is it fine as a later item?

## Later (not in this plan)

An MSI through WiX for managed deployment; `winget` and Chocolatey manifests; a code-signing pipeline with hardware keys; a portable build that is truly single-file with a console; Linux and macOS builds.
