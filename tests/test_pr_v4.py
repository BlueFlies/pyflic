"""Progressive Ratio on recorded state (docs/v4-data-plan.md, stream 4).

A generation-3 recording from the firmware 4.0.0 simulator (``v4_fixtures``)
analysed as a Progressive Ratio experiment: Training from the Paired Sucrose
Well's Phase (decision 11), Light Events from its Activations with the
Requirement each met and the Firmware Events it took (decision 13), the Test
window ending with the ratio Paradigm's run (decision 12), FixedRatio
(decision 14), and a generation-2 recording, which has no Training at all
(decision 15).  Generation 1 is covered, unchanged, by
``test_progressive_ratio.py``, ``test_pr_light_qc.py`` and
``test_pr_breaking_point.py``.

``choice_pr_spec`` acts out ``CHOICE_PR_CASES`` on both DFMs; the configs
here make DFM 1's paired chambers 1, 3, 5 (healthy, drifting,
never-training) and DFM 2's 2, 4, 6 (healthy, dead LED, healthy).
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import opto_program as op
from pyflic.base import pr_light_qc as lqc
from pyflic.base import report_layout as rl
from pyflic.base.experiment_types.progressive_ratio import break_requirement_view
from pyflic.base.paradigm_state import ParadigmState
from pyflic.base.progressive_ratio_experiment import (
    EMPTY_TRAINING_NOTE,
    NO_TRAINING_INFORMATION,
    ProgressiveRatioExperiment,
)
from pyflic.base.yaml_config import load_experiment_yaml

from pr_fixtures import pr_config
from v4_fixtures import (
    CHOICE_PR_CASES,
    CHOICE_THRESHOLDS,
    PR10,
    IntervalSpec,
    choice_pr_spec,
    fixed_ratio_spec,
    program_text,
    simulate,
    write_gen2_recording,
    write_v4_recording,
)

RECORD_MIN = 0.2 / 60.0
PAIRED = {1: [1, 3, 5], 2: [2, 4, 6]}
TREATMENTS = {1: "Ctrl", 2: "Ctrl", 3: "Exp", 4: "Exp", 5: "Third", 6: "Third"}


def write_config(root: Path, dfm_ids, *, constants: dict | None = None) -> None:
    cfg = pr_config([{"id": int(d), "paired_chambers": PAIRED.get(int(d), [1, 3, 5]),
                      "chambers": dict(TREATMENTS)} for d in dfm_ids],
                    constants=constants)
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))


def pr_dir(root: Path, spec, results, *, writer=write_v4_recording, constants=None,
           **kw) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    writer(root / "data", spec, results=results, **kw)
    write_config(root, [d.dfm_id for d in spec.dfms], constants=constants)
    return root


def load(root: Path) -> ProgressiveRatioExperiment:
    e = load_experiment_yaml(root, parallel=False, use_disk_cache=False)
    assert isinstance(e, ProgressiveRatioExperiment)
    return e


@lru_cache(maxsize=None)
def choice():
    spec = choice_pr_spec()
    return spec, simulate(spec)


@lru_cache(maxsize=None)
def fixed():
    spec = fixed_ratio_spec(dfm_ids=(1,))
    return spec, simulate(spec)


@pytest.fixture(scope="module")
def gen3(tmp_path_factory):
    spec, results = choice()
    return load(pr_dir(tmp_path_factory.mktemp("gen3"), spec, results)), results


@pytest.fixture(scope="module")
def gen2(tmp_path_factory):
    spec, results = choice()
    return load(pr_dir(tmp_path_factory.mktemp("gen2"), spec, results,
                       writer=write_gen2_recording)), results


@pytest.fixture(scope="module")
def fr(tmp_path_factory):
    spec, results = fixed()
    return load(pr_dir(tmp_path_factory.mktemp("fr"), spec, results)), results


def case_of(dfm_id: int, group: int) -> str:
    return CHOICE_PR_CASES[next(c for c in PAIRED[dfm_id] if (c + 1) // 2 == group)]


def groups_of(case: str) -> list[tuple[int, int]]:
    return [(d, g) for d in PAIRED for g in (1, 2, 3) if case_of(d, g) == case]


# ---------------------------------------------------------------------------
# Training (decision 11)
# ---------------------------------------------------------------------------

def test_each_groups_training_ends_where_its_acclimation_ends(gen3):
    e, results = gen3
    table = e.training_table().set_index(["DFM", "Group"])
    for (dfm_id, group), row in table.iterrows():
        truth = results[dfm_id].truth
        end_ms = truth.acclimation_end_ms[int(row["SucroseWell"])]
        if case_of(dfm_id, group) in ("never_training", "dead_led"):
            assert end_ms is None
            assert row["TrainingComplete"] == False  # noqa: E712
            assert pd.isna(row["TrainingEndMin"])
            assert "training never completed" in row["Notes"]
            continue
        ## The last Training row is the one before the first Main row under PR10.
        minutes = e.dfms[dfm_id].raw_df["Minutes"].to_numpy()
        assert row["TrainingComplete"] == True  # noqa: E712
        assert row["TrainingEndMin"] == minutes[end_ms // 200 - 1]
    ## Healthy and drifting both left Acclimation; never-training stayed in A.
    assert table.loc[(1, 3), "Notes"] == ("paired Sucrose Well W9 was still in Acclimation "
                                          "(Phase A) when the recording ended — training "
                                          "never completed")


def test_training_notes_speak_of_phase_and_never_of_flags(gen3):
    e, _results = gen3
    ## The three other wells of a group are Off and read M: nothing to note.
    for dfm_id, group in groups_of("healthy"):
        assert e.group_training(dfm_id, group).notes == ()
    notes = e.training_warnings()
    assert notes and not any("flag" in n.lower() for n in notes)
    summary = e.summary_text(include_qc=False)
    assert "Training notes (QC, not errors)" in summary
    assert "Training-flag notes" not in summary


def test_an_empty_training_is_complete_and_said_so(tmp_path):
    spec, _ = fixed()
    spec = replace(spec, paradigms={"FR5": replace(spec.paradigms["FR5"], acclimation=0)})
    e = load(pr_dir(tmp_path, spec, simulate(spec)))
    dfm = e.dfms[1]
    for group in (1, 2, 3):
        gt = e.group_training(1, group)
        assert dfm.training_flag_state(gt.sucrose_well) == "never_flagged"
        assert gt.complete and gt.training_complete is True
        assert gt.notes == (EMPTY_TRAINING_NOTE,)
    assert e.training_table()["TrainingComplete"].all()
    assert not e.auto_remove_chambers()["Reason"].str.contains("training").any()


def test_a_later_ratio_run_restarts_and_ends_the_test_window(tmp_path):
    """Closed, PR10, Closed, PR10: the second PR10 resets every Well (a new
    name came between), so it is a restart in Acclimation, and the Test
    window is the first PR10's run only."""
    spec = choice_pr_spec(dfm_ids=(1,))
    intervals = tuple(IntervalSpec(name, True, CHOICE_THRESHOLDS, minutes)
                      for name, minutes in (("Closed", 5.0), ("PR10", 12.0),
                                            ("Closed", 5.0), ("PR10", 8.0)))
    spec = replace(spec, dfms=(replace(spec.dfms[0], intervals=intervals),))
    results = simulate(spec)
    e = load(pr_dir(tmp_path, spec, results))
    state = e.dfms[1].paradigm
    gt = e.group_training(1, 1)                      # healthy, paired chamber 1
    assert gt.complete
    assert "Paradigm restarted at Program Interval 4 (after the Test window, which is " \
           "the first ratio run only)" in gt.notes
    ## The window ends with the last row of Interval 2, not the recording.
    last = np.flatnonzero(state.program_interval.to_numpy(dtype=np.int64, na_value=-1) == 2)[-1]
    window = e._test_window(1, 1, e.break_settings())
    assert window == pytest.approx(float(state.minutes[last]) - gt.training_end)
    assert window < e._recording_end(e.dfms[1]) - gt.training_end - 10.0
    row = e.breaking_point_summary().set_index(["DFM", "Group"]).loc[(1, 1)]
    assert row["TestMinutes"] == pytest.approx(window)
    ## The cap still applies after.
    capped = e.break_settings().__class__(gap_min=120.0, test_window_min=3.0)
    assert e._test_window(1, 1, capped) == 3.0


