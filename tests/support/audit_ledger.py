"""Deterministic synthetic general ledger for the audit-node tests.

``make_ledger()`` returns ``Ledger(frame, planted)`` with 2,413 rows: 2,013 ``GL``
rows (``je_number`` ``GL-000001..``) and 400 ``AP`` rows (``AP-0001..AP-0400``).
Every column is text, as File Input would read a CSV. The generator owns its
SplitMix64 stream and a fixed seed, so the frame is identical on every machine and
Python version; no library randomness is involved.

Anomalies are planted on disjoint row ranges so each expected count in
docs/plan/04-audit-test-nodes.md section 7.5 is exact. ``Ledger.planted`` maps a
name to the 1-based row numbers (of the pre-gap ``GL`` base list) it touched.

Helpers for the tests:

* ``make_ledger()``       -> ``Ledger``
* ``Ledger.gl`` / ``.ap`` -> the two ledger subsets (``DataFrame``)
* ``Ledger.write_csv(dir)`` -> writes ``ledger.csv``, ``ledger_gl.csv``,
  ``ledger_ap.csv`` and returns their paths
* ``ledger_lazy()``       -> ``LazyFrame`` of the whole ledger
* constants ``LEDGER_SEED, START, END, HOLIDAY, PERIOD_END, DESCRIPTIONS,
  ROWS, GL_ROWS, AP_ROWS``
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

LEDGER_SEED = 20260101
_MASK = (1 << 64) - 1
START, END = dt.date(2024, 2, 1), dt.date(2024, 3, 28)
HOLIDAY = dt.date(2024, 3, 29)
PERIOD_END = dt.date(2024, 3, 31)
DESCRIPTIONS = (
    "Office supplies",
    "Consulting fees",
    "Freight",
    "Software licence",
    "Utilities",
    "Travel",
    "Maintenance",
)
GL_ROWS, AP_ROWS = 2013, 400
ROWS = GL_ROWS + AP_ROWS
COLUMNS = [
    "je_number",
    "ledger",
    "posting_date",
    "effective_date",
    "amount",
    "vendor",
    "invoice_no",
    "description",
    "source",
]


class _Rng:
    """SplitMix64: ``u()`` is uniform in [0, 1), ``below(n)`` an int in [0, n)."""

    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK

    def u(self) -> float:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return ((z ^ (z >> 31)) >> 11) / float(1 << 53)

    def below(self, n: int) -> int:
        return int(self.u() * n)


@dataclass
class Ledger:
    frame: pl.DataFrame
    planted: dict[str, list[int]] = field(default_factory=dict)

    @property
    def gl(self) -> pl.DataFrame:
        return self.frame.filter(pl.col("ledger") == "GL")

    @property
    def ap(self) -> pl.DataFrame:
        return self.frame.filter(pl.col("ledger") == "AP")

    def write_csv(self, directory: Path | str) -> dict[str, Path]:
        """Write the whole ledger and both subsets; return ``{name: path}``."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        paths = {
            "all": out / "ledger.csv",
            "gl": out / "ledger_gl.csv",
            "ap": out / "ledger_ap.csv",
        }
        self.frame.write_csv(paths["all"])
        self.gl.write_csv(paths["gl"])
        self.ap.write_csv(paths["ap"])
        return paths


def _days(first: dt.date, last: dt.date) -> list[dt.date]:
    return [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]


