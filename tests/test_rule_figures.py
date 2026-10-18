"""The light QC's rule subsections and their figures, and the reports around
them (stream S3 of ``docs/paradigm-analyses-plan.md``).

On a firmware 4.0.0 recording with a ``Program.txt``, the report's
*Optogenetic light QC* gains one subsection per Paradigm (:mod:`pyflic.base.
rule_figures`): the rule in words, the family's checks per Linkage Group and a
figure of the measured light against the rule's setting.  The proof is the
simulator (``v4_fixtures``): every section appears exactly when its family is
in the program; its numbers are the light QC's; each figure draws on its
spec and shows the failing points of an injected fault (``program_paradigms``,
``on_ms_faults``).  Then the reports, member and Project, build with no red
box on every simulator spec, PyMCU's simulated recording and the quiet bench
run, rendered and read as ``test_one_treatment_report`` reads them.
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import shutil
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import opto_program as op
from pyflic.base import paradigm_families as pfam
from pyflic.base import program_timeline
from pyflic.base import report_content as rc
from pyflic.base import report_layout as rl
from pyflic.base import rule_checks as rcheck
from pyflic.base import rule_figures as rf
from pyflic.base.yaml_config import load_experiment_yaml

import v4_fixtures as vf

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

#: Short runs: the rules do not depend on the length.
MINUTES = 8.0


@lru_cache(maxsize=None)
def _family() -> dict:
    return vf.family_specs(MINUTES)


SPECS = {
    **{key: (lambda key=key: _family()[key]) for key in vf.FAMILY_SPEC_KEYS},
    "one_of_each": lambda: vf.one_of_each_spec(minutes=MINUTES),
    "stress": vf.stress_spec,
    "choice": lambda: vf.choice_pr_spec(minutes=12.0),
    "yoked": lambda: vf.yoked_controls_spec(minutes=MINUTES),
    "repeating": lambda: vf.repeating_open_loop_spec(minutes=20.0),
}


@lru_cache(maxsize=None)
def sim(name: str):
    spec = SPECS[name]()
    return spec, vf.simulate(spec)


def _config(dfm_ids) -> dict:
    """A Custom two-well config, A wells on the left, every chamber assigned."""
    params = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
              "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}
    return {"global": {"chamber_layout": "two_well", "transform_licks": False,
                       "params": params},
            "dfms": [{"id": int(i), "chambers": {c: ("Ctrl" if c % 2 else "Exp")
                                                 for c in range(1, 7)}}
                     for i in dfm_ids]}


def _quiet_load(root: Path):
    with contextlib.redirect_stdout(io.StringIO()):
        return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


def load(root: Path, name: str, **kw):
    """The recording *name* written to *root* with the faults of *kw*, loaded."""
    spec, results = sim(name)
    root.mkdir(parents=True, exist_ok=True)
    vf.write_v4_recording(root / "data", spec, results=results, **kw)
    (root / "flic_config.yaml").write_text(
        yaml.safe_dump(_config([d.dfm_id for d in spec.dfms]), sort_keys=False))
    return _quiet_load(root)


@pytest.fixture(scope="module")
def clean(tmp_path_factory):
    """``get(name) -> experiment``, each clean recording loaded once."""
    cache: dict = {}

    def get(name: str):
        if name not in cache:
            cache[name] = load(tmp_path_factory.mktemp(name), name)
        return cache[name]

    return get


def _section(sections, name: str, *, acclimation: bool = False) -> rf.RuleSection:
    return next(s for s in sections if s.name == name and s.acclimation == acclimation)


def _texts(doc: rl.ReportDocument) -> str:
    return " ".join(t.get_text() for fig in doc._render_pages() for t in fig.texts)


def _no_error(text: str) -> None:
    assert "could not be drawn" not in text, re.findall(r"could not be drawn[^.]*", text)
    assert "Could not evaluate" not in text


# ---------------------------------------------------------------------------
# The sections
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", list(SPECS))
def test_a_section_appears_exactly_when_its_family_is_in_the_program(clean, name):
    """One section per Paradigm (its Acclimation apart, the Wells set On
    under another Paradigm as one), in FAMILY_ORDER then by name; their
    families are the program's (paradigm_families.families_in)."""
    e = clean(name)
    sections = rf.rule_sections(e.opto)
    ids = rf.rule_dfms(e.opto)
    assert ids == e.opto.dfm_ids()
    assert {s.family for s in sections} == set(pfam.families_in(e.opto_program, ids))
    order = [(pfam.FAMILY_ORDER.index(s.family), s.paradigm is None, s.name.lower(),
              s.acclimation) for s in sections]
    assert order == sorted(order)
    ## A Paradigm with Acclimation has its Acclimation section, closed loop.
    for p in {iv.paradigm.name: iv.paradigm for d in ids
              for iv in e.opto_program.section(d).intervals if iv.trigger_wells()}.values():
        if p.acclimation and p.type in op.ACCLIMATION_PARADIGMS:
            assert _section(sections, p.name, acclimation=True).family == pfam.CLOSED_LOOP
    ## Every figure kind is its family's (fixed length: its branch's).
    for s in sections:
        assert s.figure == (None if s.family == pfam.OPEN_LOOP
                            else pfam.rule_figure(s.paradigm.mode, acclimation=s.acclimation))


