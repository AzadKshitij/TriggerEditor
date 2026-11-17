---
icon: lucide/download
---

# Install Trigger Designer

!!! warning "Alpha build"

    Trigger Designer `0.1.0-alpha.3` is an **alpha** release for Windows. Expect
    rough edges, and report what you find.

## Download

Go to the [GitHub releases page](https://github.com/AzadKshitij/TriggerEditor/releases)
and open the newest **pre-release** named `v0.1.0-alpha.3`. Download **one** of these:

| File | Use it when |
|---|---|
| `TriggerDesigner-0.1.0-alpha.3-setup.exe` | You want a normal install: Start menu entries, `.tds` files open in the editor, and you choose the parts (editor, command line, AI tools). **Recommended.** |
| `TriggerDesigner-0.1.0-alpha.3-windows-portable.zip` | You want no installer: unzip anywhere and run. Contains the editor and the command line. |
| `TriggerDesigner-0.1.0-alpha.3-windows-editor-single-file.zip` | You only want the editor, as one lighter file. No command line and no AI tools. |

Also download `SHA256SUMS.txt` to check the download (see below).

## Install with the setup program

Run `TriggerDesigner-0.1.0-alpha.3-setup.exe`. It installs for your Windows user only,
so no administrator rights are needed.

The **Select Components** page offers these presets:

- **Full:** the editor, the command line (`tds`) and the AI tool setup.
- **Editor only:** the editor, with Start menu entries and `.tds` files.
- **Command line and AI tools only:** `tds` and `tds mcp`, without the editor window.
- **Custom:** tick the parts you want.

The **Tasks** page can also add the desktop icon, and add `tds` to your PATH so you can
type `tds` in any terminal. The PATH option is off by default.

Silent install for administrators, for example from a script:

```powershell
.\TriggerDesigner-0.1.0-alpha.3-setup.exe /VERYSILENT /NORESTART /COMPONENTS="editor,cli,mcp" /TASKS="addtopath"
```

## Use the portable zip

Unzip it anywhere you can write to, such as `C:\Tools\TriggerDesigner`, and keep the files
together. Start `TriggerEditor.exe` for the editor. Use `tds.exe` in the same folder for
the command line; `tds mcp` starts the AI tool server. Its README explains the commands.

## Check the download

Open PowerShell in the folder with the files and run (use the file you downloaded):

```powershell
Get-FileHash .\TriggerDesigner-0.1.0-alpha.3-setup.exe -Algorithm SHA256
```

The hash it prints must match the line for that file in `SHA256SUMS.txt`. If it does
not match, download the file again.

## First start: the Windows warning

The alpha is **not code-signed**, so Windows may show a warning the first time you
start it or run the setup program.

1. Start the program.
2. If the blue **Windows protected your PC** box appears, click **More info**.
3. Click **Run anyway**.

Windows shows this warning for every unsigned program it has not seen before. It does
not mean the file is known to be harmful. You can check the hash above first.

## Requirements

<div class="grid cards" markdown>

-   :lucide-monitor: **Windows 10 or 11, 64-bit**

    ---

    The alpha ships as a 64-bit Windows build only. There is no Linux or macOS version.

-   :lucide-hard-drive: **About 500 MB free**

    ---

    Space for the program itself. Your data needs its own space, on a drive you can write to.

-   :lucide-memory-stick: **Memory for the files you open**

    ---

    Large files need more memory. See [Limits and performance](guide/limits-and-performance.md).

</div>

## Where your data lives

| What | Where |
|---|---|
| Preferences and themes | `%APPDATA%\Trigger Designer` |
| AI tool policy file (installed with the AI tool setup) | `%APPDATA%\Trigger Designer\agent-policy.json` |
| Log files | `%APPDATA%\Trigger Designer\logs` |
| Run records (audit trail) | Next to each workflow, in a `<name>.runs` folder |
| Optional modules (only if you add any) | `%APPDATA%\Trigger Designer\modules` |

`%APPDATA%` is usually `C:\Users\<you>\AppData\Roaming`. Type `%APPDATA%` into the
Explorer address bar to open it.

The program does not check for updates and does not send data anywhere. The one
exception is an [optional module](guide/optional-modules.md) download that you start
yourself, after a screen that names the source. See
[Security and privacy](guide/security-and-privacy.md).

## Uninstall

Use **Apps > Installed apps > Trigger Designer > Uninstall**, or run the uninstaller in
the program folder. It removes the program files, the PATH entry and the Start menu
entries.

It does **not** remove your settings, your optional modules, or the `.tds` file
association. To remove the settings too, delete `%APPDATA%\Trigger Designer`. To remove
the association, use **Settings > Apps > Default apps**. Your workflow files and their run
records stay where you saved them.

## Known issues

- **Crash with code `0xC0000409`.** Under some heavy workloads (large files, many
  nodes running at once), the program can close without an error message. Windows
  records the crash as an application fault in Event Viewer. Save your work often and
  note the steps. This is the most important alpha risk, and it was first reported for
  alpha 1.
- **Setup and portable builds are new in alpha 3.** The setup program has not yet been
  tested on a clean Windows install. If something goes wrong, report it with the steps.
- **No update check.** Watch the releases page for new versions.

Full release notes are in [What's new in alpha 3](release-notes/v0.1.0-alpha.3.md) and on
the [GitHub release page](https://github.com/AzadKshitij/TriggerEditor/releases).

## Report a problem

Open an issue with the **Bug report** template:
[new issue](https://github.com/AzadKshitij/TriggerEditor/issues/new/choose).

Give the version, the steps, and the file name of the log in `%APPDATA%\Trigger Designer\logs`.
Do not attach workflow files or data files: they can hold business data. Describe
the shape of the data instead.

For security problems, follow [SECURITY.md](https://github.com/AzadKshitij/TriggerEditor/blob/main/SECURITY.md).
