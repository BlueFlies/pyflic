"""Slices: separate analyses of part of a recording (ADR-0020)."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import selections as sel
from pyflic.base import slices
from pyflic.base.experiment_types import get_experiment_type
from pyflic.base.project import Project
from pyflic.base.script_editor.runner import run_experiment_script
from pyflic.base.yaml_config import load_experiment_yaml

PARAMS = {"feeding_threshold": 5, "feeding_minimum": 5, "tasting_minimum": 1,
          "tasting_maximum": 4, "feeding_event_link_gap": 2, "samples_per_second": 5,
          "correct_for_dual_feeding": False}
CHAMBERS = {1: "Ctrl", 2: "Ctrl", 3: "Exp", 4: "Exp", 5: "Ctrl", 6: "Exp"}
SLICES = {
    "early": {"start": 0, "end": 10, "also_exclude": ["dead"],
              "constants": {"min_untransformed_licks_cutoff": 0}},
    "late": {"start": 10, "end": "end", "also_exclude": ["dead"]},
    "mid": {"start": 5, "end": 28},
}


def _global(**extra) -> dict:
    g = {"transform_licks": False, "params": dict(PARAMS), "exclusion_group": "general",
         "also_exclude": ["dead"], "slices": SLICES}
    g.update(extra)
    return g


def _write_csv(directory: Path, *, dfm_id: int = 1, minutes: float = 30.0) -> None:
    """Five samples a second with a feeding bout on every well every minute."""
    n = int(minutes * 60 * 5)
    rng = np.random.default_rng(dfm_id)
    cols: dict[str, object] = {"Sample": np.arange(1, n + 1),
                               "Seconds": np.arange(n) / 5.0}
    for w in range(1, 13):
        sig = rng.normal(0.0, 0.3, size=n)
        for k in range(int(minutes)):
            start = 300 * k + 40 + (w * 7) % 30
            sig[start:start + 8] += 10.0 + rng.normal(0, 0.5, size=8)
        cols[f"W{w}"] = np.round(sig, 3)
    directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cols).to_csv(directory / f"DFM{dfm_id}_0.csv", index=False)


def _exclusions(directory: Path, rows: list[tuple[str, int, int]]) -> None:
    lines = ["group,dfm_id,chamber,note"] + [f"{g},{d},{c}," for g, d, c in rows]
    (directory / "remove_chambers.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _standalone(root: Path, *, minutes: float = 30.0, **extra) -> Path:
    _write_csv(root / "data", minutes=minutes)
    cfg = {"global": _global(**extra), "dfms": [{"id": 1, "chambers": dict(CHAMBERS)}]}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": _global()}}, sort_keys=False))
    for name, minutes in (("long", 30.0), ("short", 20.0)):
        _write_csv(root / name / "data", minutes=minutes)
        (root / name / "flic_config.yaml").write_text(yaml.safe_dump(
            {"dfms": [{"id": 1, "chambers": dict(CHAMBERS)}]}, sort_keys=False))
    return root


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def _load(root: Path, **kwargs):
    return _quiet(load_experiment_yaml, root, parallel=False, use_disk_cache=False, **kwargs)


# ---------------------------------------------------------------------------
# The declaration
# ---------------------------------------------------------------------------

def test_slices_parse_in_declared_order_with_their_own_groups():
    parsed = slices.parse_slices(_global())
    assert [s.name for s in parsed] == ["early", "late", "mid"]
    early, late, mid = parsed
    assert early.exclusion_groups == ("early", "dead")
    assert early.constants == {"min_untransformed_licks_cutoff": 0}
    assert late.end is None and late.range_minutes == (10.0, 0.0)
    assert mid.exclusion_group == "mid" and mid.also_exclude == ()
    assert early.bounds_label() == "(0, 10] min"
    assert late.bounds_label() == "(10, end] min"


@pytest.mark.parametrize("body, message", [
    ({"all": {"start": 0, "end": 10}}, "reserved"),
    ({"x y": {"start": 0, "end": 10}}, "letters, digits"),
    ({"a": {"start": 10, "end": 5}}, "must be after start"),
    ({"a": {"start": 0, "end": 5, "exclusion_group": "general"}}, "already the own group"),
    ({"a": {"start": 0, "end": 5}, "b": {"start": 0, "end": 5, "exclusion_group": "a"}},
     "already the own group"),
    ({"a": {"start": 0, "end": 5, "constants": {"feeding_threshold": 3}}},
     "cannot vary by Slice"),
    ({"a": {"start": 0, "end": "soon"}}, "end must be a minute"),
    ({"a": {"start": 0, "end": 5, "colour": "red"}}, "unknown key"),
])
def test_a_slice_that_cannot_be_used_is_named(body, message):
    problems = slices.slice_problems({"slices": body})
    assert problems and message in problems[0]
    with pytest.raises(slices.SliceError):
        slices.parse_slices({"slices": body})


def test_the_ratio_analysis_has_no_slices():
    """Progressive Ratio and Fixed Ratio split Training and Test at each
    group's own training end, which a Slice could clip away."""
    pr = get_experiment_type("Progressive Ratio")
    assert not slices.allows_slices(pr)
    assert any("has no Slices" in p for p in slices.slice_problems(_global(), pr))
    assert slices.usable_slices(_global(), pr) == []
    assert slices.allows_slices(get_experiment_type("Hedonic"))