#: The QC table's columns each section reports, summed over a group's
#: Paradigms as the light QC sums them.
_SUMMED = (rcheck.SHORT_COLUMN, rcheck.OVER_MAX_ON_COLUMN, rcheck.CUT_OFFS_COLUMN,
           rcheck.WRONG_LENGTH_COLUMN, rcheck.LOCKOUT_COLUMN, rcheck.MISSED_CONTACTS_COLUMN,
           rcheck.SERIES_COLUMN, rcheck.NON_FEEDING_DARK_COLUMN)


@pytest.mark.parametrize("name", ["closed_max", "fixed_interval", "non_feeding",
                                  "exponential", "restart", "one_of_each", "stress"])
def test_the_numbers_are_the_light_qcs(clean, name):
    """Per Linkage Group, each check's column summed over the sections is
    the QC table's (which sums it over the group's Paradigms); a relight
    delay is the QC's where one NonFeeding Paradigm gives it; a group's
    verdict in a section names only flags the QC table raised for it."""
    e = clean(name)
    qc = e.opto.qc_table().set_index(["DFM", "Group"])
    sections = rf.rule_sections(e.opto)
    rows = pd.concat([s.groups.assign(_family=s.family) for s in sections
                      if s.family != pfam.OPEN_LOOP], ignore_index=True)
    for column in _SUMMED:
        if column not in rows.columns:
            continue
        mine = rows.groupby(["DFM", "Group"])[column].apply(
            lambda v: pd.to_numeric(v, errors="coerce").sum(min_count=1))
        for key, value in mine.items():
            theirs = pd.to_numeric(pd.Series([qc.loc[key, column]]), errors="coerce").iloc[0]
            if pd.isna(value):
                assert pd.isna(theirs), (key, column)
            else:
                assert value == pytest.approx(float(theirs)), (key, column)
    relight = rows.dropna(subset=[rcheck.RELIGHT_DELAY_COLUMN]) \
        if rcheck.RELIGHT_DELAY_COLUMN in rows.columns else rows.iloc[0:0]
    for (dfm, group), sub in relight.groupby(["DFM", "Group"]):
        if len(sub) == 1:
            assert sub[rcheck.RELIGHT_DELAY_COLUMN].iloc[0] == \
                pytest.approx(float(qc.loc[(dfm, group), rcheck.RELIGHT_DELAY_COLUMN]))
    for r in rows.itertuples(index=False):
        mine = [f for f in str(r.Flags).split(", ") if f]
        assert set(mine) <= set(str(qc.loc[(r.DFM, r.Group), "Flags"]).split(", "))


