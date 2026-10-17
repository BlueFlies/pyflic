"""Program Facets (docs/v4-data-plan.md, Stream 5, decision 7).

``facet_source: program`` gives one Facet per Program Interval of each DFM's
program, its Cycles pooled; ``program_cycles`` one per Interval and Cycle.
Generation 3 reads the Intervals from the data (``ParadigmState``), generation
1 from the program's clock schedule.  A Facet is a label with one or more
windows, and a chamber is summarised over their union.  Recordings come from
the firmware simulator (``v4_fixtures``) and the generation-1 opto fixtures.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import experiment_types, program_facets, windowing
from pyflic.base import opto_program as op
from pyflic.base import pdf_report, project_report
from pyflic.base.project import DESIGN_KEYS, Project
from pyflic.base.yaml_config import load_experiment_yaml
from pyflic.base.yaml_lint import lint_flic_config

import opto_fixtures as of
from pr_fixtures import make_pr_experiment_dir
from v4_fixtures import (
    one_of_each_spec,
    repeating_open_loop_spec,
    simulate,
    write_v4_recording,
    yoked_controls_spec,
)

PARAMS = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
          "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}


def two_well_global(**extra) -> dict:
    g = {"chamber_layout": "two_well", "transform_licks": False, "params": dict(PARAMS)}
    g.update(extra)
    return g


def dfm_nodes(dfm_ids) -> list[dict]:
    return [{"id": int(i), "chambers": {c: ("Ctrl" if c % 2 else "Exp") for c in range(1, 7)}}
            for i in dfm_ids]


def recording(root: Path, spec, *, results=None, global_extra: dict | None = None,
              program: bool = True, with_global: bool = True) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_v4_recording(root / "data", spec, results=results, program=program)
    cfg: dict = {"dfms": dfm_nodes(d.dfm_id for d in spec.dfms)}
    if with_global:
        cfg = {"global": two_well_global(**(global_extra or {})), **cfg}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def load(root: Path, **kw):
    return load_experiment_yaml(root, parallel=False, use_disk_cache=False, **kw)


def facet_issues(root: Path) -> list[str]:
    """``pyflic lint``'s findings about the Facets (the linter's older
    chamber_size rule is not this stream's)."""
    return [i.message for i in lint_flic_config(root / "flic_config.yaml")
            if "facet" in i.message.lower()]


@lru_cache(maxsize=None)
def repeating():
    spec = repeating_open_loop_spec()
    return spec, simulate(spec)


@lru_cache(maxsize=None)
def one_of_each():
    spec = one_of_each_spec(minutes=12.0)
    return spec, simulate(spec)


@pytest.fixture(scope="module")
def pooled(tmp_path_factory):
    spec, results = repeating()
    root = recording(tmp_path_factory.mktemp("pooled"), spec, results=results,
                     global_extra={"facet_source": "program"})
    return load(root)


@pytest.fixture(scope="module")
def cycles(tmp_path_factory):
    spec, results = repeating()
    root = recording(tmp_path_factory.mktemp("cycles"), spec, results=results,
                     global_extra={"facet_source": "program_cycles"})
    return load(root)


# ---------------------------------------------------------------------------
# A Repeating program: Cycles pooled, or one Facet per pass
# ---------------------------------------------------------------------------

def test_a_repeating_program_gives_one_facet_per_program_interval(pooled):
    """Open (every Well On, 3 min) then Open (every Well Off, 12 min),
    Repeating for 45 min: the name runs in two Intervals, so each Facet is
    told apart by its Interval, and each pools its three Cycles."""
    assert pooled.facet_source == "program"
    assert pooled.facets_vary_by_dfm
    assert pooled.facet_labels() == ["I1 Open", "I2 Open"]
    assert pooled.facet_windows() == []           # no window every DFM shares
    facets = dict(pooled.facet_windows_for(1))
    assert list(facets) == ["I1 Open", "I2 Open"]
    assert [len(w) for w in facets.values()] == [3, 3]
    ## The windows select exactly the rows the DFM recorded under each Interval.
    dfm = pooled.dfms[1]
    minutes = dfm.raw_df["Minutes"].to_numpy(dtype=float)
    interval = dfm.paradigm.program_interval.to_numpy(dtype=np.int64, na_value=-1)
    for k, label in ((1, "I1 Open"), (2, "I2 Open")):
        rows = windowing.window_mask(minutes, facets[label])
        assert np.array_equal(rows, interval == k), label
        lo, hi = facets[label][0]
        assert lo < hi


