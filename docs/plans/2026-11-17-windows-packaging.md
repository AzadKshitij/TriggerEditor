# Windows packaging: a portable zip and an installer, both with the editor, the CLI and the AI (MCP) server

Status: plan, nothing built yet. Written 2026-11-17 against `main` at `ca38cb3` (version `0.1.0a2`).

## Goal

People can use Trigger Designer, its command-line program and its AI-tool (MCP) server **without installing Python or any developer tooling**, in one of two forms:

1. **Portable**: download one zip, unzip anywhere, run. Contains the editor, `trigger-designer-cli` and `trigger-designer-mcp`. Writes nothing outside its own folder and the user's data folder, and needs no administrator rights.
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

1. **The MCP server cannot run from a frozen build as it is.** The data tools start `[sys.executable, "-m", "trigger_designer.cli", ...]`. In a PyInstaller exe `sys.executable` is the exe itself and `-m` is not understood. Nothing in `src/` branches on `sys.frozen`.
2. **No spec entry, hidden imports or smoke test for the MCP server.** The `mcp` package pulls in `starlette`, `uvicorn`, `httpx2`, `pydantic`, `anyio`, `pyjwt`, `pywin32` and more; their PyInstaller behaviour is untested.
3. **The "portable" build excludes the CLI** (and would exclude MCP) because it is single-file and GUI-only (`console=False`). A GUI-subsystem exe is the wrong host for stdio tools.
4. **The installer script has problems:**
   - the version (`0.1.0`) and publisher text are hard-coded and stale;
   - the `PATH` check reads `HKCU` while the entry is written under `HKA`, so an all-users install can add the folder twice;
   - the `PATH` entry is **not removed on uninstall**;
   - it has no component selection and no MCP;
   - it lives in `savedfiles\`, which holds sample data.
5. **No signing.** Unsigned executables get a SmartScreen "unrecognised app" warning, and unsigned self-extracting exes are the most likely to be flagged by antivirus.
6. **No automation and no check of the built artifacts** beyond the CLI smoke test: the editor exe is never started, and nothing exercises the packaged MCP server.

## The artifacts

```text
TriggerDesigner-0.1.0-alpha.2-windows-portable.zip     (portable: folder layout, see below)
TriggerDesigner-0.1.0-alpha.2-setup.exe                (installer)
SHA256SUMS.txt
```

Portable layout (the zip contains one folder, `TriggerDesigner\`):

```text
TriggerDesigner\
  TriggerEditor.exe              the editor (GUI)
  trigger-designer-cli.exe       command line
  trigger-designer-mcp.exe       AI-tool server (stdio)
  _internal\                     the shared runtime (one copy, used by all three)
  README.txt                     three lines: what each exe is, where the guides are
  LICENSE