@pytest.mark.parametrize("name", ["closed_max", "fixed_interval", "non_feeding",
                                  "exponential", "restart", "one_of_each"])
def test_the_marks_are_the_checks_counts(clean, name):
    """Row by row, the figures' marks add up to the section's columns: the
    lengths that break the rule, the lockout pairs, the series."""
    for s in rf.rule_sections(clean(name).opto):
        if s.family == pfam.OPEN_LOOP:
            continue
        a = s.activations
        for (dfm, group), g in s.groups.groupby(["DFM", "Group"]):
            mine = a[(a["DFM"] == dfm) & (a["Group"] == group)]
            row = g.iloc[0]
            assert int(mine["Judged"].sum()) == row["Judged"], (s.title, dfm, group)
            breaks = mine["Breaks"].astype(str)
            for flag, column in ((rcheck.SHORT_ACTIVATIONS, rcheck.SHORT_COLUMN),
                                 (rcheck.MAX_ON_EXCEEDED, rcheck.OVER_MAX_ON_COLUMN),
                                 (rcheck.WRONG_ACTIVATION_LENGTH, rcheck.WRONG_LENGTH_COLUMN)):
                if column in row.index and pd.notna(row[column]):
                    assert int((breaks == flag).sum()) == int(row[column]), (s.title, flag)
            if rcheck.LOCKOUT_COLUMN in row.index and pd.notna(row[rcheck.LOCKOUT_COLUMN]):
                assert int(mine["SpacingBreaks"].sum()) == int(row[rcheck.LOCKOUT_COLUMN])
            if rcheck.SERIES_COLUMN in row.index and pd.notna(row[rcheck.SERIES_COLUMN]):
                assert int(mine["SeriesBreaks"].sum()) == int(row[rcheck.SERIES_COLUMN])


def test_a_section_reads_its_rule_and_its_settings(clean):
    sections = rf.rule_sections(clean("one_of_each").opto)
    assert [s.title for s in sections] == [
        "Open (open loop; DFM 1)", "Closed (closed loop; DFM 2, 5)",
        "PR10 Acclimation (closed loop; DFM 5)", "FR5 (fixed length, ratio; DFM 6)",
        "Interval1Min (fixed length, interval; DFM 3)", "PR10 (fixed length, ratio; DFM 5)",
        "NotFeeding (non-feeding; DFM 4)"]
    closed = _section(sections, "Closed")
    assert closed.sentence().startswith("Closed (closed loop): lit during contact and for "
                                        "500 ms after; at most 2500 ms per light period")
    assert list(rf.section_table(closed).columns) == [
        "DFM", "Group", "Wells", "Treatment", "Short", "Over MaxOnMs", "Cut-offs", "Judged",
        "Not judged", "Verdict"]
    assert (closed.groups["Verdict"] == "ok").all() and len(closed.groups) == 12
    ## Fixed length shows its branch's checks only.
    interval = rf.section_table(_section(sections, "Interval1Min"))
    assert {"Wrong length", "Lockout broken", "Missed contacts"} <= set(interval.columns)
    assert "Series mismatches" not in interval.columns
    ratio = rf.section_table(_section(sections, "FR5"))
    assert {"Wrong length", "Series mismatches"} <= set(ratio.columns)
    assert "Lockout broken" not in ratio.columns
    ## Open loop: its lowest lit fraction per group, no Activations.
    assert _section(sections, "Open").groups[rcheck.OPEN_LOOP_COLUMN].min() > 0.95


# ---------------------------------------------------------------------------
# The figures
# ---------------------------------------------------------------------------

