"""The HTML report and the shared wording helpers (core/profile_report.py)."""

from __future__ import annotations

import re

import polars as pl
import pytest

from tests.support.profile_fixtures import FX
from trigger_designer.core import profile as pf
from trigger_designer.core import profile_report as rep

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def prof() -> pf.DataProfile:
    return pf.profile_frame(FX)


def test_status_text_says_data_not_full_data(prof):
    assert rep.status_text(prof) == "Data: 10 rows"
    assert "Full" not in rep.status_text(prof)


def test_status_text_names_a_sample():
    big = pl.DataFrame({"n": list(range(3000))})
    head = pf.profile_frame(
        big, settings=pf.ProfileSettings(sample_mode="head", sample_rows=1000)
    )
    assert rep.status_text(head) == "Sample: first 1,000 rows"
    rnd = pf.profile_frame(
        big,
        settings=pf.ProfileSettings(sample_mode="random", sample_rows=1000, seed=7),
    )
    assert rep.status_text(rnd) == "Sample: random 1,000 rows (seed 7)"


def test_every_flag_has_a_label():
    assert set(rep.FLAG_LABELS) == set(pf.FLAG_ORDER)


def test_min_max_label_for_parsed_dates_is_not_text_order(prof):
    when = next(c for c in prof.columns if c.name == "when")
    labels = dict(rep.detail_rows(when))
    assert "Min / max" in labels
    assert "Min / max (text order)" not in labels
    flag = next(c for c in prof.columns if c.name == "flag")  # Y/N text
    assert "Min / max (text order)" in dict(rep.detail_rows(flag))


def test_html_report_is_self_contained(prof):
    html = rep.profile_to_html(prof, "Ledger profile")
    assert html.startswith("<!doctype html>")
    assert "<title>Ledger profile</title>" in html
    assert "<script" not in html
    # no external resources: it must open offline and attach to a workpaper
    assert not re.search(r"""(src|href)=["']https?://""", html)
    assert "@import" not in html


def test_html_report_shows_every_column_with_its_own_card(prof):
    html = rep.profile_to_html(prof)
    for position, name in enumerate(FX.columns, start=1):
        assert f'id="col-{position}"' in html, name
        assert f'href="#col-{position}"' in html, name
        assert f">{name}<" in html or f"{name} <small>" in html
    assert html.count('class="card"') == len(FX.columns)


def test_html_report_carries_the_figures(prof):
    html = rep.profile_to_html(prof)
    assert "Data: 10 rows" in html
    assert "10 columns" in html
    assert "mixed numbers and text" in html  # the amount column's flag
    assert "numbers stored as text" in html
    assert "Most frequent values" in html
    assert "Distribution" in html  # qty has a histogram


def test_html_report_escapes_column_names_and_values():
    frame = pl.DataFrame({"<b>x</b>": ["<script>alert(1)</script>", "a & b"]})
    html = rep.profile_to_html(pf.profile_frame(frame), "<i>t</i>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<b>x</b>" not in html
    assert "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<i>t</i>" not in html
    assert "a &amp; b" in html


def test_html_report_marks_stray_spaces():
    frame = pl.DataFrame({"s": [" padded ", "plain"]})
    html = rep.profile_to_html(pf.profile_frame(frame))
    assert '<span class="ws">·</span>padded<span class="ws">·</span>' in html


def test_html_report_of_an_empty_profile_does_not_fail():
    html = rep.profile_to_html(pf.profile_frame(pl.DataFrame()), "Empty")
    assert "No columns" in html


def test_html_report_from_a_run_table_matches_the_live_report(prof):
    rebuilt = pf.profile_from_frame(prof.to_frame())

    def strip(text: str) -> str:
        return re.sub(r"Generated [\d\-: ]+", "", text)

    assert strip(rep.profile_to_html(rebuilt, "T")) == strip(
        rep.profile_to_html(prof, "T")
    )