def make_ledger(seed: int = LEDGER_SEED) -> Ledger:
    rng = _Rng(seed)
    all_days = _days(START, END)
    weekdays = [d for d in all_days if d.weekday() < 5]
    weekend_days = [d for d in all_days if d.weekday() >= 5]

    def clean_amount(low_exp: float, span: float) -> float:
        while True:
            v = round(10 ** (low_exp + span * rng.u()), 2)
            cents = round(v * 100)
            if cents % 100_000 == 0 or 4900 <= v < 5000 or 9800 <= v < 10000:
                continue
            return v

    def row(i: int) -> dict:
        d = weekdays[rng.below(len(weekdays))]
        return {
            "ledger": "GL",
            "posting_date": d,
            "effective_date": d,
            "amount": clean_amount(1, 5),
            "vendor": f"V{rng.below(400):03d}",
            "invoice_no": f"INV-{i:05d}",
            "description": DESCRIPTIONS[rng.below(7)],
            "source": "Auto",
        }

    base = [row(i + 1) for i in range(2000)]  # index k -> row number k+1
    planted: dict[str, list[int]] = {}

    def plant(name: str, idxs: range, **fields_by_k) -> None:
        planted[name] = [i + 1 for i in idxs]
        for k, i in enumerate(idxs):
            for f, fn in fields_by_k.items():
                base[i][f] = fn(k)
            if "posting_date" in fields_by_k and "effective_date" not in fields_by_k:
                base[i]["effective_date"] = base[i]["posting_date"]

    plant(
        "weekend",
        range(100, 115),
        posting_date=lambda k: weekend_days[k % len(weekend_days)],
    )
    plant("holiday", range(200, 204), posting_date=lambda k: HOLIDAY)
    plant(
        "round",
        range(300, 320),
        amount=lambda k: float(1000 * (1 + (k * 7) % 40)),
    )
    plant(
        "just_below",
        range(400, 413),
        amount=lambda k: 4900 + 12.5 * k if k < 8 else 9800.0 + 40 * (k - 8),
    )
    kw = ["Reversal of accrual"] * 4 + ["REVERSAL OF PRIOR PERIOD"] * 2
    kw += ["Plug adjustment"] * 3
    plant("keyword", range(500, 509), description=lambda k: kw[k])
    plant(
        "after_period",
        range(600, 607),
        posting_date=lambda k: dt.date(2024, 4, 2),
        effective_date=lambda k: dt.date(2024, 3, 28),
    )
    plant("manual", range(700, 725), source=lambda k: "Manual")
    plant(
        "triple",
        range(800, 801),
        posting_date=lambda k: weekend_days[0],
        amount=lambda k: 20000.0,
        source=lambda k: "Manual",
    )

    def next_weekday(d: dt.date) -> dt.date:
        i = weekdays.index(d)
        return weekdays[i + 1] if i + 1 < len(weekdays) else weekdays[i - 1]

    copies: list[dict] = []

    def copy_of(i: int, **over) -> dict:
        c = dict(base[i])
        c.update(over)
        return c

    for i in range(900, 910):  # 10 exact pairs
        copies.append(copy_of(i))
    for i in (910, 911):  # 2 exact triples
        copies += [copy_of(i), copy_of(i)]
    for i in range(920, 925):  # 5 amount-shifted (+0.30)
        copies.append(copy_of(i, amount=round(base[i]["amount"] + 0.30, 2)))
    for i in range(930, 935):  # 5 date-shifted (next weekday)
        shifted = next_weekday(base[i]["posting_date"])
        copies.append(copy_of(i, posting_date=shifted, effective_date=shifted))
    planted["dup_sources"] = [
        i + 1
        for i in list(range(900, 910))
        + [910, 911]
        + list(range(920, 925))
        + list(range(930, 935))
    ]
    gl = base + copies  # 2024 rows
    for n, r in enumerate(gl, start=1):
        r["je_n"] = n
    missing = set(range(1000, 1010)) | {1500} | set(range(1800, 1803))
    gl = [r for r in gl if r["je_n"] not in missing]  # 2024 - 14 = 2010 rows
    pos = {r["je_n"]: i for i, r in enumerate(gl)}
    for a in (1100, 1200, 1300, 1400):  # swap neighbours -> out of order
        i, j = pos[a], pos[a + 1]
        gl[i], gl[j] = gl[j], gl[i]
    repeats = []
    for n, num in enumerate((100, 200, 300), start=1):  # repeated numbers at the end
        r = row(5000 + n)
        r["je_n"] = num
        repeats.append(r)
    gl += repeats  # 2013 GL rows
    ap = []
    for i in range(400):  # Benford-violating ledger
        d = weekdays[rng.below(len(weekdays))]
        while True:
            v = round(5000 + 4800 * rng.u(), 2)
            if round(v * 100) % 100_000 != 0:
                break
        ap.append(
            {
                "ledger": "AP",
                "je_n": i + 1,
                "posting_date": d,
                "effective_date": d,
                "amount": v,
                "vendor": f"V{rng.below(400):03d}",
                "invoice_no": f"APINV-{i + 1:04d}",
                "description": DESCRIPTIONS[rng.below(7)],
                "source": "Auto",
            }
        )
    out = [{**r, "je_number": f"GL-{r['je_n']:06d}"} for r in gl]
    out += [{**r, "je_number": f"AP-{r['je_n']:04d}"} for r in ap]
    frame = pl.DataFrame(
        {
            "je_number": [r["je_number"] for r in out],
            "ledger": [r["ledger"] for r in out],
            "posting_date": [r["posting_date"].isoformat() for r in out],
            "effective_date": [r["effective_date"].isoformat() for r in out],
            "amount": [f"{r['amount']:.2f}" for r in out],  # text, as a CSV read
            "vendor": [r["vendor"] for r in out],
            "invoice_no": [r["invoice_no"] for r in out],
            "description": [r["description"] for r in out],
            "source": [r["source"] for r in out],
        }
    ).select(COLUMNS)
    return Ledger(frame=frame, planted=planted)


def ledger_lazy(seed: int = LEDGER_SEED) -> pl.LazyFrame:
    return make_ledger(seed).frame.lazy()


if __name__ == "__main__":
    ledger = make_ledger()
    print(ledger.frame.shape, {k: len(v) for k, v in ledger.planted.items()})