#: (spec, Paradigm, Acclimation, figure kind, its parts).
FIGURES = [
    ("closed_max", "CL500", False, pfam.FIGURE_ACTIVATION_LENGTH, ["lit"]),
    ("fixed_interval", "FI10s", False, pfam.FIGURE_ONSET_SPACING, ["spacing", "lit"]),
    ("fixed_interval", "FI500", False, pfam.FIGURE_ONSET_SPACING, ["spacing", "lit"]),
    ("fixed_interval", "FI500", True, pfam.FIGURE_ACTIVATION_LENGTH, ["lit"]),
    ("exponential", "PRExp", False, pfam.FIGURE_REQUIREMENT_SERIES, ["series", "lit"]),
    ("exponential", "PRExp", True, pfam.FIGURE_ACTIVATION_LENGTH, ["lit"]),
    ("non_feeding", "NF1000", False, pfam.FIGURE_RELIGHT_DELAY, ["relight"]),
    ("non_feeding", "NFMax5s", False, pfam.FIGURE_RELIGHT_DELAY, ["relight", "lit"]),
    ("restart", "FR3", False, pfam.FIGURE_REQUIREMENT_SERIES, ["series", "lit"]),
    ("restart", "CL", False, pfam.FIGURE_ACTIVATION_LENGTH, ["lit"]),
]


def _drawn_breaks(figure) -> int:
    """How many breaking values a rule figure draws in the failure colour:
    its histogram's ``breaks the rule`` rows, or its series' red points."""
    data = figure.data
    if "Status" in data.columns:
        return int((data["Status"].astype(str) == rf.BREAKS).sum())
    red = [layer.data for layer in figure.layers
           if isinstance(layer.data, pd.DataFrame)
           and layer.geom.aes_params.get("color") == rf.BREAKS_COLOR]
    return int(sum(len(d) for d in red))


@pytest.mark.parametrize("name, paradigm, acclimation, kind, parts", FIGURES)
def test_each_rule_figure_draws_on_its_spec(clean, name, paradigm, acclimation, kind, parts):
    section = _section(rf.rule_sections(clean(name).opto), paradigm, acclimation=acclimation)
    assert section.figure == kind and rf.figure_parts(section) == parts
    for part in parts:
        figure = rf.build_part(section, part)
        figure.draw()
        assert len(figure.data) and _drawn_breaks(figure) == 0, part
        assert rf.part_caption(section, part).startswith(rf._WHAT[part])


def _onsets(name: str, dfm_id: int, well: int) -> np.ndarray:
    return np.asarray(sim(name)[1][dfm_id].truth.activation_onset_ms[well])


def _stuck_on(name: str):
    """W1's LED (and its linked W2's) lit 6 s from an onset (S1's fault)."""
    onsets = _onsets(name, 1, 1)
    gap = np.diff(onsets)
    t0 = int(onsets[:-1][(gap > 9000) & (onsets[:-1] > 60000)][0]) / 1000
    return {1: [vf.OnMsFault(w, t0 + 0.2, t0 + 6.2, 200) for w in (1, 2)]}


def _cut_short(name: str):
    """Ten of W1's Activations dark 400 ms in, on W1 and W2 (S1's fault)."""
    onsets = _onsets(name, 1, 1)[2:12]
    return {1: [vf.OnMsFault(w, t / 1000 + 0.4, t / 1000 + 1.2, 0) for t in onsets
                for w in (1, 2)]}


