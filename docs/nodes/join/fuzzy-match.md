# Fuzzy Match

![Fuzzy Match icon](../../assets/node_icons/Join/FuzzyMatch.svg){ .node-icon }

## Purpose

Fuzzy Match pairs rows whose text is similar but not identical: `Acme Inc.` and `ACME, Inc`, `Initech LLC` and `Initec`. Each pair gets a score between 0 and 1 (1 is identical), and only pairs at or above your minimum are kept.

## When to use it

- Vendor names typed differently in two systems (vendor master to payments).
- Employee names, customer names, addresses and descriptions where an exact [Join](join.md) misses real matches.

Use [Join](join.md) or [Reconcile](reconcile.md) when the key is exact. Fuzzy results are suggestions: review them.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left) | The first list. |
| Input 2 (right) | The second list. |
| Output `M` | **Matched.** `Match_ID`, `Match_Score`, then every left column, then every right column (a right column with the same name as a left column gets `_right`). |
| Output `L` | **Left unmatched.** Left rows with no pair at or above the minimum score (and rows with empty text). |
| Output `R` | **Right unmatched.** The same for the right. |

## Settings

**Compare**

| Control | What it does | Default |
|---|---|---|
| **Left text** / **Right text** | The text columns to compare. Only text columns are listed. | Empty |
| **Algorithm** | **Jaro-Winkler**: gives extra credit to names that start the same way; good for names. **Levenshtein ratio**: counts the single-character edits between the texts; good for codes and descriptions. | Jaro-Winkler |
| **Minimum score** | Pairs scoring below this are dropped. 0.01 to 1.0 in steps of 0.01. Hint: "1.0 is identical; pairs scoring below are dropped." | 0.85 |
| **Ignore Inc/Ltd/LLC** (checkbox) | Removes company-form words before comparing: inc, incorporated, ltd, limited, llc, plc, corp, corporation, co, company, gmbh, ag, sa, pty, pvt, bv, nv, lp, llp. | On |
| **Pairs** | **One to one**: each row is used at most once; the best-scoring pairs win. **Best per left row**: each left row gets its best right row (a right row can be used several times). **All pairs**: every pair at or above the minimum. | One to one |

Hint on the form: "Text is lower-cased and punctuation is ignored before comparing. Empty text never matches."

**Speed**

| Control | What it does | Default |
|---|---|---|
| **Block on** | Only rows that share a "block" are compared, which keeps large inputs fast. **First characters**: rows must start with the same first few letters. **First word**: rows must share the first word. **Nothing (small data)**: compare everything with everything. | First characters |
| **Characters** | How many leading characters count for the block (1 to 10). Shown for First characters. | 3 |
| **Must also match** (list, up to 5) | Extra column pairs (a **Left column** and a **Right column**) that must be equal, for example country or city. Trimmed and compared as lower-case text. | Empty |

Hint: "Only rows that share the block are compared, which keeps large inputs fast. Extra columns are trimmed and compared as lower-case text."

**Limits & output** (collapsed): "Up to 5,000,000 candidate pairs (1,000,000 with no blocking). The live preview uses the first 100 rows of each input; Run gives the full result."

How text is prepared before scoring: lower-case; every character that is not a letter or digit becomes a space; the company words above are removed (if the checkbox is on); repeated spaces are collapsed. So `ACME, Inc` and `Acme Inc.` both become `acme`.

## Worked example

Left (vendor master):

| Vendor | Spend |
|---|---|
| Acme Inc. | 100 |
| Globex Corporation | 200 |
| Initech LLC | 300 |
| Umbrella Ltd | 400 |

Right (suppliers):

| Supplier | Country |
|---|---|
| ACME, Inc | US |
| Globex Corp | DE |
| Initec | US |
| Wayne Enterprises | UK |

Settings: **Left text** `Vendor`, **Right text** `Supplier`, defaults otherwise. Output `M`:

| Match_ID | Match_Score | Vendor | Spend | Supplier | Country |
|---|---|---|---|---|---|
| 1 | 1.0 | Acme Inc. | 100 | ACME, Inc | US |
| 2 | 1.0 | Globex Corporation | 200 | Globex Corp | DE |
| 3 | 0.9714 | Initech LLC | 300 | Initec | US |

Output `L`:

| Vendor | Spend |
|---|---|
| Umbrella Ltd | 400 |

Output `R`:

| Supplier | Country |
|---|---|
| Wayne Enterprises | UK |

With **Algorithm** Levenshtein ratio, the third pair scores 0.8571 instead of 0.9714.

## Edge cases and limits

- **Candidate pairs: up to 5,000,000** (1,000,000 with **Block on** = Nothing). More stops the run. The count is made before any scoring, so it fails fast.
- **Live preview:** 100 rows of each input. Run uses all rows and keeps both inputs in memory. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Blocking can hide real matches.** With First characters = 3, `The Acme Trading Co` and `Acme Trading Company` are never compared (they start with `the` and `acm`). Use First word, shorten Characters, remove leading words first, or use Nothing on a small table. With Nothing and a minimum of 0.7, that pair is found, with a score of 0.8333.
- **Must also match** is exact (after trimming and lower-casing). A wrong spelling in the extra column also hides a match.
- **Empty text** (null or only spaces and punctuation) never matches and the row goes to `L` or `R`.
- **Only text columns** can be chosen. Convert numbers to text with a Select node first.
- **Ties** are broken the same way every time (higher score first, then row order), so a re-run gives the same result.
- **Score** is rounded to four decimals.
- **Column names.** `Match_ID` and `Match_Score` are reserved: a left column with one of those names is renamed with a `_2` suffix.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-001` | "Pick the text column on both sides". | Choose **Left text** and **Right text**. |
| `TD-SHAPE-004` | A setting is out of range (Minimum score must be above 0 and at most 1; Characters 1 to 10; at most 5 extra match columns). | Pick a value inside the range. |
| `TD-SHAPE-081` | More than 5,000,000 possible pairs. | Use more Characters, or add a **Must also match** column. |
| `TD-SHAPE-082` | **Block on** is Nothing and the tables have more than 1,000,000 row pairs (for example 1,001 by 1,000). | Turn on prefix or first-word blocking. |
| `TD-SHAPE-003` | A chosen column is no longer in the input. | Select the column again. |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

## Tips

- Start at the default 0.85 and read `M` sorted by `Match_Score`. Look at the lowest scores: that is where wrong matches live. Raise the minimum until the lowest rows are right, then look at `L` and `R` for real names that were missed.
- Add a **Must also match** column (country, tax number, city) to cut false matches and make large runs faster.
- Names with a leading "The" or a title defeat prefix blocking. Use First word, or strip those words with a Find and Replace node first.
- After matching, use the pairs in `M` as a mapping table and Join on `Match_ID`, or keep the pair list as evidence in your working paper.


Back to the [Join node index](index.md).
