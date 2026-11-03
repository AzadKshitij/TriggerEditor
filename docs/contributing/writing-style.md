# Writing node pages

Every node in the palette has one page under `docs/nodes/<family>/`. A reader
arrives from the node index or from a search, wants to know whether the node
solves their problem, and needs the exact settings. They do not need to know how
the node is built.

## Who you are writing for

An auditor or analyst building a pipeline in the app. They know their data and
their question. They may not know what a socket is, and they will not read a
paragraph that starts with an engine name.

Write in the second person. Name controls exactly as the Config Dock shows them.
Use **bold** for a control or a panel name and `code font` for a message code, a
column name or a file name.

## What never appears on a node page

- Class names, module paths, or any path under `src/`.
- Engine names and internals: no mention of the data frame library, the SQL
  engine, lazy plans, plans, or how a node is evaluated.
- Design notes, performance measurements, or refactoring plans. Those belong in
  `docs/internal/`.

If you need to explain behaviour, describe what the user sees: rows in a socket,
a column that appears, a badge, a message.

## The page template

Each page uses these sections, in this order. Drop a section only when the node
genuinely has nothing to say there.

1. **Title** - the node name exactly as the palette shows it.
2. **Opening line** - one sentence: what the node does, phrased as a task.
3. **Purpose** - two or three sentences. What comes out, and what question it
   answers.
4. **When to use it** - the case it fits, and the neighbouring node to use
   instead when it does not fit.
5. **Inputs and outputs** - the sockets and their letters, and which rows or
   columns leave by each one. This is the section readers re-read, so be exact.
6. **Settings** - a table with four columns: Control, What it does, Default,
   When to change it. One row per control, in dock order. Include the icon-only
   buttons by their tooltip name.
7. **Worked example** - a small table in, a small table out, and one sentence
   saying what changed. Keep it to five rows or fewer.
8. **Edge cases and limits** - empty input, missing columns, type surprises,
   caps, and anything that behaves differently in a preview.
9. **Messages you may see** - the user-visible codes, what they mean in plain
   language, and the fix. A table with Code, Message, What to do.
10. **Tips** - one or two sentences, only if they add something the sections
    above do not.
11. **Related nodes** - two or three links, each with the reason to follow it.

End every page with a link back to the family index:

```markdown
Back to the [Preparation node index](index.md).
```

## Preview versus Run

Every node page states the rule in its own words, in Edge cases and limits:

> While you edit, the node works on the first 100 rows and shows at most 100
> output rows. A Run uses every row. Trust the Run.

Do not paste the same paragraph into all 39 pages. Say what the 100-row sample
means for this node: a Count can only say 100, a Pivot can miss a header, an
audit test can miss a duplicate that sits on row 4,000.

## Icons

Node icons are copied into `docs/assets/node_icons/<Family>/<Name>.svg`. A page
in `docs/nodes/<family>/` refers to one like this:

```markdown
![Duplicates](../../assets/node_icons/Audit/Duplicates.svg)
```

A family index page uses the same path because it sits in the same directory.
Never link into `src/`: the built site cannot serve it.

## Links

- To another node in the same family: `[Filter](filter.md)`.
- To a node in another family: `[Aggregate](../preparation/aggregate.md)`.
- To the family index: `[Preparation nodes](index.md)`.
- To a guide page: `[Running workflows](../../guide/running-workflows.md)`.
- To a section on the same page: `[Settings](#settings)`.

Use relative links only. An absolute path or a link starting with `/` fails the
strict build.

## Before you commit a page

1. Open the node in the app and read every control in the Config Dock. The page
   must list all of them.
2. Check each message code against the app, not against an older note.
3. Run `uv run --group docs mkdocs build --strict` and fix what it reports.
4. Read the page once as a user who has never opened the app. If a sentence
   needs the source code to make sense, rewrite it.
