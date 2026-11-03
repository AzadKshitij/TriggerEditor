# Split

![Split icon](../../assets/node_icons/Preparation/Split.svg){ .node-icon }

## Purpose

Divides the rows into two groups by percentage: an **Estimation** group and a **Validation** group (the usual build and test split).

## When to use it

Develop a rule on one part of the data and test it on the rest, or take a reproducible portion of a population.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| **E** (Estimation) | The first part, sized by Estimation % |
| **V** (Validation) | The rest |

## Settings

One section, **Split**. Its info line reads "Estimation rows first; the rest go to Validation."

| Control | Default | Effect |
|---|---|---|
| **Method** | Random | Random shuffles the rows first. Sequential keeps the input order. |
| **Estimation %** | 70 | 1 to 99: the share that goes to E. |
| **Random seed** | 42 | 0 to 2,147,483,647. Shown only for Random. The same seed on the same data always gives the same split. |

## Worked example

Ten rows numbered 1 to 10, Estimation % = 70.

- Sequential: E gets rows 1 to 7, V gets rows 8 to 10.
- Random with seed 42: E gets rows 2, 1, 7, 3, 6, 4, 5 (in shuffled order) and V gets 10, 9, 8.

## Edge cases and limits

- The split point is "row position below (number of rows minus 1) times the percentage", so sizes are **close to** the percentage, not always exact. With 5 rows and 50 percent, 2 rows go to E and 3 to V. With a single row, E is empty and the row goes to V.
- In Random mode rows come out in shuffled order, not input order.
- [Preview uses 100 rows](index.md#preview-vs-run): the preview splits the sample, Run splits the whole table, so the rows that land in E and V differ.
- This is not a statistical sampler; for audit samples use the Sample test in [Audit nodes](../audit/index.md).

## Messages you may see

`TD-SHAPE-004` ("Estimation percent must be between 1 and 99"), `TD-SHAPE-005`.

## Tips

Record the seed with your workpapers so someone else can reproduce the split.


Back to the [Preparation node index](index.md).