#: (spec, the fault, Paradigm, the part that shows it, its column).
FAULTS = [
    ("closed_max", {"program_paradigms": {"CL500": replace(vf.CL500, max_on_ms=1000)}},
     "CL500", "lit", rcheck.OVER_MAX_ON_COLUMN),
    ("closed_max", {"program_paradigms": {"CL500": replace(vf.CL500, hold_ms=1500)}},
     "CL500", "lit", rcheck.SHORT_COLUMN),
    ("closed_max", {"on_ms_faults": "stuck"}, "CL500", "lit", rcheck.OVER_MAX_ON_COLUMN),
    ("fixed_interval", {"program_paradigms": {"FI10s": replace(vf.FI10S, lockout_ms=20000)}},
     "FI10s", "spacing", rcheck.LOCKOUT_COLUMN),
    ("fixed_interval", {"program_paradigms": {"FI10s": replace(vf.FI10S, activation_ms=1500)}},
     "FI10s", "lit", rcheck.WRONG_LENGTH_COLUMN),
    ("fixed_interval", {"on_ms_faults": "cut"}, "FI10s", "lit", rcheck.WRONG_LENGTH_COLUMN),
    ("exponential", {"program_paradigms": {"PRExp": replace(vf.PR_EXP, rate=0.3)}},
     "PRExp", "series", rcheck.SERIES_COLUMN),
    ("non_feeding", {"program_paradigms": {"NFMax5s": replace(vf.NF_MAX5S, max_on_ms=2000)}},
     "NFMax5s", "lit", rcheck.OVER_MAX_ON_COLUMN),
]


@pytest.mark.parametrize("name, fault, paradigm, part, column", FAULTS)
def test_an_injected_fault_shows_its_failing_points(tmp_path, name, fault, paradigm, part,
                                                    column):
    """Each fault's breaking light is drawn in the failure colour, as many
    values as the check counted, and the section's verdict fails or warns."""
    if fault.get("on_ms_faults") == "stuck":
        fault = {"on_ms_faults": _stuck_on(name)}
    elif fault.get("on_ms_faults") == "cut":
        fault = {"on_ms_faults": _cut_short(name)}
    e = load(tmp_path / "e", name, **fault)
    section = _section(rf.rule_sections(e.opto), paradigm)
    counted = int(pd.to_numeric(section.groups[column], errors="coerce").sum())
    assert counted > 0
    assert not (section.groups["Verdict"] == "ok").all()
    figure = rf.build_part(section, part)
    figure.draw()
    assert _drawn_breaks(figure) == counted


def test_nothing_judged_is_a_grey_note():
    """A section none of whose Activations could be judged gets the
    layout's neutral note, not a figure and not an error."""
    p = op.Paradigm(name="CL9", type=op.CLOSED_LOOP, frequency_hz=40, pulse_width_ms=8,
                    hold_ms=500)
    empty = pd.DataFrame(columns=["DFM", "Group", "Well", "Row", "LitMs", "Phase",
                                  *rf.MARK_COLUMNS])
    groups = pd.DataFrame({"DFM": [1], "Group": [1], "Wells": ["W1, W2"], "Treatment": ["A"],
                           "ShortActivations": [0], "Judged": [0], "NotJudged": [3],
                           "Flags": [""], "Verdict": ["ok"]})
    section = rf.RuleSection(pfam.CLOSED_LOOP, p, False, (1,), groups, empty)
    with pytest.raises(rl.NothingToDraw, match="No Activation's length of CL9"):
        rf.build_part(section, "lit")
    blocks = rf.report_blocks(None, [section])
    doc = rl.ReportDocument("Experiment report", "x", generated="2026-01-01", version="test")
    doc.add(rl.Cover("Experiment report", "x", []), *blocks)
    text = _texts(doc)
    assert "No Activation of CL9 could be judged" in text
    _no_error(text)


# ---------------------------------------------------------------------------
# The member report's light QC
# ---------------------------------------------------------------------------

def _blocks_text(blocks) -> str:
    out = []
    for b in blocks:
        for attribute in ("text", "caption", "title"):
            value = getattr(b, attribute, None)
            if isinstance(value, str):
                out.append(value)
    return " ".join(out)


