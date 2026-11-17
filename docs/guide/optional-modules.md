# Optional modules

Optional modules add a capability that Trigger Designer does not include on its own. The program works completely offline without them, and an installed module works offline too. This page explains what a module is, how to add one, what the consent screen tells you, and how to check, update and remove modules.

[Back to the guide index](README.md)

!!! success "The only connection to the internet"

    Trigger Designer connects to the internet in one case: when you press **Download** on a module's consent screen. It then connects to the host named on that screen, once for each file. Nothing about you, your workflows or your data is sent. Everything else works offline.

## On this page

- [What an optional module is](#what-an-optional-module-is)
- [The promise](#the-promise)
- [Add a module](#add-a-module)
- [What the consent screen shows](#what-the-consent-screen-shows)
- [After the download](#after-the-download)
- [Check, update and remove](#check-update-and-remove)
- [Where the files live](#where-the-files-live)
- [Use modules offline](#use-modules-offline)
- [For IT and security teams](#for-it-and-security-teams)
- [Error codes](#error-codes)
- [Frequently asked questions](#frequently-asked-questions)

## What an optional module is

A module is a small set of files that adds one optional capability. Its description is a manifest, `module.json`, which gives the module's name, version and license, and lists its files. For each file the manifest gives the address it comes from, its exact size and its SHA-256 hash.

**This version ships with an empty catalogue**, the list of modules the program knows about. No module is offered yet, so there is nothing to install. Modules will arrive in later versions. The rest of this page describes how the feature works, so you know what to expect when they do.

## The promise

- **Offline by default.** The program does not connect to the internet when it starts, while you work, or when you run a workflow.
- **One exception, which you start.** Pressing **Download** on a module's consent screen is the only action that connects to the internet.
- **Only the named host.** The connection goes only to the host named on the consent screen. There is one connection for each file.
- **Nothing about you is sent.** No account, identifier, workflow or data is sent. As with any download, the host sees the request, including your computer's internet address.
- **Nothing is run.** A downloaded file is checked, stored and kept as data. The program does not run it, unpack it or import it.

## Add a module

1. Choose **Help > Optional modules…**.
2. Select a module in the list. Its status shows whether it is installed.
3. Press **Install**. If a newer version of an installed module is listed, the button reads **Update** instead.
4. Read the consent screen (see [What the consent screen shows](#what-the-consent-screen-shows)). Press **Cancel** if anything is not what you expect.
5. Press **Download**. A progress window shows the download. Press **Cancel** in that window to stop it. The module is then not installed.
6. When every file has been checked, the module shows **Installed**.

**Cancel is the default button** on the consent screen, so pressing Enter does not start a download.

## What the consent screen shows

The consent screen is titled **Download** followed by the module's name and version. Before you press **Download**, check:

| Item | What it tells you |
|---|---|
| Notice | What will happen: the host names, the number of files, the total size, and that nothing else is sent. |
| Downloads from | The host names the files come from. This is the only place the program will connect. |
| Total download | The combined size of all the files. |
| License | The license of the module. |
| Files | For each file: its name (hover over the name to see its full address), its size, and its **SHA-256** hash. |

If you have another source for the hashes, such as the publisher's own documentation, compare them with the table before you press **Download**.

## After the download

- Each file is checked against the size and the SHA-256 hash on the consent screen. A file that does not match is discarded, and the module is not installed.
- The module is stored in its own folder under the app data folder. See [Where the files live](#where-the-files-live).
- The module is used offline. You do not need a connection to use it, and the program does not check for changes online.

## Check, update and remove

Each module in the **Optional modules** dialog has a status:

| Status | Meaning | What to do |
|---|---|---|
| Not installed | The module is listed but is not on this computer. | Press **Install**. |
| Installed | The installed version is the one listed in the catalogue. | Nothing. |
| Installed (changed on disk) | A file of the installed module no longer matches its hash. | Press **Verify** to see which file. Then **Remove** the module and **Install** it again. |
| Update available | The catalogue lists a different version from the one installed. | Press **Update**. The new version goes through the same consent screen and replaces the installed one. |

The dialog's buttons are **Install** (or **Update**), **Verify**, **Remove** and **Close**. **Verify** re-checks the installed files against their recorded hashes. **Remove** deletes the selected module from this computer.

The command line can also list, verify and remove modules. These commands work offline:

```text
trigger-designer-cli modules list
trigger-designer-cli modules verify <module-id>
trigger-designer-cli modules remove <module-id> --yes
```

`remove` does nothing without `--yes`. Add `--json` to any of these commands for output that a script can read.

There is no install command on the command line, on purpose. A download has to go through its consent screen in the program.

## Where the files live

Each installed module is a folder inside the app data folder:

```text
%APPDATA%\Trigger Designer\modules\<module-id>\
    module.json      the record: when the module was installed, and its manifest
    <the module's files>
```

- To open the app data folder, paste `%APPDATA%\Trigger Designer` into the address bar of Explorer. The **Open Preferences Folder** action on the General page of [Preferences](preferences.md) opens the same folder.
- `TRIGGER_DESIGNER_DATA_DIR` moves the whole app data folder, and the modules folder with it. Set it before you start the program.
- Removing a module deletes only its own folder.

## Use modules offline

A computer without internet access can still use installed modules. Bring the module in from a computer where it was installed:

1. On a computer that can connect, install the module from **Help > Optional modules…**.
2. Copy the module's whole folder, `%APPDATA%\Trigger Designer\modules\<module-id>\`, to the same place on the offline computer. The copy must still contain `module.json` and every file of the module.
3. On the offline computer, run `trigger-designer-cli modules verify <module-id>`. It checks every file against the hashes in `module.json` and reports anything that does not match.

If your IT team keeps a catalogue for offline use, point the environment variable `TRIGGER_DESIGNER_MODULE_CATALOGUE` at that file before you start the program. The program then reads its list of modules and versions from that file instead of the catalogue that ships with it. The file has this shape:

```json
{"schema": 1, "modules": []}
```

Each entry in `modules` describes one module: `id`, `name`, `version`, `description`, `license` and `files`, and optionally `homepage`. Each file has `name`, `url`, `size_bytes` and `sha256`. The `sha256` value is 64 lowercase hexadecimal characters. Each `url` must be an `https` address with a host name and no user name or password.

The program makes no connection while you do any of this.

## For IT and security teams

The downloader checks the following, in this order:

1. **The address.** Only `https://` addresses are used, and an address with a user name or password is refused (`TD-MOD-004`). The connection goes only to the hosts that the consent screen lists, which are the hosts of the module's own file addresses.
2. **Redirects.** A redirect is followed only to an `https` address on the same host. Any other redirect is refused (`TD-MOD-004`).
3. **Size.** A file that is bigger or smaller than its listed size is discarded (`TD-MOD-006`). The size is checked while the file arrives, so a file cannot grow past its listed size.
4. **Hash.** The SHA-256 of each file must equal the hash on the consent screen. Otherwise the file is discarded (`TD-MOD-007`).
5. **Installation.** Files are written to a private folder and moved into the modules folder only when every file has passed. `module.json` is written last. A failed installation leaves nothing behind.

Other facts:

- Each file is one HTTPS GET with the user agent `TriggerDesigner-modules/1`. It sends no cookies and no credentials, and nothing about the user, the workflows or the computer.
- The download uses the computer's proxy settings.
- Nothing is extracted, run or imported.
- Only one file of the program imports a networking library: `core/modules/downloader.py`. The project's test suite includes a guard test (`tests/unit/test_network_isolation.py`) that fails if any other file imports a networking library or calls a connection function. A second test (`tests/ui/test_no_network_at_idle.py`) checks that the main window makes no connection while a workflow is open and nothing is pressed.

What the checks do not cover:

- A hash shows that a file is the file the module description names. It does not show that the file is safe to use. The program does not scan files for malware.
- Modules are not digitally signed in this version. Decide whether to trust a publisher before you install its module.

## Error codes

Problems with modules use the codes `TD-MOD-001` to `TD-MOD-009`. The message says what happened, and the hint says what to do next. How to read a message is explained in [Errors and problems](errors-and-problems.md#how-to-read-a-message).

| Code | What it means |
|---|---|
| `TD-MOD-001` | A module description is not valid. Update Trigger Designer, or ask the publisher for a corrected list. |
| `TD-MOD-002` | The module is not installed. Check the name, or list the installed modules. |
| `TD-MOD-003` | The module was not approved for download. Read the consent screen again and accept it. Nothing was downloaded. |
| `TD-MOD-004` | The download address is not allowed: it is not an `https` address, it has a user name or password, or a redirect led to another host. Nothing was installed. |
| `TD-MOD-005` | The module could not be downloaded: the connection failed or timed out, the server returned an error, or the connection dropped. Nothing was installed. |
| `TD-MOD-006` | A file arrived with more or fewer bytes than the consent screen lists. The download was discarded. |
| `TD-MOD-007` | A file does not match its SHA-256 hash. The file was discarded and nothing was installed. Report it to the publisher. |
| `TD-MOD-008` | A file could not be written, moved or removed in the data folder, usually because the disk is full or the folder is not writable. Nothing was installed. |
| `TD-MOD-009` | You cancelled the download. Nothing was installed. This is a warning, not an error. |

## Frequently asked questions

**Does Trigger Designer connect to the internet?**
Not by itself. It connects only when you press **Download** on a module's consent screen, and then only to the host named there.

**Can I use the program with no internet connection?**
Yes. The program works fully offline, and so do installed modules. See [Use modules offline](#use-modules-offline).

**Does the program check for new versions of modules?**
No. It makes no connection to check. The **Update available** status compares the installed version with the version listed in the catalogue file on your computer.

**Which modules can I install?**
None in this version. The catalogue that ships with the program is empty.

**What does a download send?**
A request for the file, to the host named on the consent screen. The request carries no account, no workflow and no data. The host can see your computer's internet address, as it can for any download.

**Why can I not install a module from the command line?**
Installation happens only in the program, so that every download passes through its consent screen. The command line lists, verifies and removes modules, and it works offline.

**What if a file does not match its hash?**
The file is discarded and nothing is installed. The message is `TD-MOD-007`. Report the problem to the publisher.

**Does removing a module change my workflows?**
No. Removal deletes only the module's own folder.

**A module shows "Installed (changed on disk)". What should I do?**
Press **Verify** to see which file no longer matches. Then **Remove** the module and **Install** it again from its consent screen.

**Can I move the modules folder?**
Yes. Set `TRIGGER_DESIGNER_DATA_DIR` before you start the program. This moves the whole app data folder, including the modules.