# ---------------------------------------------------------------------------
# Light Events: the Paired Sucrose Well's Activations (decision 13)
# ---------------------------------------------------------------------------

def test_light_events_are_the_sucrose_wells_activations(gen3):
    e, results = gen3
    for dfm_id in PAIRED:
        truth = results[dfm_id].truth
        minutes = e.dfms[dfm_id].raw_df["Minutes"].to_numpy()
        for group in (1, 2, 3):
            gt = e.group_training(dfm_id, group)
            events = e.light_events_table(dfm_id, group)
            onsets = truth.activation_onset_ms[gt.sucrose_well]
            assert len(events) == len(onsets)
            assert np.array_equal(events["RecordingMinute"].to_numpy(),
                                  minutes[[t // 200 for t in onsets]])
            ## An Acclimation Activation is a Training Light Event, in Phase A.
            phases = truth.activation_phase[gt.sucrose_well]
            assert events["Phase"].tolist() == phases
            training = events[events["Facet"] == "Training"]
            assert (events.loc[events["Phase"] == "A", "Facet"] == "Training").all()
            if gt.complete:
                assert int((training["Phase"] == "A").sum()) == PR10.acclimation


def test_the_ledger_records_the_requirement_each_light_event_met(gen3):
    e, results = gen3
    ledger = e.light_events_ledger()
    series = [PR10.first_requirement + PR10.step * k for k in range(40)]
    for dfm_id, group in groups_of("healthy"):
        rows = ledger[(ledger.DFM == dfm_id) & (ledger.Group == group)]
        assert len(rows) >= 3
        assert rows["Requirement"].tolist() == series[:len(rows)]       # 1, 11, 21, ...
        assert rows["FirmwareEvents"].tolist() == rows["Requirement"].tolist()
        assert (rows["Phase"] == "M").all()
    ## Against the engine itself, every Main Activation of every group.
    for dfm_id in PAIRED:
        truth = results[dfm_id].truth
        for group in (1, 2, 3):
            gt = e.group_training(dfm_id, group)
            events = e.light_events_table(dfm_id, group)
            got = [None if pd.isna(v) else int(v) for v in events["Requirement"]]
            assert got == truth.requirement_met[gt.sucrose_well]
            main = events[(events["Phase"] == "M") & events["Requirement"].notna()]
            assert (main["FirmwareEvents"] == main["Requirement"]).all()


def test_the_ledger_csv_carries_the_firmware_columns(gen3, tmp_path):
    e, _results = gen3
    out = e.write_light_qc()
    ledger = pd.read_csv(out["pr_light_events"])
    assert list(ledger.columns[-4:]) == ["Requirement", "FirmwareEvents", "Phase", "Counted"]
    assert ledger["Requirement"].dropna().astype(int).min() == 1
    qc = pd.read_csv(out["pr_light_qc"])
    assert "TrendRhoFirmware" in qc.columns
    assert qc["TrendRhoFirmware"].notna().any()


def test_a_requirement_no_row_shows_comes_from_the_program():
    """An Activation on the first row of a new Paradigm met a Requirement no
    row shows (the row before belongs to the old Paradigm); the program's
    series gives it.  An Acclimation one meets none."""
    n = 10
    frame = pd.DataFrame({
        "Interval": [1] * 5 + [2] * 5,
        "Paradigm": ["Closed"] * 5 + ["PRX"] * 5,
        "Phase1": ["M"] * n,
        "Activations1": [0, 0, 0, 0, 0, 1, 1, 1, 2, 2],
        "Requirement1": [np.nan] * 5 + [3, 3, 3, 5, 5],
        "Progress1": [np.nan] * 5 + [0, 1, 2, 0, 0],
        "OnMs1": [0, 0, 0, 0, 0, 200, 0, 0, 200, 0],
    })
    state = ParadigmState.from_frame(frame, minutes=np.arange(n) * RECORD_MIN)
    dfm = SimpleNamespace(generation=3, paradigm=state)
    prx = op.Paradigm(name="PRX", type=op.PROGRESSIVE_RATIO, frequency_hz=40,
                      pulse_width_ms=8, activation_ms=500, series=op.SERIES_ARITHMETIC,
                      first_requirement=1, step=2)
    onsets = state.activation_onsets(1)
    assert onsets.tolist() == [5, 8]

    def columns(program):
        host = SimpleNamespace(opto_program=program,
                               _reads_phase=ProgressiveRatioExperiment._reads_phase)
        return ProgressiveRatioExperiment._firmware_columns(host, dfm, 1, onsets)

    with_program = columns(SimpleNamespace(paradigms={"PRX": prx}))
    assert list(with_program["Requirement"]) == [1, 3]
    assert list(with_program["FirmwareEvents"])[1] == 3
    assert list(with_program["Phase"]) == ["M", "M"]
    without = columns(None)
    assert pd.isna(without["Requirement"][0]) and without["Requirement"][1] == 3


# ---------------------------------------------------------------------------
# Breaking Point (ADR-0014 addendum)
# ---------------------------------------------------------------------------

def test_the_breaking_point_reports_the_requirement_it_reached(gen3):
    e, _results = gen3
    summary = e.breaking_point_summary().set_index(["DFM", "Group"])
    ledger = e.light_events_ledger()
    assert len(summary)
    for (dfm_id, group), row in summary.iterrows():
        counted = ledger[(ledger.DFM == dfm_id) & (ledger.Group == group) & ledger.Counted]
        assert row["BreakingPoint"] == len(counted)
        assert row["BreakRequirement"] == counted["Requirement"].iloc[-1]
        assert row["LargestRequirement"] == row["BreakRequirement"]
        assert row["FirmwareEvents"] == counted["FirmwareEvents"].sum()
    for dfm_id, group in groups_of("healthy"):
        n = int(summary.loc[(dfm_id, group), "BreakingPoint"])
        assert summary.loc[(dfm_id, group), "BreakRequirement"] == 1 + 10 * (n - 1)
    ## The text and the report put it beside the Breaking Point.
    lines = "\n".join(e.breaking_point_lines())
    assert "BreakingPoint BreakReq" in lines
    blocks = e.report_results_blocks([], SimpleNamespace(include_comparison=False))
    tables = [b for b in blocks if isinstance(b, rl.Table) and "Breaking point" in b.frame.columns]
    columns = list(tables[0].frame.columns)
    assert columns[columns.index("Breaking point") + 1] == "Break requirement"
    assert any(isinstance(b, rl.Heading) and b.text == "Breaking point" for b in blocks)


def test_the_project_report_shows_the_break_requirement_beside_the_breaking_point(gen3):
    e, _results = gen3
    view = break_requirement_view(e.breaking_point_summary())
    columns = list(view.columns)
    assert columns[columns.index("Breaking point") + 1] == "Break requirement"
    ctrl = view.set_index("Treatment").loc["Ctrl"]
    assert ctrl["Break requirement"] == 31 and ctrl["Groups"] == 2
    ## Nothing new for a project of generation-1 members.
    old = e.breaking_point_summary().assign(BreakRequirement=pd.NA)
    assert break_requirement_view(old) is None
    assert break_requirement_view(old.drop(columns="BreakRequirement")) is None


def test_the_project_pools_the_break_requirement(tmp_path):
    from pyflic.base.project import Project
    from pyflic.base.project_report import build_project_report

    spec, results = choice()
    root = tmp_path / "proj"
    design = None
    for name in ("rep1", "rep2"):
        member = pr_dir(root / name, spec, results)
        cfg = yaml.safe_load((member / "flic_config.yaml").read_text())
        design = design or cfg.pop("global")
        cfg.pop("global", None)
        (member / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": design}}, sort_keys=False))
    project = Project(root)
    for name in project.member_names:
        project.load_member(name, parallel=False,
                            use_disk_cache=False).execute_basic_analysis(skip_qc=True)
    project.build_combined_analysis()
    pooled = pd.read_csv(root / "analysis" / "proj_BreakingPoint.csv")
    assert {"BreakRequirement", "FirmwareEvents"} <= set(pooled.columns)
    text = (root / "analysis" / "proj_Stats.txt").read_text(encoding="utf-8")
    line = next(t for t in text.splitlines() if t.startswith("Break requirement"))
    assert "Ctrl BreakingPoint 4, BreakRequirement 31" in line
    doc = build_project_report(project)
    tables = [b for b in doc.blocks if isinstance(b, rl.Table)
              and (b.caption or "").startswith("Breaking point and the Requirement")]
    assert tables and "Break requirement" in tables[0].frame.columns


def test_light_on_seconds_are_the_on_ms_of_the_chamber(gen3):
    e, results = gen3
    summary = e.feeding_summary()
    for _, row in summary.iterrows():
        rows = results[int(row["DFM"])].rows
        a, b = 2 * int(row["Chamber"]) - 1, 2 * int(row["Chamber"])
        expected = np.maximum(rows[f"OnMs{a}"].to_numpy(), rows[f"OnMs{b}"].to_numpy()).sum()
        assert row["LightOn_sec"] == pytest.approx(expected / 1000.0)
    ## Over a Facet's window, the rows inside it.
    facet = e.feeding_summary_facet()
    test = facet[(facet.Facet == "Test") & (facet.DFM == 1) & (facet.Chamber == 1)].iloc[0]
    dfm = e.dfms[1]
    inside = dfm.paradigm.minutes > float(test["StartMin"])
    assert test["LightOn_sec"] == pytest.approx(
        dfm.paradigm.on_ms[inside][:, [0, 1]].max(axis=1).sum() / 1000.0)


# ---------------------------------------------------------------------------
# The trend on Firmware Events
# ---------------------------------------------------------------------------

def _judge(**overrides):
    kwargs = dict(training_complete=True, training_light_events=3, training_licks=20,
                  test_counts=np.array([5, 5, 5, 5, 5, 5]), resting={"start": 8, "max": 8,
                                                                     "end": 8, "level": 8},
                  reference_level=8.0, any_light=True)
    kwargs.update(overrides)
    return lqc.judge_group(lqc.LightQCSettings(), **kwargs)


def test_firmware_events_witness_the_trend_but_do_not_set_the_warning():
    rising = np.array([1, 11, 21, 31, 41, 51], dtype=float)
    flat = _judge(firmware_events=rising)
    assert lqc.NO_TREND in flat.flags
    assert lqc.FIRMWARE_TREND_NOTE in flat.notes
    assert flat.trend_rho_firmware == pytest.approx(1.0)
    ## Licks that rise with it: no warning, no note.
    both = _judge(test_counts=np.array([2, 12, 20, 33, 40, 55]), firmware_events=rising)
    assert lqc.NO_TREND not in both.flags and lqc.FIRMWARE_TREND_NOTE not in both.notes
    ## Neither rising: the warning, no note; NA Events are left out.
    neither = _judge(firmware_events=np.array([5, 5, np.nan, 5, 5, 5]))
    assert lqc.NO_TREND in neither.flags and lqc.FIRMWARE_TREND_NOTE not in neither.notes
    ## Generation 1 has none to give.
    assert np.isnan(_judge().trend_rho_firmware)


def test_the_drifting_group_gets_the_detection_note(gen3):
    e, _results = gen3
    table = e.light_qc_table().set_index(["DFM", "Group"])
    for dfm_id, group in groups_of("drifting"):
        row = table.loc[(dfm_id, group)]
        assert lqc.NO_TREND in row["Flags"]
        assert row["TrendRhoFirmware"] == pytest.approx(1.0)
        assert lqc.FIRMWARE_TREND_NOTE in row["Notes"]
    ## The note is one line in the summary, not split at its semicolon.
    lines = e.light_qc_lines()
    assert any(line.strip() == f"· {lqc.FIRMWARE_TREND_NOTE}" for line in lines)


# ---------------------------------------------------------------------------
# FixedRatio (decision 14)
# ---------------------------------------------------------------------------

def test_a_fixed_ratio_breaks_at_its_ratio_without_a_trend_check(fr):
    e, _results = fr
    assert e.test_paradigm(1, 1)[0] == "FR5"
    assert e.test_paradigm(1, 1)[1].type == op.FIXED_RATIO
    summary = e.breaking_point_summary()
    assert len(summary) == 3
    assert (summary["BreakRequirement"] == 5).all()
    assert (summary["LargestRequirement"] == 5).all()
    assert (summary["FirmwareEvents"] == 5 * summary["BreakingPoint"]).all()
    table = e.light_qc_table()
    assert (table["TestLightEvents"] >= lqc.LightQCSettings().trend_min_events).all()
    assert not table["Flags"].str.contains(lqc.NO_TREND).any()
    ledger = e.light_events_ledger()
    assert (ledger["Requirement"] == 5).all()
    blocks = e.report_results_blocks([], SimpleNamespace(include_comparison=False))
    headings = [b.text for b in blocks if isinstance(b, rl.Heading)]
    assert "Fixed ratio: activations earned" in headings
    assert "Breaking point" not in headings


def test_without_a_program_the_type_is_unknown_and_taken_as_progressive(tmp_path):
    spec, results = fixed()
    e = load(pr_dir(tmp_path, spec, results, program=False))
    assert e.test_paradigm(1, 1) == ("FR5", None)
    table = e.light_qc_table()
    assert table["Notes"].str.contains("type is unknown").all()
    ## Judged as progressive: the trend check runs, and the rows still show 5.
    assert not table["Notes"].str.contains("fixed ratio").any()
    assert (e.breaking_point_summary()["BreakRequirement"] == 5).all()


# ---------------------------------------------------------------------------
# Generation 2 (decision 15)
# ---------------------------------------------------------------------------

def test_generation_2_is_one_recording_facet_with_no_removals(gen2, tmp_path):
    e, _results = gen2
    assert e.training_information() == NO_TRAINING_INFORMATION
    assert e.facet_labels() == ["Recording"]
    facet = e.feeding_summary_facet()
    assert set(facet["Facet"]) == {"Recording"} and len(facet) == 12
    assert facet["PersistA"].isna().all()
    table = e.training_table()
    assert table["TrainingComplete"].isna().all()
    assert (table["Notes"] == NO_TRAINING_INFORMATION).all()
    qc = e.light_qc_table()
    assert qc["TrainingComplete"].isna().all()
    assert not qc["Flags"].str.contains(lqc.IMPLAUSIBLE_TRAINING).any()
    assert e.breaking_point_summary().empty
    diff = e.paired_yoked_diff()
    assert set(diff["Facet"]) == {"Recording"} and diff["TrainingComplete"].isna().all()
    ## require_training_complete removes nothing: there is nothing to judge.
    removed = e.auto_remove_chambers()
    assert not removed["Reason"].str.contains("training").any()
    assert e.light_qc_table()["Excluded"].sum() == 0


def test_generation_2_says_so_in_the_summary_and_the_report(gen2):
    e, _results = gen2
    summary = e.summary_text(include_qc=False)
    assert NO_TRAINING_INFORMATION in summary
    assert "no Breaking Point or Sucrose Persistence" in summary
    callouts = [b for b in e.report_glance_blocks() if isinstance(b, rl.Callout)]
    assert any(NO_TRAINING_INFORMATION in b.text for b in callouts)
    ## Not reported as a training that failed.
    assert not any("Training never completed" in b.text for b in callouts)


@pytest.mark.parametrize("writer", [write_v4_recording, write_gen2_recording],
                         ids=["gen3", "gen2"])
def test_the_pipeline_and_the_report_run(tmp_path, writer):
    from pyflic.base.pdf_report import build_experiment_report

    spec, results = choice()
    root = pr_dir(tmp_path / "exp", spec, results, writer=writer)
    e = load(root)
    e.execute_basic_analysis(skip_qc=True)
    analysis = root / "analysis"
    for name in e.experiment_type.output_manifest():
        assert (analysis / name).is_file(), name
    summary = (analysis / "summary.txt").read_text(encoding="utf-8")
    assert (NO_TRAINING_INFORMATION in summary) == (writer is write_gen2_recording)
    doc = build_experiment_report(load(root), metrics=("Licks",))
    assert doc.save(tmp_path / "report.pdf").stat().st_size > 0


def test_a_mixed_experiment_has_the_union_of_the_facets(tmp_path):
    spec, results = choice()
    data = tmp_path / "data"
    write_v4_recording(data, spec, results={1: results[1]}, program=False, messages=False)
    write_gen2_recording(data, spec, results={2: results[2]}, program=False, messages=False)
    (data / "Program.txt").write_text(program_text(spec), encoding="utf-8")
    write_config(tmp_path, [1, 2])
    e = load(tmp_path)
    assert [e.dfms[d].generation for d in (1, 2)] == [3, 2]
    assert e.facet_labels() == ["Training", "Test", "Recording"]
    assert e.training_information() == f"DFM 2: {NO_TRAINING_INFORMATION}"
    facet = e.feeding_summary_facet()
    assert set(facet.loc[facet.DFM == 2, "Facet"]) == {"Recording"}
    assert {"Training", "Test"} <= set(facet.loc[facet.DFM == 1, "Facet"])
    assert set(e.breaking_point_summary()["DFM"]) == {1}