def test_the_light_qc_has_a_subsection_per_paradigm(clean):
    blocks = clean("one_of_each").opto.report_qc_blocks()
    headings = [b.text for b in blocks if isinstance(b, rl.Heading)]
    assert headings == ["Optogenetic light QC",
                        *(f"Rule check: {s.title}"
                          for s in rf.rule_sections(clean("one_of_each").opto))]
    text = _blocks_text(blocks)
    ## Generation 3: the paragraph says each rule is checked below, not "decay".
    assert "Each Paradigm is also checked against its own rule" in text
    assert "within the interval's light decay" not in text
    ## A rule figure under each section but open loop's: the six others.
    first = next(i for i, b in enumerate(blocks)
                 if isinstance(b, rl.Heading) and b.text.startswith("Rule check:"))
    assert sum(isinstance(b, (rl.Plot, rl.PlotRow)) for b in blocks[first:]) == 6


def test_generation_1_keeps_its_light_qc(tmp_path):
    """A generation-1 member's light QC has no rule subsection, and keeps
    its decay paragraph."""
    from opto_fixtures import make_opto_dir

    e = _quiet_load(make_opto_dir(tmp_path / "g1"))
    assert rf.rule_dfms(e.opto) == [] and rf.rule_sections(e.opto) == []
    blocks = e.opto.report_qc_blocks()
    assert [b.text for b in blocks if isinstance(b, rl.Heading)] == ["Optogenetic light QC"]
    assert "within the interval's light decay" in _blocks_text(blocks)


def test_the_glance_callout_counts_the_new_flags(tmp_path, clean):
    callout = clean("one_of_each").opto.report_glance_blocks()[0]
    assert callout.tone == "ok"
    assert callout.text == ("Every linkage group's light was explained by its licks and kept "
                            "its Paradigm's rule (36 of 36).")
    e = load(tmp_path / "e", "fixed_interval",
             program_paradigms={"FI10s": replace(vf.FI10S, lockout_ms=20000)})
    callout = e.opto.report_glance_blocks()[0]
    assert callout.tone == "failed"
    assert "6 of 12 linkage groups failed (DFM 1 group 1;" in callout.text
    assert ": lockout broken in 6 groups;" in callout.text


# ---------------------------------------------------------------------------
# The Program timeline and the QC Viewer's Activations
# ---------------------------------------------------------------------------

def _legend(fig) -> list[str]:
    return [t.get_text() for legend in fig.legends for t in legend.get_texts()]


def test_the_timeline_marks_each_restart(clean):
    e = clean("restart")
    for dfm_id in (1, 2):
        dfm = e.dfms[dfm_id]
        minutes = pd.to_numeric(dfm.raw_df["Minutes"], errors="coerce").to_numpy(float)
        spans = program_timeline._restart_spans(dfm, minutes, 1 / 300)
        (span,) = spans
        (restart,) = dfm.restarts()
        assert span[0] < restart["Minute"] <= span[1]
        fig = program_timeline.plot_dfm(e, dfm_id)
        assert "DFM restart" in _legend(fig)
        assert any(t.get_text().strip() == "restart" for ax in fig.axes for t in ax.texts)


def test_the_timeline_shades_on_and_off_wells(clean):
    e = clean("repeating")
    dfm = e.dfms[1]
    minutes = pd.to_numeric(dfm.raw_df["Minutes"], errors="coerce").to_numpy(float)
    states = program_timeline._well_states(dfm, e.opto_program.section(1), minutes, 1 / 300)
    ## Every Well On for 3 minutes, then Off for 12, on each pass.
    assert {kind for _w, _a, _b, kind in states} == {"On", "Off"}
    on = sorted({(round(a, 2), round(b, 2)) for _w, a, b, kind in states if kind == "On"})
    assert len(on) == 2 and all(2.8 < b - a < 3.2 for a, b in on)
    legend = _legend(program_timeline.plot_dfm(e, 1))
    assert "Well On" in legend and "Well Off" in legend and "DFM restart" not in legend


