# Install Trigger Designer

Trigger Designer `0.1.0a1` is an **alpha** release for Windows. It is a first public
build: expect rough edges, and report what you find.

## Download

Go to the [GitHub releases page](https://github.com/AzadKshitij/TriggerEditor/releases)
and open the newest **pre-release** named `v0.1.0-alpha.1`. Download:

- `TriggerDesigner-0.1.0a1-windows-portable.zip` (the program)
- `SHA256SUMS.txt` (to check the download, see below)

The alpha has no installer. Unzip the archive anywhere you can write to, such as
`C:\Tools\TriggerDesigner`, and keep the files together.

## Check the download

Open PowerShell in the folder with the files and run:

```powershell
Get-FileHash .\TriggerDesigner-0.1.0a1-windows-portable.zip -Algorithm SHA256
```

The hash it prints must match the line for that file in `SHA256SUMS.txt`. If it does
not match, download the file again.

## First start: the Windows warning

The alpha is **not code-signed**, so Windows may show a warning the first time you
start it.

1. Double-click `TriggerEditor.exe`.
2. If the blue **Windows protected your PC** box appears, click **More info**.
3. Click **Run anyway**.

Windows shows this warning for every unsigned program it has not seen before. It does
not mean the file is known to be harmful. You can check the hash above first.

## Requirements

- Windows 10 or Windows 11, 64-bit.
- About 500 MB of free disk space for the program. Your data needs its own space.
- Enough memory for the files you process. Large files need more memory.

## Where your data lives

| What | Where |
|---|---|
| Preferences and themes | `%APPDATA%\Trigger Designer` |
| Log files | `%APPDATA%\Trigger Designer\logs` |
| Run records (audit trail) | Next to each workflow, in a `<name>.runs` folder |

`%APPDATA%` is usually `C:\Users\<you>\AppData\Roaming`. Type `%APPDATA%` into the
Explorer address bar to open it.

The program does not check for updates and does not send data anywhere. See
[Security and privacy](guide/security-and-privacy.md).

## Uninstall

Delete the program folder. To remove your settings too, delete
`%APPDATA%\Trigger Designer`. Your workflow files and their run records stay where
you saved them.

## Known issues in alpha 1

- **Crash with code `0xC0000409`.** Under some heavy workloads (large files, many
  nodes running at once), the program can close without an error message. Windows
  records the crash as an application fault in Event Viewer. Save your work often and
  note the steps. This is the most important alpha risk.
- **Portable only.** There is no installer and no Linux build in this alpha.
- **No update check.** Watch the releases page for new versions.

Full release notes are on the [GitHub release page](https://github.com/AzadKshitij/TriggerEditor/releases).

## Report a problem

Open an issue with the **Bug report** template:
[new issue](https://github.com/AzadKshitij/TriggerEditor/issues/new/choose).

Give the version, the steps, and the file name of the log in `%APPDATA%\Trigger Designer\logs`.
Do not attach workflow files or data files: they can hold business data. Describe
the shape of the data instead.

For security problems, follow [SECURITY.md](https://github.com/AzadKshitij/TriggerEditor/blob/main/SECURITY.md).
