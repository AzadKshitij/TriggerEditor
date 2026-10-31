# Join nodes

These nodes combine two or more tables. Pick the one that matches the question you are asking.

| If you want to... | Use |
|---|---|
| Put the rows of one table under the rows of another (two inputs) | [Append](append.md) |
| Stack any number of tables, with control over how columns line up | [Union](union.md) |
| Look up matching rows by an exact key, and see what matched, what only the left has and what only the right has | [Join](join.md) |
| Match two lists on keys plus an amount (with a tolerance) and a date window, and report the differences | [Reconcile](reconcile.md) |
| Match names or descriptions that are almost, but not exactly, the same | [Fuzzy Match](fuzzy-match.md) |

## Nodes in this family

| Icon | Node | What it does |
|---|---|---|
| ![Join](../../assets/node_icons/Join/Join.svg) | **[Join](join.md)** | Combines two tables on matching key columns and also gives the unmatched rows from each side (outputs `L`, `J`, `R`). |
| ![Append](../../assets/node_icons/Join/Append.svg) | **[Append](append.md)** | Puts the rows of a second table underneath the first. |
| ![Union](../../assets/node_icons/Join/Union.svg) | **[Union](union.md)** | Stacks two or more tables, matching columns by name or by a mapping you set. |
| ![Reconcile](../../assets/node_icons/Join/Reconcile.svg) | **[Reconcile](reconcile.md)** | Matches two tables on keys plus an amount tolerance and/or date window; gives matched pairs, both unmatched sides and a summary. |
| ![Fuzzy Match](../../assets/node_icons/Join/FuzzyMatch.svg) | **[Fuzzy Match](fuzzy-match.md)** | Pairs similar text (such as vendor and supplier names) from two tables by similarity score. |

## Before you start: left, right and the 100-row preview

- **Left and right.** Append, Join, Reconcile and Fuzzy Match have two input sockets. The first socket (top) is the **left** input and the second socket is the **right** input. "Input 1" in an error message means the left one and "Input 2" the right one. Swapping them changes which side's columns come first and which outputs are "left only" and "right only".
- **Output sockets are lettered.** Join has `L`, `J`, `R`. Reconcile has `M`, `L`, `R`, `S`. Fuzzy Match has `M`, `L`, `R`. Connect each socket to the node you want to receive that output. The summary line at the top of the Config Dock spells out what each letter means.
- **Live preview versus Run.** While you edit, each input is cut to its first 100 rows, so a match that needs row 101 will not appear in the preview. Run uses all rows. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Row order is not guaranteed.** After a join or match, rows may come out in a different order from run to run. If order matters, add a Sort node (see [Preparation nodes](../preparation/index.md)) after it.

---

