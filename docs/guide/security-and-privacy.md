# Security and privacy

This page says plainly what the app is built to guarantee, how it does it, and what it does not promise. It is written for people who handle client data and workflows from other people.

[Back to the guide index](README.md)

## On this page

- [The short version](#the-short-version)
- [Your text is treated as data, never as code](#your-text-is-treated-as-data-never-as-code)
- [SQL is read-only and locked down](#sql-is-read-only-and-locked-down)
- [Databases are opened read-only](#databases-are-opened-read-only)
- [No network access](#no-network-access)
- [What the run records contain](#what-the-run-records-contain)
- [Hiding data values in messages](#hiding-data-values-in-messages)
- [What is not guaranteed](#what-is-not-guaranteed)
- [Opening a workflow you did not create](#opening-a-workflow-you-did-not-create)
- [If something goes wrong](#if-something-goes-wrong)

## The short version

| The app does | The app does not |
|---|---|
| Keep your data on your computer. It has no feature that sends data anywhere. | Encrypt your files, workflows or run records. |
| Turn what you type into settings, not into program code. | Stop a workflow from reading files you can read, or writing files where you can write. |
| Let SQL only read, and only the tables the node gives it. | Prove who a person is. The user name in a record is whatever Windows reports. |
| Open databases read-only. | Guard against someone with write access to the run-record folder who rewrites the whole chain. |
| Keep data values out of run records. | Keep every value out of every log (see below). |

## Your text is treated as data, never as code

A workflow is a set of settings. When you press **Run** (or while you edit, on the live sample), the app **generates Python code** from those settings and executes it. That is what the [run script](running-workflows.md#the-run-script) shows.

The rule that protects you is in `core/codegen_safe.py`: **text you type is never pasted into code as code.** Every value, such as a column name, a find-and-replace text, a file path or a filter value, is turned into a quoted *literal* (using Python's own `repr` or JSON string rules) before it is put in a code string. A column called `x'); import os #` is just a column with a strange name. Line breaks in a label or a comment cannot end a code comment and start a statement either.

How it is checked: the unit tests feed hostile text (quotes, backslashes, line breaks, null characters, fake code) to these helpers and confirm that it comes back identical and stays on one line, and a test scans the code generators for the unsafe patterns `'{x}'` and `"{x}"`, which are the classic ways to let text escape.

This is a property of the app's built-in nodes. There is **no custom-code node** in the application, so a workflow cannot contain a Python script of its own.

## SQL is read-only and locked down

Several nodes accept SQL text from you: **SQL Query**, **Formula**, **Multi-Field Formula** and the expression mode of **Filter**. All of them go through one guard (`core/sql_guard.py`) that applies two independent defences:

**1. The text is checked first.** A query is rejected unless it is exactly **one read-only SELECT**. In particular:

| Rejected | Code |
|---|---|
| Empty SQL | `TD-SHAPE-001` |
| More than one statement (anything after a `;`) | `TD-SHAPE-110` |
| Anything that is not a SELECT, including `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `ATTACH`, `COPY`, `INSTALL`, `LOAD`, `SET`, `PRAGMA`, `DESCRIBE`, `SHOW`, `EXPLAIN` | `TD-SHAPE-111` |
| Functions or syntax that touch files, the system or randomness: `read_*`, `glob`, `*_scan`, `sniff_csv`, `query`, `duckdb_*`, `pragma_*`, `current_setting`, `getenv`, `random`, `uuid`, `setseed`; `FROM 'file.csv'` and `FROM "dir/file.csv"`; dollar-quoted and escape strings; control characters | `TD-SHAPE-112` |
| SQL that does not parse | `TD-SHAPE-113` |
| More than 20,000 characters | `TD-SHAPE-114` |

Comments and string contents are blanked before the rules are applied, and look-alike characters (full-width letters, ligatures) are normalised, so they cannot be used to dodge the rules.

**2. The query then runs in a locked sandbox.** It runs on a **fresh, in-memory** DuckDB connection with **external access switched off** (no files, no network), **configuration locked** (the query cannot change its own settings), **one thread**, and, for the SQL Query node, a **2 GB memory limit**. The only data it can see is the frames the node hands to it.

**3. It is time-limited.** A query that runs longer than **25 seconds** is interrupted (`TD-SHAPE-115`).

Either layer alone could be bypassed. Together, the SQL of a workflow cannot read a file, write a file, load an extension, or change the engine's settings.

## Databases are opened read-only

A **File Input** that reads an SQLite or a DuckDB file opens it **read-only** (SQLite in read-only mode, DuckDB with the read-only flag), and only accepts a table name or a single SELECT. The app cannot change a database it reads.

## No network access

The application does not contact the internet, a license server, or any other computer: it has no update check, no telemetry and no cloud features, and the code contains no networking library (the only use of `socket` is to read your computer's name for the run record). SQL and databases are sandboxed from the network as described above. Your input files can of course live on a network drive, and the app reads and writes them like any other path.

## What the run records contain

Run records are designed to prove what happened **without holding your data**.

| In a record | Not in a record |
|---|---|
| File paths, sizes, modified times and **fingerprints** (SHA-256) | The rows or cell values of any file |
| Column names and column types, row counts | Any table data |
| Node **settings** (including filter text, find-and-replace text, thresholds) | Passwords (the app does not handle any) |
| The generated code (optional) | |
| User name and computer name (optional) | |
| For a failed node: the error and, unless hidden, a few of the offending values | |
| For an audit test: counts, rates, parameters and aggregate results | |

Two things to be aware of:

- **Settings can hold sensitive text.** If you type a customer's name into a Filter or a Find and Replace rule, it is in the settings, and so in the record and in the embedded code. Treat records as you would the workflow file itself.
- **Failed-node errors can carry sample values.** See the next section.

You can also turn off the user and machine name, the embedded code, and the whole recording in [Preferences](preferences.md).

## Hiding data values in messages

Error messages can quote the bad values they found ("contains 'abc' in row 3"). Tick **Edit > Settings > General > Error messages > Hide data values in error messages** to remove those values from:

- the node tooltip and the Problems dock,
- the text you copy with **Copy details**,
- the error stored in the run record,
- the technical text and stack trace (the offending values are scrubbed),
- the session log, which receives the same message.

The code, the column and the row number remain, so you can still find the problem.

What it does not do: it does not remove values from the **Data Preview**, from your output files, from the clipboard when you use **Copy as TSV**, or from values you typed into settings. The session log file (see [Files and formats](files-and-formats.md#other-files-the-app-creates)) is a diagnostic record: it can contain file paths, settings and detailed messages. Keep it with the same care as the workflow, and review it before sending it to anyone.

## What is not guaranteed

Be clear-eyed about the limits:

- **No encryption.** Workflows, run records, logs and preferences are plain files. Use disk or folder encryption and file permissions to protect them.
- **Tamper evidence, not tamper proofing.** The run-record chain detects edits, swaps and deletions in the middle. It cannot detect that the **newest** records were removed, and it is not a digital signature: someone who can write to the folder and recomputes every hash can make a different, valid-looking chain. Note the chain's **head hash** outside the folder after important runs. See [the hash chain](run-history-and-audit-trail.md#the-hash-chain-and-tamper-evidence).
- **Identity is not verified.** The "user" and "machine" in a record are what Windows reports, and can be switched off.
- **A workflow can read and write what you can.** A File Input can point at any file you may read; a File Output at any path you may write, and **overwrites an existing file without asking**.
- **The 30-second step limit and SQL limits are safety nets, not security boundaries.** A very heavy step can still use a lot of CPU or memory until it ends.
- **The preview is not redacted.** If someone can see your screen, they can see your data.
- **Spreadsheet formulas.** When you write data that begins with `=`, `+`, `-` or `@` to a CSV or Excel file and open it in Excel, Excel may treat it as a formula. Review output that came from untrusted data before opening it in Excel. (The workpaper export has its own handling; see [workpaper.md](workpaper.md).)
- **Dependencies.** The app relies on third-party libraries (Polars, DuckDB, Qt and others). Keep your installation up to date with your administrator.

## Opening a workflow you did not create

A `.tds` file is text that someone else wrote. What can it do?

**Safe by design:**

- It cannot contain code to run. The nodes in it are looked up by name from the nodes built into the app; an unknown node name becomes an inert **Unknown** placeholder.
- Its settings become literals in generated code (see above), and its SQL goes through the sandbox.
- Opening it does not write any file and does not send anything anywhere.

**Still worth care:**

- **Opening it reads files.** The live preview reads the first rows of the files its File Input nodes point at, and Excel, JSON and database inputs are read whole. If a workflow points at a huge file, opening it will be slow.
- **Running it writes files.** A File Output node can point at any location you can write to, replacing a file there. **Before you press Run on a workflow from someone else**, click each **File Output** node and read where it writes, and check each **File Input** for what it reads.
- **Paths are theirs.** The absolute paths were set on their computer. If a relative path exists on yours, it is used first (see [How file paths are stored](files-and-formats.md#how-file-paths-are-stored)). Check that you are about to process the data you think you are.
- **Read the settings.** A workflow can contain filters or formulas that silently drop or change rows. Open each node, or compare against the run script.
- **Newer files.** A file saved by a newer version loads with a warning and may drop settings this version does not understand; use **Save As** so the original stays intact.

A safe routine for an unknown workflow: copy it to a folder of your own, open it, check every File Input and File Output path, look at the Logs and Problems, and only then Run.

## If something goes wrong

| Symptom | What to do |
|---|---|
| A SQL node says "Only SELECT queries are allowed" or "not allowed (files, system or random)" | That is the guard working. Rewrite as a single SELECT without file functions. |
| I need random sampling in a query | Use the **Sample** audit node (with a seed) instead of `random()`. |
| A message shows a client value I must not share | Turn on **Hide data values in error messages**, recompute, and copy the details again. Delete the old copy. |
| A record shows a name I want removed | Records are write-once and read-only on purpose. Turn off **Record the user and machine name** for future runs. |
| I opened a workflow and I am worried about where it writes | Close it without running. Check each File Output. Nothing is written until Run. |