def test_coverage_needs_every_dfm_to_reach_the_end_within_the_tolerance():
    mid = slices.get_slice(_global(), "mid")
    assert slices.coverage(mid, {1: 27.0, 2: 30.0}, 5.0) is None
    reason = slices.coverage(mid, {1: 22.0, 2: 30.0}, 5.0)
    assert reason and "DFM 1" in reason and "DFM 2" not in reason
    late = slices.get_slice(_global(), "late")
    assert slices.coverage(late, {1: 11.0}, 5.0) is None
    assert "before the Slice starts" in slices.coverage(late, {1: 9.0}, 5.0)


# ---------------------------------------------------------------------------
# Loading a Slice
# ---------------------------------------------------------------------------

def test_a_slice_is_clipped_at_load_and_writes_under_slices(tmp_path):
    root = _standalone(tmp_path / "exp")
    whole = _load(root)
    early = _load(root, slice="early")
    minutes = early.dfms[1].raw_df["Minutes"]
    assert minutes.min() > 0 and minutes.max() <= 10.0
    assert minutes.max() == pytest.approx(10.0)
    assert early.analysis_dir == root / "slices" / "early" / "analysis"
    assert early.qc_dir == root / "slices" / "early" / "qc"
    assert whole.analysis_dir == root / "analysis"
    ## Fewer minutes, so fewer licks than the whole recording.
    licks = lambda e: e.feeding_summary()["LicksA"].sum()  # noqa: E731
    assert 0 < licks(early) < licks(whole)


def test_adjacent_slices_share_no_row_and_lose_none(tmp_path):
    root = _standalone(tmp_path / "exp")
    whole = _load(root).dfms[1].raw_df
    early = _load(root, slice="early").dfms[1].raw_df
    late = _load(root, slice="late").dfms[1].raw_df
    assert len(early) + len(late) == len(whole[whole["Minutes"] > 0])
    assert set(early["Sample"]).isdisjoint(late["Sample"])


def test_each_slice_applies_its_own_groups_and_none_of_the_wholes(tmp_path):
    root = _standalone(tmp_path / "exp")
    _exclusions(root, [("general", 1, 1), ("early", 1, 2), ("dead", 1, 3), ("late", 1, 4)])
    whole = _load(root)
    early = _load(root, slice="early")
    mid = _load(root, slice="mid")
    assert whole.excluded_chambers == {1: [1, 3]}       # general + also_exclude dead
    assert early.excluded_chambers == {1: [2, 3]}       # early + dead, not general
    assert mid.excluded_chambers == {}                  # mid excludes nothing
    assert early.exclusion_group == "early" and early.also_exclude == ("dead",)
    assert early.exclusion_groups_label() == "'early' + 'dead'"
    assert set(early.feeding_summary()["Chamber"]) == {1, 4, 5, 6}


def test_a_slice_overrides_only_the_auto_removal_cutoffs(tmp_path):
    root = _standalone(tmp_path / "exp", constants={"min_untransformed_licks_cutoff": 10_000})
    assert _load(root).global_constants["min_untransformed_licks_cutoff"] == 10_000
    assert _load(root, slice="early").global_constants["min_untransformed_licks_cutoff"] == 0
    assert _load(root, slice="late").global_constants["min_untransformed_licks_cutoff"] == 10_000