def test_the_pooled_facet_summarises_the_union_of_its_cycles(pooled, cycles):
    facet = pooled.feeding_summary_facet()
    assert list(facet.columns[:2]) == ["Facet", "FacetRange"]
    assert list(dict.fromkeys(facet["Facet"])) == ["I1 Open", "I2 Open"]
    assert set(facet.groupby("Facet").size()) == {6}
    assert facet.loc[facet["Facet"] == "I1 Open", "FacetRange"].iloc[0].count(";") == 2

    per_cycle = cycles.feeding_summary_facet()
    assert list(dict.fromkeys(per_cycle["Facet"])) == [
        "I1 Open C1", "I2 Open C1", "I1 Open C2", "I2 Open C2", "I1 Open C3", "I2 Open C3"]
    for k in (1, 2):
        whole = facet[facet["Facet"] == f"I{k} Open"].set_index("Chamber")
        parts = per_cycle[per_cycle["Facet"].str.startswith(f"I{k} Open C")]
        summed = parts.groupby("Chamber")[["LicksA", "LicksB", "EventsA", "EventsB",
                                           "OptoOn_sec_A"]].sum()
        for column in summed.columns:
            assert np.allclose(whole.loc[summed.index, column], summed[column]), (k, column)
    ## Every Well is lit through Interval 1 and dark through Interval 2.
    lit = facet[facet["Facet"] == "I1 Open"]["OptoOn_sec_A"]
    assert (lit > 500).all() and (facet[facet["Facet"] == "I2 Open"]["OptoOn_sec_A"] == 0).all()


def test_medians_come_from_the_events_inside_the_union(pooled):
    """Not an average of per-Cycle medians: the median of every feeding
    event whose minute lies in any of the Facet's windows."""
    dfm = pooled.dfms[1]
    facet = pooled.feeding_summary_facet()
    windows = dict(pooled.facet_windows_for(1))["I2 Open"]
    for chamber in range(1, 7):
        well = f"W{2 * chamber - 1}"
        durations = dfm.durations[well]
        inside = durations[windowing.window_mask(durations["Minutes"], windows)]
        row = facet[(facet["Facet"] == "I2 Open") & (facet["Chamber"] == chamber)].iloc[0]
        assert row["MedDurationA"] == pytest.approx(float(inside["Duration"].median()))
        assert row["MeanDurationA"] == pytest.approx(float(inside["Duration"].mean()))
        assert row["EventsA"] == len(inside)


def test_one_window_as_a_list_matches_the_pair(pooled):
    """The row-mask path and the single-window path agree, so a Facet of one
    window is summarised exactly as a cutoff window is."""
    dfm = pooled.dfms[1]
    pair = dfm.feeding_summary(range_minutes=(4.0, 13.5), transform_licks=False)
    listed = dfm.feeding_summary(range_minutes=[(4.0, 13.5)], transform_licks=False)
    pd.testing.assert_frame_equal(pair, listed)
    assert np.array_equal(dfm.light_seconds((0.5, 2.5)), dfm.light_seconds([(0.5, 2.5)]))


def test_summary_and_report_say_where_the_facets_came_from(pooled):
    text = pooled.summary_text(include_qc=False)
    assert "Facets: Program Intervals, Cycles pooled (facet_source: program)" in text
    assert "I1 Open, I2 Open" in text
    assert program_facets.CLOCK_SCHEDULE_NOTE not in text      # generation 3: recorded
    assert "facet_source: program" in pdf_report._facet_description(pooled)
    frame, frames, column = pdf_report._summary_frames(pooled, pdf_report.ReportOptions())
    assert column == "Facet" and [label for label, _f in frames] == ["I1 Open", "I2 Open"]