def test_a_generation_1_timeline_is_unchanged(tmp_path):
    from opto_fixtures import make_opto_dir

    e = _quiet_load(make_opto_dir(tmp_path / "g1"))
    legend = _legend(program_timeline.plot_dfm(e, 1))
    assert "Well On" not in legend and "Well Off" not in legend
    assert program_timeline.activations_table(e, 1).empty


def test_the_activations_table_is_the_ledgers_rows(clean):
    e = clean("fixed_interval")
    table = program_timeline.activations_table(e, 2)
    assert list(table.columns) == list(program_timeline.ACTIVATION_TABLE_COLUMNS)
    events = e.opto.events_table()
    mine = events[(events["DFM"] == 2) & (events["Source"] == "activations")]
    assert len(table) == len(mine) > 0
    assert table["OnsetMin"].is_monotonic_increasing
    assert set(table["Family"].dropna()) == {pfam.CLOSED_LOOP, pfam.FIXED_LENGTH}


# ---------------------------------------------------------------------------
# Light behaviour by family
# ---------------------------------------------------------------------------

def test_light_behaviour_has_a_subsection_per_family(clean):
    from pyflic.base.pdf_report import ReportOptions, _light_results

    e = clean("one_of_each")
    blocks = _light_results(e, ReportOptions(metrics=()))
    headings = [b.text for b in blocks if isinstance(b, rl.Heading)]
    assert headings == ["Light behaviour", "Light behaviour: open loop",
                        "Light behaviour: closed loop", "Light behaviour: fixed length, interval",
                        "Light behaviour: fixed length, ratio", "Light behaviour: non-feeding",
                        "Light behaviour: Acclimation (closed loop)"]
    titles = [p.title for b in blocks if isinstance(b, rl.Plot) for p in [b]]
    assert "Feeding in light and dark" in titles
    tables = [b.caption for b in blocks if isinstance(b, rl.Table)]
    assert "Treatment comparisons: light behaviour, closed loop" in tables
    ## Only the families the program runs.
    assert [f.key for f in rc.light_families([(clean("closed_max").opto_program, None)])] == \
        [pfam.CLOSED_LOOP]
    assert [f.key for f in rc.light_families([(clean("exponential").opto_program, None)])] == \
        [pfam.RATIO_BRANCH, rc.ACCLIMATION]


def test_a_family_shows_the_chambers_that_ran_it(clean):
    from pyflic.base import light_summary as ls

    e = clean("one_of_each")
    frame = ls.behaviour_rows(ls.light_summary(e))
    keys = {(None, d): rc.program_light_keys(e.opto_program, [d]) for d in e.opto.dfm_ids()}
    rows = {f.key: f.rows(frame, keys) for f in rc.light_families([(e.opto_program, None)])}
    assert set(rows[pfam.OPEN_LOOP]["DFM"]) == {1}
    ## DFM 5 ran Closed, then PR10 with Acclimation: its rows are "mixed".
    assert set(rows[pfam.CLOSED_LOOP]["DFM"]) == {2, 5}
    assert set(rows[pfam.INTERVAL_BRANCH]["DFM"]) == {3}
    assert set(rows[pfam.RATIO_BRANCH]["DFM"]) == {5, 6}
    assert set(rows[pfam.NON_FEEDING]["DFM"]) == {4}
    assert set(rows[rc.ACCLIMATION]["DFM"]) == {5}


def test_light_metrics_read_with_their_labels_and_units():
    from pyflic.base.pubfigures import LIGHT_METRICS

    for metric, label in LIGHT_METRICS:
        assert rc.metric_label(metric) == label
    assert rc.metric_label("MedianActivationSec") == "Median Activation (s)"


def test_feeding_in_light_and_dark_joins_each_chambers_two_rates():
    frame = pd.DataFrame({"DFM": [1, 1, 1], "Chamber": [1, 2, 3], "Treatment": ["A", "A", "B"],
                          "LicksPerMinLit": [10.0, 12.0, 4.0],
                          "LicksPerMinDark": [2.0, 1.0, np.nan]})
    figure = rc.light_dark_plot(frame)
    figure.draw()
    assert len(figure.data) == 4                     # chamber 3 has no dark rate
    with pytest.raises(rl.NothingToDraw):
        rc.light_dark_plot(frame.assign(LicksPerMinDark=np.nan))


