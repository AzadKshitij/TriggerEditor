# Comment

![Comment icon](../../assets/node_icons/Report/Comment.svg){ .node-icon }

## Purpose

A Comment is a note on the canvas. It never runs, has no inputs or outputs, and has no effect on the data. Its text is saved with the workflow.

## When to use it

- Explain why a filter or a tolerance was chosen ("tolerance 0.50 agreed with client, see email of 3 March").
- Mark a step as "to be reviewed", or leave a question for the reviewer.
- Describe a group of nodes.
- Explain the process in an Excel workpaper: every Comment on the canvas is copied word for word to the **Workflow** sheet of a [workpaper](../../guide/workpaper.md).

## Inputs and outputs

None. A Comment has no sockets, so it cannot be connected to other nodes. Its summary in the dock reads "0 inputs · 0 outputs · never runs".

## Settings

| Control | What it does | Default |
|---|---|---|
| **Note** (a large text box, placeholder "Note for the reviewer") | The text of the comment, as many lines as you like. Tooltip: "The first line is shown above the node." | Empty |

The first non-blank line of the note, cut to its first 60 characters, is shown as a label above the node on the canvas, so the canvas stays readable. The rest of the text is only visible when you select the node.

Editing a Comment does not make the workflow re-evaluate and does not mark anything as out of date.

## Worked example

You type:

```
Tolerance of 0.50 agreed with the client
Source: bank rec policy, section 4
```

The node shows `Tolerance of 0.50 agreed with the client` above it. Select the node to read both lines.

## Edge cases and limits

- **Label length.** Only the first 60 characters of the first line are shown on the canvas. The note itself is not limited.
- **Empty note.** No label is shown.
- **Running a workflow** does nothing for a Comment: its generated code is only the line `# Comment (not executed)`.
- **Privacy.** The note is stored in the workflow file as plain text. Do not put confidential details in a workflow you will share outside the team.

## Errors you may see

None. A Comment cannot fail.

## Tips

- Start the note with a short title on the first line; that line is what people see on the canvas.
- Place one Comment above each group of nodes that does one job (for example "Step 2: match bank to ledger").


Back to the [Report node index](index.md).