def test_a_recording_that_stops_short_does_not_cover_the_slice(tmp_path):
    root = _standalone(tmp_path / "exp", minutes=20.0)
    with pytest.raises(slices.SliceNotCovered) as raised:
        _load(root, slice="mid")
    assert "short of the Slice's end at 28" in raised.value.reason
    assert raised.value.dfm_ends[1] == pytest.approx(20.0, abs=0.01)
    ## An open-ended Slice runs to wherever each recording ends.
    assert _load(root, slice="late").dfms[1].raw_df["Minutes"].max() == pytest.approx(20.0,
                                                                                      abs=0.01)


def test_a_slice_starting_after_the_recording_is_not_covered(tmp_path):
    root = _standalone(tmp_path / "exp", minutes=8.0)
    with pytest.raises(slices.SliceNotCovered, match="before the Slice starts"):
        _load(root, slice="late")


def test_slice_and_range_minutes_cannot_both_be_given(tmp_path):
    root = _standalone(tmp_path / "exp")
    with pytest.raises(ValueError, match="not both"):
        _load(root, slice="early", range_minutes=(0, 5))


def test_load_slice_reuses_how_the_experiment_was_loaded(tmp_path):
    root = _standalone(tmp_path / "exp")
    whole = _load(root)
    late = _quiet(whole.load_slice, "late")
    assert late.slice_name == "late" and late.load_options == whole.load_options
    again = _quiet(late.load_slice, None)
    assert again.slice is None and again.exclusion_group == "general"


# ---------------------------------------------------------------------------
# Facets inside a Slice
# ---------------------------------------------------------------------------

def test_facets_are_intersected_with_the_slice_and_keep_their_names(tmp_path):
    root = _standalone(tmp_path / "exp", facet_cutoffs=[5, 15])
    whole = _load(root)
    late = _load(root, slice="late")
    assert whole.facet_labels() == ["0-5 min", "5-15 min", "15+ min"]
    assert late.facet_labels() == ["5-15 min", "15+ min"]
    assert late.facet_windows() == [(10, 15), (15, float("inf"))]
    assert late.dropped_facets() == ["0-5 min"]
    assert any("0-5 min dropped" in line for line in late.facet_notes())
    facet = late.feeding_summary_facet()
    assert list(dict.fromkeys(facet["Facet"])) == ["5-15 min", "15+ min"]
    assert set(facet["FacetRange"]) == {"(10, 15)", "(15, inf)"}


# ---------------------------------------------------------------------------
# Running a Slice: outputs, the record, the stale rule
# ---------------------------------------------------------------------------

def test_basic_analysis_of_a_slice_writes_its_outputs_and_record(tmp_path):
    root = _standalone(tmp_path / "exp")
    early = _load(root, slice="early")
    paths = _quiet(early.execute_basic_analysis, skip_qc=True)
    out = root / "slices" / "early" / "analysis"
    assert paths["feeding_summary"] == (out / "feeding_summary.csv").resolve()
    assert not (root / "analysis").exists()
    record = slices.read_record(root, "early")
    assert record["covered"] is True
    assert record["definition"]["end"] == 10.0
    assert record["actual_end_minutes"] == pytest.approx(10.0)
    summary = (out / "summary.txt").read_text(encoding="utf-8")
    assert "Slice: early (0, 10] min" in summary
    assert "group 'early' + 'dead'" in summary


# ---------------------------------------------------------------------------
# The Project
# ---------------------------------------------------------------------------

def test_a_project_pools_each_slice_from_the_members_that_cover_it(tmp_path):
    project = Project(_project(tmp_path))
    assert [s.name for s in project.slices] == ["early", "late", "mid"]
    failures = _quiet(project.run_all, make_reports=False)
    assert failures == []
    for member in ("long", "short"):
        assert (project.project_directory and
                os.path.isfile(os.path.join(project.member_dir(member), "analysis",
                                            "feeding_summary.csv")))
    mid = project.for_slice("mid")
    assert mid.not_covered().keys() == {"short"}
    assert mid.member_status("short")["covered"] is False
    assert mid.member_status("long")["analyzed"] is True
    results = _quiet(project.build_all_combined_analyses)
    assert set(results) == {None, "early", "late", "mid"}
    assert results["mid"]["not_covered"].keys() == {"short"}
    pooled = pd.read_csv(Path(mid.analysis_path) / "proj_Summary.csv")
    assert set(pooled["Experiment"]) == {"long"}
    early = pd.read_csv(Path(project.for_slice("early").analysis_path) / "proj_Summary.csv")
    assert set(early["Experiment"]) == {"long", "short"}
    coverage = pd.read_csv(Path(mid.analysis_path) / "proj_SliceCoverage.csv")
    assert dict(zip(coverage["Experiment"], coverage["Covered"])) == {"long": "yes",
                                                                       "short": "no"}
    assert mid.analysis_path == os.path.join(project.project_directory, "slices", "mid",
                                             "analysis")
    stats = (Path(mid.analysis_path) / "proj_Stats.txt").read_text(encoding="utf-8")
    assert "Not covered       : short" in stats
    ## late runs to each recording's end: 30 and 20 minutes, more than the
    ## tolerance apart, so it says so.
    assert "end 10.0 min apart" in (project.for_slice("late").open_end_spread_note() or "")