# ---------------------------------------------------------------------------
# The reports, end to end
# ---------------------------------------------------------------------------

def _project(root: Path, name: str, spec_name: str | None = None):
    """A one-member Custom Project at *root* over simulator spec *spec_name*,
    analysed and combined."""
    from pyflic.base.project import Project

    spec, results = sim(spec_name or name)
    member = root / name
    member.mkdir(parents=True)
    vf.write_v4_recording(member / "data", spec, results=results)
    cfg = _config([d.dfm_id for d in spec.dfms])
    design = cfg.pop("global")
    (member / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": root.name, "design": {"global": design}}, sort_keys=False))
    return Project(root)


def _reports(project, member: str) -> tuple[str, str]:
    """The member's report and the Project's, rendered and read."""
    from pyflic.base.pdf_report import build_experiment_report
    from pyflic.base.project_report import build_project_report

    with contextlib.redirect_stdout(io.StringIO()):
        exp = project.load_member(member, parallel=False, use_disk_cache=False)
        exp.execute_basic_analysis(skip_qc=False)
        member_text = _texts(build_experiment_report(
            exp, metrics=("Licks", "Events", "MedDuration")))
        project.build_combined_analysis()
        project_text = _texts(build_project_report(project))
    return member_text, project_text


REPORT_SPECS = [*vf.FAMILY_SPEC_KEYS, "one_of_each", "stress", "choice", "yoked"]


@pytest.mark.slow
@pytest.mark.parametrize("name", REPORT_SPECS)
def test_the_reports_build_with_no_error(tmp_path, name):
    """The member and Project reports of every family spec, one_of_each,
    stress, choice and yoked_controls: no red box, no "could not be drawn";
    a rule subsection per Paradigm in the member's, Light behaviour by
    family in both, and Paired and yoked where groups are yoked."""
    project = _project(tmp_path / f"p_{name}", "m1", name)
    member, pooled = _reports(project, "m1")
    _no_error(member)
    _no_error(pooled)
    assert "Rule check:" in member
    assert "Light behaviour: " in member and "Light behaviour: " in pooled
    assert ("Paired and yoked" in member) == ("Paired and yoked" in pooled) == (name == "yoked")


# -- PyMCU's simulated recording (skips without the PyMCU checkout) -----------

from test_pymcu_simulator import (  # noqa: E402,F401  (fixture)
    CUSTOM_DESIGN, PR_DESIGN, build_project, simulated)


@pytest.mark.slow
@pytest.mark.parametrize("design", ["custom", "progressive_ratio"])
def test_pymcus_recording_reports_build_with_no_error(simulated, tmp_path, design):
    """As Custom and as Progressive Ratio (twelve solo groups): no red box.
    The Progressive Ratio Project report had two (the breaking-point
    figures were drawn from the wrong rows), and its Stats text an empty
    paired − yoked section."""
    root = tmp_path / design / "pymcu_sim"
    project = build_project(root, simulated.recording,
                            CUSTOM_DESIGN if design == "custom" else PR_DESIGN)
    member, pooled = _reports(project, simulated.recording.name)
    _no_error(member)
    _no_error(pooled)
    assert "Rule check: PR5 (fixed length, ratio; DFM 1, 2)" in member
    if design == "progressive_ratio":
        assert "Breaking point by treatment" in pooled
        stats = (Path(project.analysis_path) / f"{project.name}_Stats.txt").read_text(
            encoding="utf-8")
        assert "Paired − yoked difference: none; the design has no yoked controls" in stats
        assert "Paired − yoked difference (primary" not in stats
        assert "No test against zero was possible" not in pooled