def test_the_facet_csv_is_written(pooled, tmp_path):
    path = pooled.write_feeding_summary_facet(tmp_path / "facet.csv")
    written = pd.read_csv(path)
    assert list(dict.fromkeys(written["Facet"])) == ["I1 Open", "I2 Open"]


# ---------------------------------------------------------------------------
# Different Paradigms on different DFMs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def each(tmp_path_factory):
    spec, results = one_of_each()
    root = recording(tmp_path_factory.mktemp("each"), spec, results=results,
                     global_extra={"facet_source": "program"})
    return load(root)


def test_each_dfm_s_facet_is_labelled_by_its_paradigm(each):
    assert each.facet_labels() == ["Open", "Closed", "Interval1Min", "NotFeeding",
                                   "PR10", "FR5"]
    assert [label for label, _w in each.facet_windows_for(1)] == ["Open"]
    assert [label for label, _w in each.facet_windows_for(5)] == ["Closed", "PR10"]
    facet = each.feeding_summary_facet()
    dfms_of = facet.groupby("Facet")["DFM"].agg(lambda s: sorted(set(s)))
    assert dfms_of["Closed"] == [2, 5]          # the same name pools the two DFMs
    assert dfms_of["Open"] == [1] and dfms_of["PR10"] == [5] and dfms_of["FR5"] == [6]
    ## Pooled under one label, though DFM 5 ran Closed for one minute only.
    closed = facet[facet["Facet"] == "Closed"]
    assert closed.groupby("DFM")["FacetRange"].first().nunique() == 2
    ## Each DFM's rows over its own windows: DFM 5's Closed is its first
    ## minute, DFM 2's the whole recording after the lead-in.
    span = closed.groupby("DFM")["EndMin"].first()
    assert span[5] == pytest.approx(1.0, abs=0.01) and span[2] == pytest.approx(12.0, abs=0.01)


def test_cycles_of_a_linear_program_are_one(tmp_path):
    spec, results = one_of_each()
    exp = load(recording(tmp_path, spec, results=results,
                         global_extra={"facet_source": "program_cycles"}))
    assert exp.facet_labels() == ["Open C1", "Closed C1", "Interval1Min C1",
                                  "NotFeeding C1", "PR10 C1", "FR5 C1"]


def test_a_project_pools_program_facets_by_label(tmp_path):
    """Two Members whose DFMs ran different Paradigms: the Combined Analysis
    groups by the Facet label, so Closed pools every Member's Closed chambers."""
    root = tmp_path / "proj"
    root.mkdir()
    design = two_well_global(facet_source="program")
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": design}}, sort_keys=False))
    spec_a, results_a = one_of_each()
    recording(root / "a", spec_a, results=results_a, with_global=False)
    spec_b = yoked_controls_spec(minutes=12.0)
    recording(root / "b", spec_b, results=simulate(spec_b), with_global=False)

    project = Project(root)
    assert "facet_source" in DESIGN_KEYS
    assert project.facet_source == "program" and project.facets_vary_by_dfm
    for name in project.member_names:
        exp = project.load_member(name, parallel=False, use_disk_cache=False)
        assert exp.facet_source == "program"
        exp.write_feeding_summary()
        assert exp.write_feeding_summary_facet() is not None
    summary, facet, missing = project.combined_frames()
    assert missing == []
    frames = dict(project._facet_frames(summary, facet))
    assert list(frames) == ["Open", "Closed", "Interval1Min", "NotFeeding", "PR10", "FR5"]
    closed = frames["Closed"]
    assert set(zip(closed["Experiment"], closed["DFM"])) == {("a", 2), ("a", 5), ("b", 1)}
    rows = project.comparison_rows(summary, facet)
    assert "Closed" in {row["phase"] for row in rows}

    project.build_combined_analysis()
    stats = (root / "analysis" / "proj_Stats.txt").read_text(encoding="utf-8")
    assert "Program Intervals, Cycles pooled" in stats
    assert "facet_source: program" in project_report._facets_line(project)