def test_a_slice_whose_definition_changed_reads_re_run_needed(tmp_path):
    root = _project(tmp_path)
    project = Project(root)
    _quiet(project.run_all, make_reports=False)
    assert project.for_slice("early").member_status("long")["stale"] is False
    meta = yaml.safe_load((root / "project.yaml").read_text())
    meta["design"]["global"]["slices"]["early"]["end"] = 12
    (root / "project.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    assert Project(root).for_slice("early").member_status("long")["stale"] is True


def test_a_slice_view_loads_members_as_its_slice(tmp_path):
    project = Project(_project(tmp_path))
    exp = _quiet(project.for_slice("early").load_member, "long")
    assert exp.slice_name == "early" and exp.excluded_chambers == {}
    assert project.for_slice(None) is project
    with pytest.raises(slices.SliceError):
        project.for_slice("nope")


def test_project_report_of_a_slice_names_it_and_who_was_left_out(tmp_path):
    from pyflic.base import report_layout as rl
    from pyflic.base.project_report import build_project_report, report_path

    project = Project(_project(tmp_path))
    _quiet(project.run_all, make_reports=False)
    mid = project.for_slice("mid")
    _quiet(mid.build_combined_analysis)
    doc = _quiet(build_project_report, mid)
    texts = [getattr(b, "text", "") for b in doc.blocks]
    assert any("do not cover this Slice" in t and "short" in t for t in texts)
    assert report_path(mid).endswith(os.path.join("slices", "mid", "proj_mid_report.pdf"))
    assert isinstance(doc, rl.ReportDocument)


# ---------------------------------------------------------------------------
# Scripts and the Selection
# ---------------------------------------------------------------------------

def test_a_script_step_names_its_slice(tmp_path):
    root = _standalone(tmp_path / "exp")
    exp = _load(root)
    log: list[str] = []
    run_experiment_script(exp, {"name": "s", "steps": [
        {"action": "feeding_csv", "slice": "early"},
        {"action": "feeding_csv"},
    ]}, log=log.append)
    assert (root / "slices" / "early" / "analysis" / "feeding_summary.csv").is_file()
    assert (root / "analysis" / "feeding_summary.csv").is_file()


def test_a_script_window_is_retired_and_skipped(tmp_path):
    root = _standalone(tmp_path / "exp")
    exp = _load(root)
    log: list[str] = []
    run_experiment_script(exp, {"name": "s", "steps": [
        {"action": "load", "start": 0, "end": 360},
        {"action": "feeding_csv", "start": 0, "end": 360},
    ]}, log=log.append)
    assert not (root / "analysis" / "feeding_summary.csv").exists()
    text = "\n".join(log)
    assert "[Skip] feeding_csv: start/end (0.0, 360.0) are retired" in text
    assert "start: 0, end: 360" in text


def test_the_selection_leaves_out_slices(tmp_path):
    from pyflic.base.run_selection import each_slice

    root = _standalone(tmp_path / "exp", omit={"slices": ["mid"]})
    exp = _load(root)
    assert sel.selected_slices(exp) == ["early", "late"]
    names = [e.slice_name for e in _quiet(lambda: list(each_slice(exp, log=lambda m: None)))]
    assert names == [None, "early", "late"]
    assert sel.validate_omit({"omit": {"slices": ["nope"]}, "slices": SLICES})
    sel.set_slice_included(exp, "mid", True)
    assert sel.selected_slices(exp) == ["early", "late", "mid"]
    on_disk = yaml.safe_load((root / "flic_config.yaml").read_text())
    assert "omit" not in on_disk["global"]


def test_an_uncovered_slice_in_a_run_is_recorded_not_raised(tmp_path):
    from pyflic.base.run_selection import each_slice

    root = _standalone(tmp_path / "exp", minutes=20.0)
    exp = _load(root)
    log: list[str] = []
    names = [e.slice_name for e in _quiet(lambda: list(each_slice(exp, log=log.append)))]
    assert names == [None, "early", "late"]
    assert slices.read_record(root, "mid")["covered"] is False
    assert any("Slice mid: not covered" in line for line in log)


# ---------------------------------------------------------------------------
# The disk cache
# ---------------------------------------------------------------------------

def test_the_disk_cache_is_keyed_by_the_exclusions(tmp_path):
    """An exclusion edit once returned the summary from before it."""
    root = _standalone(tmp_path / "exp")
    first = _quiet(load_experiment_yaml, root, parallel=False)
    assert 1 in set(first.feeding_summary()["Chamber"])
    _exclusions(root, [("general", 1, 1)])
    second = _quiet(load_experiment_yaml, root, parallel=False)
    assert 1 not in set(second.feeding_summary()["Chamber"])


def test_the_record_compares_the_definition_not_the_folder(tmp_path):
    root = _standalone(tmp_path / "exp")
    early = slices.get_slice(_global(), "early")
    slices.write_record(root, early, tol=5.0, dfm_ends={1: 30.0}, reason=None)
    record = slices.read_record(root, "early")
    assert json.loads(json.dumps(early.definition())) == record["definition"]
    assert not slices.definition_changed(record, early)
    moved = slices.get_slice(_global(slices={"early": {"start": 0, "end": 12}}), "early")
    assert slices.definition_changed(record, moved)


def test_a_slice_loaded_without_exclusions_still_names_its_own_group(tmp_path):
    """The QC Viewer loads every chamber and writes removals to the group of
    the Slice it shows."""
    root = _standalone(tmp_path / "exp")
    _exclusions(root, [("early", 1, 2), ("dead", 1, 3)])
    early = _load(root, slice="early", exclusion_group=None)
    assert early.excluded_chambers == {} and early.also_exclude == ()
    assert early.exclusion_group == "early"


# ---------------------------------------------------------------------------
# Lint
# ---------------------------------------------------------------------------

def test_lint_names_the_slice_for_an_old_windowed_folder_and_script(tmp_path):
    from pyflic.base.migration_lint import check_directory

    root = tmp_path / "exp"
    root.mkdir()
    (root / "flic_config.yaml").write_text(yaml.safe_dump({
        "global": {}, "dfms": [],
        "scripts": [{"name": "late", "steps": [{"action": "feeding_csv", "start": 360,
                                                 "end": 0}]}]}))
    (root / "analysis_0_360").mkdir()
    text = "\n".join(i.format() for i in check_directory(root))
    assert "m0_360: {start: 0, end: 360}" in text
    assert "script 'late' states start/end (360, 0)" in text
    assert "m360_end: {start: 360, end: end}" in text
    assert (root / "analysis_0_360").is_dir()


def test_yaml_lint_reports_a_slice_that_cannot_be_used(tmp_path):
    from pyflic.base.yaml_lint import lint_flic_config

    root = _standalone(tmp_path / "exp", slices={"bad": {"start": 10, "end": 5}})
    messages = [i.message for i in lint_flic_config(root / "flic_config.yaml")]
    assert any("must be after start" in m for m in messages)
    assert not any("unknown global key 'slices'" in m for m in messages)


# ---------------------------------------------------------------------------
# Publication figures
# ---------------------------------------------------------------------------

def test_a_plot_spec_draws_from_its_slice(tmp_path):
    from pyflic.base import pubfigures

    project = Project(_project(tmp_path))
    _quiet(project.run_all, make_reports=False)
    _quiet(project.build_all_combined_analyses)
    specs = pubfigures.load_project_specs(project.project_directory)
    specs.plots["faceted_licks"] = pubfigures.PlotSpec(slice="mid")
    pubfigures.save_project_specs(project.project_directory, specs)
    assert pubfigures.load_project_specs(project.project_directory).plots[
        "faceted_licks"].slice == "mid"
    written = _quiet(pubfigures.render_all, project, fmt="png", only=["faceted_licks"],
                     log=lambda m: None)
    assert written == [os.path.join(project.project_directory, "slices", "mid", "figures",
                                    "faceted_licks.png")]
    assert pubfigures.PlotSpec.from_dict({"slice": " "}).slice is None


def test_a_members_slice_reads_the_selection_ticked_since_it_loaded(tmp_path):
    """load_slice re-reads project.yaml: a tick in the Hub after the member
    loaded must reach the Slices a run loads next."""
    project = Project(_project(tmp_path))
    exp = _quiet(project.load_member, "long")
    sel.set_included(exp, sel.QC, "integrity", False, project=project)
    sel.set_slice_included(exp, "mid", False, project=project)
    early = _quiet(exp.load_slice, "early")
    assert "integrity" in sel.omitted(early, sel.QC)
    assert sel.selected_slices(early) == ["early", "late"]


def test_a_slices_unfaceted_rows_are_named_for_it(tmp_path):
    """A Slice's tables never call its minutes the whole recording."""
    early = slices.get_slice(_global(), "early")
    assert slices.whole_label(None) == "Whole recording"
    assert slices.whole_label(early) == "Slice early"
    assert slices.is_whole_label("Slice early") and slices.is_whole_label("Whole recording")
    assert not slices.is_whole_label("0-5 min")
    project = Project(_project(tmp_path))
    frame = pd.DataFrame({"Treatment": ["Ctrl"]})
    assert project.for_slice("early")._facet_frames(frame, None)[0][0] == "Slice early"
    assert project._facet_frames(frame, None)[0][0] == "Whole recording"


def test_an_unquoted_numeric_slice_name_is_named_not_renamed():
    """YAML reads 0_360 unquoted as the octal number 240."""
    g = yaml.safe_load("slices:\n  0_360: {start: 0, end: 360}\n  '360_1440': {start: 360}\n")
    problems = slices.slice_problems(g)
    assert len(problems) == 1 and "read as the number 240" in problems[0]
    assert [s.name for s in slices.usable_slices(g)] == ["360_1440"]


def test_unusable_coverage_settings_and_slice_constants_are_named():
    """A load reads them as no groups and the default tolerance, so the
    linter and the editors say so instead."""
    problems = slices.slice_problems({"slice_tolerance_min": "five", "also_exclude": {"a": 1}})
    assert any("slice_tolerance_min" in p for p in problems)
    assert any("also_exclude" in p for p in problems)
    assert slices.tolerance({"slice_tolerance_min": -2}) == slices.DEFAULT_TOLERANCE_MIN
    bad = {"slices": {"a": {"end": 5, "constants": {"min_untransformed_licks_cutoff": "x"}}}}
    assert "must be a number" in slices.slice_problems(bad)[0]
    ## A Slice's failure fraction is checked against the design's warning one.
    low = {"constants": {"opto_unexplained_warn_fraction": 0.2},
           "slices": {"a": {"end": 5, "constants": {"opto_unexplained_fail_fraction": 0.1}}}}
    assert "must not exceed" in slices.slice_problems(low)[0]


def test_a_slice_may_set_its_own_unexplained_light_verdict(tmp_path):
    root = _standalone(tmp_path / "exp", slices={
        "early": {"end": 10, "constants": {"opto_unexplained_fail_fraction": 0.5}}})
    assert _load(root, slice="early").opto.settings().fail_fraction == 0.5
    assert _load(root).opto.settings().fail_fraction == 0.30


def test_a_load_naming_no_group_excludes_the_configs_own(tmp_path):
    """The Hub, the QC Viewer and a Slice's sibling load of the whole
    recording all read a standalone config's exclusion_group."""
    root = _standalone(tmp_path / "exp", exclusion_group="main")
    _exclusions(root, [("main", 1, 1), ("general", 1, 2)])
    whole = _load(root)
    assert whole.exclusion_group == "main" and whole.excluded_chambers == {1: [1]}
    shown = _load(root, exclusion_group=None)
    assert shown.excluded_chambers == {} and shown.exclusion_group == "main"
    again = _quiet(_load(root, slice="early").load_slice, None)
    assert again.exclusion_group == "main" and again.excluded_chambers == {1: [1]}


def _set_early_end(root: Path, end: float) -> None:
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"]["slices"]["early"]["end"] = end
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))