```

## Decisions (recommended answer first)

**D1. Portable = a folder zip, not a single-file exe.** All three programs share one `_internal\`, so the zip is only a little larger than the editor alone. It starts fast (no extraction to a temp folder), is less likely to be flagged by antivirus, and the MCP server can find its sibling CLI. A single-file exe cannot be both the editor and a stdio tool. *Alternative:* keep today's single-file GUI-only build as a second, lighter download; it would still not include the CLI or MCP.

**D2. One shared runtime via PyInstaller `MERGE` with three programs** (editor, CLI, MCP). This is what the CLI already does. The CLI loads the editor's own classes headlessly (offscreen Qt), so even "CLI only" needs the Qt runtime; see D5.

**D3. MCP finds the CLI explicitly.** A small `launcher` helper decides how to start a child CLI command: in development `[sys.executable, "-m", "trigger_designer.cli"]`; when frozen, the sibling `trigger-designer-cli.exe` in the same folder (with an environment override and a clear error if it is missing). The MCP server never calls itself recursively. *Alternative:* the MCP exe runs CLI code in-process by a hidden `__cli__` argument, which removes the dependency on a sibling file but couples the two entry points.

**D4. Installer technology: Inno Setup 6.** It already exists in the repo, supports exactly the "choose what to install" screen (components), per-user installs without administrator rights, `PATH` tasks, file associations, and a clean uninstaller, and it needs no extra runtime. *Alternatives:* WiX (an MSI, better for enterprise deployment through Intune or Group Policy, but far more authoring work; listed under "Later"), NSIS (similar to Inno, less common now), MSIX (needs signing and restricts writing to the install folder).

**D5. What the components really control.** Because of D2, the shared runtime (the large part) is always installed. Components choose:

| Component | Installs | Adds |
|---|---|---|
| **Trigger Designer (editor)** | `TriggerEditor.exe` | Start Menu entry, optional desktop icon, `.tds` association |
| **Command-line tools** | `trigger-designer-cli.exe` | optional "add to PATH" task |
| **AI tool server (MCP)** | `trigger-designer-mcp.exe` and the AI setup helper (D8) | optional "add to PATH" task; a default policy file |
| *Runtime (hidden, always)* | `_internal\`, licence | the uninstaller |

The installer says plainly that deselecting a component removes entry points, not most of the disk space. Presets: **Full**, **Editor only**, **Command line and AI tools only**, **Custom**.

**D6. Install scope.** Default **per user** (`%LOCALAPPDATA%\Programs\Trigger Designer`, no administrator needed); an "all users" option through the standard Inno dialog (`PrivilegesRequiredOverridesAllowed=dialog`, already in the script). Portable needs no rights at all.

**D7. `PATH` and file association.** `PATH` entries are tasks, unchecked by default, written for the right scope, de-duplicated, and **removed on uninstall**. The `.tds` association registers "Open with" and the default icon, as today. A new shell entry is not needed.

**D8. AI setup helper, not automatic edits of other tools' settings.** Rewriting Claude Code, Cursor or Codex configuration files from an installer is intrusive and fragile. Instead:

- add `trigger-designer-mcp --print-config --client {claude-code,cursor,codex,claude-desktop} [--workspace DIR] [--policy FILE]`, which prints the exact command or JSON/TOML snippet with the **installed, absolute paths**;
- the installer (MCP component) creates a default policy file in `%APPDATA%\Trigger Designer\agent-policy.json` (`schema_only`, `edit` false, outside any workspace) and a Start Menu entry "AI tools setup" that opens the guide and prints the snippet;
- the final installer page offers to open the guide. No third-party configuration is touched.

**D9. Signing.** Sign `TriggerEditor.exe`, the two console exes, the installer and (if the tool allows) the uninstaller, with a timestamp. The build calls `signtool` only when a certificate is configured, so unsigned alpha builds still work and say so. *Needs a decision:* which certificate (OV, EV, or Azure Trusted Signing) and who holds it.

**D10. Versions and names.** One source of truth: `core/constants.VERSION`. The installer gets it from the build (`/DMyAppVersion=...`), not from a hard-coded line. A test (already added) keeps `pyproject.toml`, `uv.lock` and the constant equal. Artifact names as above.

**D11. Data, upgrade and uninstall.** Same `AppId` for upgrades in place (never downgrade without asking). User data lives outside the install folder (`%APPDATA%\Trigger Designer`: preferences, logs, optional modules; run records sit beside each workflow) and is **kept** on uninstall; the uninstaller offers to delete it. The uninstaller also removes the `PATH` entries and the file association.

**D12. No updater.** The program does not contact the internet, so an update means downloading a new installer or zip. The install page says so.

## Risks and the spikes that settle them

| Risk | Spike (first, one afternoon each) | Pass criterion |
|---|---|---|
| `mcp` and its dependencies do not freeze cleanly (hidden imports, `pydantic`, `importlib.metadata`, pywin32 DLLs) | Add the third program to `trigger.spec`; build; run `trigger-designer-mcp.exe` and drive it with the SDK's stdio client | `initialize`, `list_tools`, `get_policy` and `list_ops` succeed from the built exe |
| MCP bundles HTTP server libraries (`uvicorn`, `starlette`, `httpx2`) although it uses stdio only | Try excluding the HTTP transports; otherwise accept and document | Either excluded, or documented that they are present but never used; the network guard test still passes |
| Child CLI process from a frozen MCP | Implement the launcher (D3); run `get_schema` through the built MCP exe | A data tool returns a schema in the built folder, from a path containing spaces and non-ASCII characters |
| Size and startup of three programs with `MERGE` | Build and measure | Zip size and cold start reported; MCP adds only a modest amount |
| Antivirus false positives | Scan the portable zip and installer (VirusTotal, Windows Defender) | No detections, or the vendors are contacted before release |
| Installer component logic | Prototype the Inno `[Components]` and `[Tasks]` with each preset | Each preset installs exactly its files; uninstall leaves nothing behind |

## Work plan

**Phase 0: spikes (above).** Output: a short findings note and go/no-go on D1 to D3.

**Phase 1: build the portable folder.**
1. Add `src/trigger_designer/agent/server_entry.py` and the MCP program to `trigger.spec` (three-way `MERGE`); add the MCP package's hidden imports and data.
2. `agent/launcher.py`: choose how to start a child CLI (D3); `AgentTools` uses it. Unit tests for both modes.
3. `trigger-designer-mcp --print-config` (D8) with tests for every client.
4. `scripts/smoke_dist.py`: runs against `dist\`, never against source: CLI `--version`, `validate --deep`, a headless `run`; the editor exe started offscreen with a `--smoke-test` flag that opens a sample workflow and exits 0; the MCP exe driven over stdio (list tools, `get_policy`, `list_files`, `get_schema` on a sample, a refused call).
5. `package_windows.py`: the portable zip is the folder layout; add a `README.txt`; keep the single-file build only if D1's alternative is chosen.
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
- `docs/guide/mcp-server.md`: the installed path variant next to the source variant.
- `docs/guide/cli.md`: the installed path and `PATH`.
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

1. Portable as a **folder zip** (recommended), or also keep the single-file GUI-only exe?
2. **Inno Setup** for the installer (recommended)? Is an MSI for enterprise needed soon?
3. Default install scope: **per user** (recommended), all users, or ask?
4. **Code signing:** is there a certificate, or should alpha builds ship unsigned with a documented SmartScreen note?
5. Should the installer **create a default AI workspace folder** as well as the default policy file (it creates only the policy file in this plan)?
6. Release flow: GitHub Actions on tags producing a **draft** pre-release for approval (recommended)?

## Later (not in this plan)

An MSI through WiX for managed deployment; `winget` and Chocolatey manifests; a code-signing pipeline with hardware keys; a portable build that is truly single-file with a console; Linux and macOS builds.