def test_long_labels_widen_the_stats_facet_column(tmp_path):
    """A generation-1 program's generated Paradigm names are long; the Stats
    table's Facet column grows to fit them instead of running into A."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": two_well_global(facet_source="program")}}))
    project = Project(root)
    label = "ClosedLoop-40Hz-8ms-Hold500-MaxOn0"
    rows = []
    for experiment in ("m1", "m2"):
        for treatment, base in (("Ctrl", 0.1), ("Exp", 0.6)):
            for chamber in range(3):
                rows.append({"Experiment": experiment, "Facet": label,
                             "FacetRange": "(0, 30)", "Treatment": treatment,
                             "DFM": 1, "Chamber": chamber + 1, "PI": base + chamber / 50,
                             "EventPI": base, "LicksA": 10.0 + chamber, "LicksB": 5.0,
                             "EventsA": 3.0, "EventsB": 2.0, "MedDurationA": 1.0,
                             "MedDurationB": 1.0})
    facet = pd.DataFrame(rows)
    text = project.stats_text(facet.drop(columns=["Facet", "FacetRange"]), facet)
    assert f"{label} Ctrl" in text


# ---------------------------------------------------------------------------
# Generation 1: the clock schedule, noted as approximate
# ---------------------------------------------------------------------------

THRESH = [of.WELL_CASES[w][1] for w in range(1, 13)]


def two_interval_program() -> str:
    return of.program_text({1: {"intervals": [
        of.interval_line(THRESH, duration_min=30, decay=500),
        of.interval_line([-1] * 12, start=of.START + timedelta(minutes=30), duration_min=30)]}},
        minutes=60)


def opto_dir(root: Path, *, program: str | None, **g_extra) -> Path:
    of.make_opto_dir(root, program=program)
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"].update(g_extra)
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def test_generation_1_facets_come_from_the_clock_schedule(tmp_path):
    root = opto_dir(tmp_path / "g1", program=two_interval_program(), facet_source="program")
    exp = load(root)
    assert exp.dfms[1].generation == 1
    section = op.parse_program(two_interval_program()).section(1)
    names = [iv.paradigm.name for iv in section.intervals]
    assert len(set(names)) == 2
    assert exp.facet_labels() == names
    windows = exp.facet_windows_for(1)
    assert [len(w) for _label, w in windows] == [1, 1]
    (first_a, first_b), = windows[0][1]
    (second_a, second_b), = windows[1][1]
    assert first_b == pytest.approx(30.0, abs=0.25) and second_a == first_b
    assert second_b == pytest.approx(60.0, abs=0.25)
    facet = exp.feeding_summary_facet()
    assert list(dict.fromkeys(facet["Facet"])) == names
    text = exp.summary_text(include_qc=False)
    assert f"DFM 1: {program_facets.CLOCK_SCHEDULE_NOTE}" in text
    assert "approximate" in pdf_report._facet_description(exp)
    assert facet_issues(root) == []


def test_a_name_in_two_intervals_is_told_apart_on_generation_1(tmp_path):
    ## A legacy export names its Paradigm from F/P/D/L/M alone, so the two
    ## 500 ms-decay Intervals share a name and the 1000 ms one has its own.
    same = of.program_text({1: {"intervals": [
        of.interval_line(THRESH, duration_min=20, decay=500),
        of.interval_line([-1] * 12, start=of.START + timedelta(minutes=20), duration_min=20),
        of.interval_line(THRESH, start=of.START + timedelta(minutes=40), duration_min=20,
                         decay=500)]}},
        minutes=60)
    exp = load(opto_dir(tmp_path / "g1", program=same, facet_source="program"))
    names = [iv.paradigm.name for iv in op.parse_program(same).section(1).intervals]
    assert names[0] == names[2] != names[1]
    assert exp.facet_labels() == [f"I1 {names[0]}", names[1], f"I3 {names[0]}"]


# ---------------------------------------------------------------------------
# Errors: no program, a DFM without a section, cutoffs beside the source
# ---------------------------------------------------------------------------

def test_a_missing_program_is_an_error_at_load_and_in_lint(tmp_path):
    spec, results = repeating()
    root = recording(tmp_path / "noprog", spec, results=results, program=False,
                     global_extra={"facet_source": "program"})
    with pytest.raises(ValueError, match=r"facet_source: program takes the Facets from "
                                         r"data/Program.txt, and there is none"):
        load(root)
    errors = [i.message for i in lint_flic_config(root / "flic_config.yaml")
              if i.severity == "error"]
    assert any("takes the Facets from data/Program.txt" in m for m in errors)


def test_a_dfm_without_a_program_section_is_an_error(tmp_path):
    root = tmp_path / "two"
    of.make_opto_dir(root, program=of.case_program())
    of.write_opto_csv(root / "data", 2)
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"]["facet_source"] = "program_cycles"
    cfg["dfms"].append({**cfg["dfms"][0], "id": 2})
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    with pytest.raises(ValueError, match=r"no section for DFM\(s\) 2"):
        load(root)
    errors = [i.message for i in lint_flic_config(root / "flic_config.yaml")
              if i.severity == "error"]
    assert any("no section for DFM(s) 2" in m for m in errors)


def test_cutoffs_beside_a_program_source_is_an_error(tmp_path):
    spec, results = repeating()
    root = recording(tmp_path / "both", spec, results=results,
                     global_extra={"facet_source": "program", "facet_cutoffs": [10]})
    with pytest.raises(ValueError, match=r"'facet_cutoffs' and 'facet_source: program' "
                                         r"cannot both be stated"):
        load(root)
    errors = [i.message for i in lint_flic_config(root / "flic_config.yaml")
              if i.severity == "error"]
    assert any("cannot both be stated" in m for m in errors)


def test_an_unknown_source_is_an_error(tmp_path):
    spec, results = repeating()
    root = recording(tmp_path / "bad", spec, results=results,
                     global_extra={"facet_source": "intervals"})
    with pytest.raises(ValueError, match=r"global.facet_source is 'intervals'"):
        load(root)
    assert any("must be one of cutoffs, program, program_cycles" in i.message
               for i in lint_flic_config(root / "flic_config.yaml"))


def test_lint_is_clean_on_a_program_facet_recording(tmp_path):
    spec, results = repeating()
    root = recording(tmp_path / "ok", spec, results=results,
                     global_extra={"facet_source": "program_cycles"})
    assert facet_issues(root) == []


# ---------------------------------------------------------------------------
# Progressive Ratio owns its Facets, and so facet_source
# ---------------------------------------------------------------------------

def test_progressive_ratio_refuses_facet_source(tmp_path):
    pr = experiment_types.get_experiment_type("ProgressiveRatio")
    assert pr.owns_facet_source and "facet_source" in pr.owned_keys()
    assert pr.resolve_facet_source({"facet_source": "program"}) == "cutoffs"
    assert "facet_source" not in pr.build_global(facet_source="program")
    assert any("'facet_source' is owned by experiment_type 'ProgressiveRatio'" in p
               for p in pr.validate({"experiment_type": "ProgressiveRatio",
                                     "well_names": {"A": "S", "B": "Y"},
                                     "facet_source": "program"}))
    root = make_pr_experiment_dir(tmp_path / "pr")
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"]["facet_source"] = "program"
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    with pytest.raises(ValueError, match=r"'facet_source' is owned by experiment_type"):
        load(root)
    assert any("'facet_source' is owned by experiment_type" in i.message
               for i in lint_flic_config(root / "flic_config.yaml") if i.severity == "error")


def test_progressive_ratio_keeps_its_own_facets(tmp_path):
    exp = load(make_pr_experiment_dir(tmp_path / "pr"))
    assert exp.facet_source == "cutoffs" and exp.facets_vary_by_dfm
    assert exp.facet_labels() == ["Training", "Test"]
    assert exp.facet_windows_for(1) == []     # its windows are per Chamber Group
    assert set(exp.feeding_summary_facet()["Facet"]) == {"Training", "Test"}


# ---------------------------------------------------------------------------
# cutoffs: today's Facets, unchanged
# ---------------------------------------------------------------------------

def _facet_as_before(exp) -> pd.DataFrame:
    """feeding_summary_facet as it was written before Program Facets: one
    global window per Facet."""
    frames = []
    for window, label in zip(exp.facet_windows(), exp.facet_labels()):
        df = exp.feeding_summary(range_minutes=windowing.as_range_minutes(window)).copy()
        df.insert(0, "FacetRange", windowing.format_range(window))
        df.insert(0, "Facet", label)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def test_cutoffs_stay_global_windows_one_each(tmp_path):
    exp = load(opto_dir(tmp_path / "cut", program="default", facet_cutoffs=[10, 30]))
    assert exp.facet_source == "cutoffs" and not exp.facets_vary_by_dfm
    assert exp.facet_windows_for(1) == [
        ("0-10 min", [(0, 10)]), ("10-30 min", [(10, 30)]), ("30+ min", [(30, float("inf"))])]
    pd.testing.assert_frame_equal(exp.feeding_summary_facet(), _facet_as_before(exp))
    assert exp.facet_notes() == []
    assert "Facets:" not in exp.summary_text(include_qc=False)


def test_a_type_default_cutoff_gives_way_to_program_facets():
    custom = experiment_types.get_experiment_type(None)
    assert custom.resolve_facet_cutoffs({"facet_cutoffs": [10]}) == (10.0,)
    assert custom.resolve_facet_cutoffs({"facet_source": "program"}) is None
    g = custom.build_global(facet_cutoffs=[10], facet_source="program")
    assert g["facet_source"] == "program" and "facet_cutoffs" not in g
    assert "facet_source" not in custom.build_global(facet_cutoffs=[10])
    assert custom.validate(g) == []


# ---------------------------------------------------------------------------
# The editors' pickers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PyQt6")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_the_design_dialog_writes_the_facet_source(qt_app, tmp_path, monkeypatch):
    from pyflic.base.design_editor import ProjectDesignDialog

    root = tmp_path / "proj"
    root.mkdir()
    dialog = ProjectDesignDialog(start_dir=str(root))
    warned: list[str] = []
    monkeypatch.setattr(dialog, "_warn", warned.append)
    dialog.cutoffs_edit.setText("10, 70")
    dialog.facet_source_combo.setCurrentIndex(dialog.facet_source_combo.findData("program"))
    assert not dialog.cutoffs_edit.isEnabled() and not dialog.labels_edit.isEnabled()
    dialog._save()
    assert warned == []
    g = yaml.safe_load((root / "project.yaml").read_text())["design"]["global"]
    assert g["facet_source"] == "program"
    assert "facet_cutoffs" not in g and "facet_labels" not in g

    reopened = ProjectDesignDialog(start_dir=str(root))
    assert reopened.facet_source_combo.currentData() == "program"
    reopened.type_combo.setCurrentIndex(reopened.type_combo.findData("ProgressiveRatio"))
    assert reopened.facet_source_combo.currentData() == "cutoffs"
    assert not reopened.facet_source_combo.isEnabled()


def test_the_hub_counts_program_facets(qt_app, pooled):
    """The Hub counts Facets by label, so Program Facets (no window shared by
    every DFM) are counted, not reported as none."""
    import matplotlib

    matplotlib.use("Agg")
    from pyflic.base.hub import AnalysisHubWindow

    hub = AnalysisHubWindow()
    try:
        hub.experiment = pooled
        hub.experiment_name = "rep"
        hub.refresh()
        assert "2 facet(s)" in hub.tiles["plots"].toolTip()
    finally:
        hub.close()


def test_the_config_editor_writes_the_facet_source(qt_app, tmp_path):
    from pyflic.base.config_editor import FLICConfigEditor

    spec, results = repeating()
    root = recording(tmp_path / "exp", spec, results=results,
                     global_extra={"facet_source": "program_cycles"})
    editor = FLICConfigEditor(root / "flic_config.yaml")
    try:
        combo = editor._facet_source_combo
        assert combo.currentData() == "program_cycles" and combo.isEnabled()
        assert editor._global_section()["facet_source"] == "program_cycles"
        combo.setCurrentIndex(combo.findData("cutoffs"))
        assert "facet_source" not in editor._global_section()
        combo.setCurrentIndex(combo.findData("program"))
        editor._experiment_type_combo.setCurrentIndex(
            editor._experiment_type_combo.findData("ProgressiveRatio"))
        assert combo.currentData() == "cutoffs" and not combo.isEnabled()
        assert "facet_source" not in editor._global_section()
    finally:
        editor.close()