def test_a_qc_run_records_the_slice_but_never_hides_a_stale_analysis(tmp_path):
    from pyflic.base.run_selection import run_analysis, run_qc

    quiet = {"log": lambda _m: None}
    no_qc = [i.id for i in sel.items(sel.QC)]
    no_analyses = [i.id for i in sel.items(sel.ANALYSES)]
    root = _standalone(tmp_path / "exp")
    _quiet(run_qc, _load(root, slice="early"), omit=no_qc, **quiet)
    assert slices.read_record(root, "early")["definition"]["end"] == 10.0
    _quiet(run_analysis, _load(root, slice="early"), omit=no_analyses, **quiet)
    _set_early_end(root, 12)
    _quiet(run_qc, _load(root, slice="early"), omit=no_qc, **quiet)
    ## The analysis still describes (0, 10]: its record stays, so it reads stale.
    assert slices.read_record(root, "early")["definition"]["end"] == 10.0
    _quiet(run_analysis, _load(root, slice="early"), omit=no_analyses, **quiet)
    assert slices.read_record(root, "early")["definition"]["end"] == 12.0


def test_a_not_covered_record_is_no_verdict_on_a_changed_slice(tmp_path):
    root = _project(tmp_path)
    mid = slices.get_slice(_global(), "mid")
    slices.write_record(root / "short", mid, tol=5.0, dfm_ends={1: 20.0},
                        reason="DFM 1 ends at minute 20.0")
    view = Project(root).for_slice("mid")
    assert view.not_covered() == {"short": "DFM 1 ends at minute 20.0"}
    assert view.member_status("short")["covered"] is False
    meta = yaml.safe_load((root / "project.yaml").read_text())
    meta["design"]["global"]["slices"]["mid"]["end"] = 18
    (root / "project.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    view = Project(root).for_slice("mid")
    assert view.not_covered() == {}
    status = view.member_status("short")
    assert status["covered"] is None and status["stale"] is True
    coverage = view.slice_coverage_frame().set_index("Experiment")
    assert coverage.loc["short", "Covered"] == "not run"
    assert "changed" in coverage.loc["short", "Reason"]


def test_a_slice_views_facets_keep_the_designs_names(tmp_path):
    """Its Members cut each Facet to the Slice and keep the name; so does the
    Project's statistics."""
    root = _project(tmp_path)
    meta = yaml.safe_load((root / "project.yaml").read_text())
    meta["design"]["global"].update(facet_cutoffs=[5, 15],
                                    facet_labels=["Settle", "Middle", "Late"])
    (root / "project.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    view = Project(root).for_slice("early")
    windows, label_of = view.window_labels(pd.DataFrame({"FacetRange": ["(0, 5)", "(5, 10)"]}))
    assert [label_of[w] for w in windows] == ["Settle", "Middle"]


def test_a_member_without_a_facet_table_is_named_not_silently_dropped():
    summary = pd.DataFrame({"Experiment": ["a", "b"]})
    assert Project.unfaceted_members(summary, pd.DataFrame({"Experiment": ["a"]})) == ["b"]
    assert Project.unfaceted_members(summary, None) == []


# ---------------------------------------------------------------------------
# The core pipeline on a Slice's rows (review C6-C8, C12-C14)
# ---------------------------------------------------------------------------

def test_a_slices_bins_start_at_its_start(tmp_path):
    """Review C7: no empty bins before the Slice, at either level."""
    late = _load(_standalone(tmp_path / "s"), slice="late")
    binned = late.binned_feeding_summary(binsize_min=5, save=False)
    assert binned["Interval"].iloc[0] == "(10,15]"
    assert pd.to_numeric(binned["Minutes"]).min() == 12.5
    dfm = late.dfms[1]
    assert dfm.binned_feeding_summary(binsize_min=5)["Interval"].iloc[0] == "(10.0,15.0]"
    assert dfm.before_range is not None and dfm.before_range.start_min == 10.0
    ## The whole recording still starts at minute 0.
    whole = _load(tmp_path / "s")
    assert whole.binned_feeding_summary(binsize_min=5, save=False)["Interval"].iloc[0] == "(0,5]"
    assert whole.dfms[1].before_range is None


def test_moving_windows_end_by_the_recording_end(tmp_path):
    """Review C12: a 30-minute recording's last 10-minute window is (20, 30],
    not (25, 35] labelled 35 with half its width."""
    dfm = _load(_standalone(tmp_path / "s")).dfms[1]
    moving = dfm.moving_window_feeding_summary(window_min=10, step_min=5)
    assert moving["Minutes"].max() == 30.0 and moving["Interval"].iloc[-1] == "(20,30]"
    median = dfm.moving_median_duration(window_min=10, step_min=5)
    assert median["Minutes"].max() == 30.0
    ## A window wider than the data is the one window there is.
    wide = dfm.moving_median_duration(window_min=60, step_min=5)
    assert sorted(set(wide["Minutes"])) == [60.0]


def test_a_range_with_no_bin_gives_an_empty_table(tmp_path):
    """Review C13: a range that starts on the last row's minute has no bin."""
    dfm = _load(_standalone(tmp_path / "s")).dfms[1]
    last = float(dfm.raw_df["Minutes"].max())
    assert dfm.binned_feeding_summary(binsize_min=5, range_minutes=(last, last)).empty


def test_time_between_is_nan_where_no_interval_starts(tmp_path):
    """Review C6 (owner decision): MeanTimeBtw / MedTimeBtw are NaN, not 0,
    in a window where no interval starts; a well that never licks and one
    that licked only outside the window read alike.  R's rule that the
    lead-in and tail gaps are intervals is kept."""
    from pyflic.base.dfm import DFM

    root = _standalone(tmp_path / "s")
    data = pd.read_csv(root / "data" / "DFM1_0.csv")
    n = len(data)
    data["W1"] = np.round(np.random.default_rng(9).normal(0.0, 0.3, size=n), 3)   # never licks
    data.loc[data["Seconds"] > 600, "W2"] = 0.0                                     # licks to minute 10
    data.to_csv(root / "data" / "DFM1_0.csv", index=False)
    dfm = _load(root).dfms[1]
    late = dfm.feeding_summary(range_minutes=(15, 25), transform_licks=False).iloc[0]
    for column in ("MeanTimeBtwA", "MedTimeBtwA", "MeanTimeBtwB", "MedTimeBtwB"):
        assert np.isnan(late[column]), column
    assert late["EventsA"] == 0 and late["EventsB"] == 0
    ## Over the whole recording the never-licking well's one interval is the
    ## recording: the edge gaps stay intervals.
    whole = dfm.feeding_summary(transform_licks=False).iloc[0]
    assert whole["MeanTimeBtwA"] == pytest.approx(n / 5.0)
    ## The binned summary follows the same rule.
    binned = dfm.binned_feeding_summary(binsize_min=5, transform_licks=False)
    first = binned[binned["Chamber"] == 1].set_index("Interval")
    assert np.isnan(first.loc["(15.0,20.0]", "MeanTimeBtwB"])
    ## A well with no interval at all (it fed throughout) is NaN too.
    assert np.isnan(DFM._interval_summary(0, (0, 0))).all()


def test_tidy_exports_label_wells_by_the_chamber_sets(tmp_path):
    """Review C8: with chamber_sets [[1, 3], [2, 4], ...] well 3 is chamber
    1's well B, not chamber 2's well A."""
    from pyflic.base.dfm import DFM
    from pyflic.base.parameters import Parameters

    _write_csv(tmp_path / "data")
    sets = np.array([[1, 3], [2, 4], [5, 7], [6, 8], [9, 11], [10, 12]])
    params = Parameters.two_well().with_updates(chamber_sets=sets, samples_per_second=5,
                                                feeding_threshold=5, feeding_minimum=5,
                                                tasting_minimum=1, tasting_maximum=4)
    dfm = DFM.load(1, params, data_dir=tmp_path / "data")
    expected = {}
    for ch in dfm.chambers:
        expected[int(ch.well_a)] = (int(ch.index), "WellA")
        expected[int(ch.well_b)] = (int(ch.index), "WellB")
    for table in (dfm.duration_data(), dfm.interval_data()):
        got = {int(w): (int(c), t) for w, c, t
               in zip(table["Well"], table["Chamber"], table["TCWell"])}
        assert got == {w: expected[w] for w in got}
    assert expected[3] == (1, "WellB")


def test_a_slices_whole_summary_carries_its_bounds(tmp_path):
    """Review C14: StartMin / EndMin of a Slice's whole summary are its
    bounds, not (0, 0); an open end reads inf, as in FacetRange."""
    from pyflic.base import windowing
    from pyflic.base.utils import range_is_specified

    root = _standalone(tmp_path / "s")
    late = _load(root, slice="late").feeding_summary()
    assert set(late["StartMin"]) == {10.0} and set(late["EndMin"]) == {float("inf")}
    mid = _load(root, slice="mid").feeding_summary()
    assert set(mid["StartMin"]) == {5.0} and set(mid["EndMin"]) == {28.0}
    whole = _load(root).feeding_summary()
    assert set(whole["StartMin"]) == {0.0} and set(whole["EndMin"]) == {0.0}
    assert windowing.range_span((70, 0)) == (70.0, float("inf"))
    assert windowing.range_span((0, 0)) == (0.0, 0.0)
    ## (-5, 5) is a window, as windowing.is_full_range already said.
    assert range_is_specified((-5, 5)) and not range_is_specified((0, 0))
