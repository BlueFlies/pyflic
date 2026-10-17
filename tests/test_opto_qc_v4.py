"""The optogenetic light QC on a firmware 4.0.0 recording (generation 3).

``docs/v4-data-plan.md``, stream 3, and ADR-0015's addendum: the rows are the
schedule, each Activation owns its light, the firmware's own Activations and
Firmware Events replace the Emulated Trigger, and five more checks read the
file's bookkeeping.  Every recording comes from the simulator
(``v4_fixtures``), loaded through a ``flic_config.yaml`` as a user's would be;
a check that needs a fault gets it by editing the simulated rows before they
are written, as a faulty board or the wrong ``Program.txt`` would.
"""

from __future__ import annotations

import contextlib
import io
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import opto_program as op
from pyflic.base import opto_qc as oq
from pyflic.base.yaml_config import load_experiment_yaml

from v4_fixtures import (
    CHOICE_PR_CASES,
    SimResult,
    choice_pr_spec,
    fixed_ratio_spec,
    one_of_each_spec,
    program_text,
    repeating_open_loop_spec,
    simulate,
    write_gen2_recording,
    write_v4_recording,
    yoked_controls_spec,
)

FIXTURES = Path(__file__).parent / "fixtures"
SPECS = {
    "choice": lambda: choice_pr_spec(),
    "choice1": lambda: choice_pr_spec(dfm_ids=(1,)),
    "one_of_each": lambda: one_of_each_spec(),
    "yoked": lambda: yoked_controls_spec(minutes=12.0),
    "fixed_ratio": lambda: fixed_ratio_spec(minutes=15.0),
    "repeating": lambda: repeating_open_loop_spec(),
}


@lru_cache(maxsize=None)
def simulated(name: str):
    spec = SPECS[name]()
    return spec, simulate(spec)


def _config(dfm_ids) -> dict:
    """A Custom two-well config, A wells on the left, every chamber assigned."""
    params = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
              "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}
    return {"global": {"chamber_layout": "two_well", "transform_licks": False,
                       "params": params},
            "dfms": [{"id": int(i), "chambers": {c: ("Ctrl" if c % 2 else "Exp")
                                                 for c in range(1, 7)}}
                     for i in dfm_ids]}


def load(root: Path, name: str, *, edit=None, program_text_override: str | None = None,
         writer=write_v4_recording, **kw):
    """The recording *name* written to *root* and loaded; *edit* changes the
    simulated rows (``{dfm: DataFrame}``, in place) before they are written."""
    spec, results = simulated(name)
    if edit is not None:
        results = {k: SimResult(v.rows.copy(), v.truth) for k, v in results.items()}
        edit({k: v.rows for k, v in results.items()})
    root.mkdir(parents=True, exist_ok=True)
    writer(root / "data", spec, results=results, **kw)
    if program_text_override is not None:
        (root / "data" / "Program.txt").write_text(program_text_override, encoding="utf-8")
    (root / "flic_config.yaml").write_text(
        yaml.safe_dump(_config([d.dfm_id for d in spec.dfms]), sort_keys=False))
    with contextlib.redirect_stdout(io.StringIO()):
        return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


def _groups(e, dfm_id: int) -> pd.DataFrame:
    table = e.opto.qc_table()
    return table[table["DFM"] == dfm_id].set_index("Group")


def _flags(row) -> list[str]:
    return [f for f in str(row["Flags"]).split(", ") if f and f != "nan"]


@pytest.fixture(scope="module")
def choice(tmp_path_factory):
    return load(tmp_path_factory.mktemp("choice"), "choice")


@pytest.fixture(scope="module")
def one_of_each(tmp_path_factory):
    return load(tmp_path_factory.mktemp("one"), "one_of_each")


@pytest.fixture(scope="module")
def yoked(tmp_path_factory):
    return load(tmp_path_factory.mktemp("yoked"), "yoked")


# ---------------------------------------------------------------------------
# The acceptance cases
# ---------------------------------------------------------------------------

def test_every_paradigm_type_of_a_healthy_rig_is_ok(one_of_each):
    """One DFM per Paradigm type, every fly healthy: every group ok, none with
    an unexplained-light flag.  What little light is unexplained is pyflic's
    detector starting a few samples into a scripted bout or missing a short
    one (as on generation 1), under ``opto_unexplained_min_sec`` throughout."""
    table = one_of_each.opto.qc_table()
    assert len(table) == 36 and set(table["Generation"]) == {3}
    assert (table["Verdict"] == "ok").all(), table[["DFM", "Group", "Flags"]]
    assert (table["Flags"] == "").all()
    assert (table["UnexplainedSec"] < oq.DEFAULT_CONSTANTS["opto_unexplained_min_sec"]).all()
    assert table["UnexplainedFraction"].median() < 0.02
    assert table["EmulationApproximate"].isna().all()
    by = table.set_index(["DFM", "Group"])
    ## OpenLoop: On wells lit throughout, every chamber Open, nothing judged.
    assert (by.loc[1, "OpenLoopLitFraction"] == 1.0).all()
    assert set(by.loc[1, "Roles"]) == {f"{c} Open" for c in range(1, 7)}
    assert (by.loc[1, "LightEvents"] == 0).all()
    ## NonFeeding: Activations counted, light not judged against licks.
    assert (by.loc[4, "JudgedLitSec"] == 0).all() and (by.loc[4, "LightEvents"] > 0).all()
    ## The ratio DFMs compare Firmware Events with pyflic's events.
    for dfm in (5, 6):
        assert by.loc[dfm, "FirmwareEvents"].notna().all()
        share = (by.loc[dfm, "FirmwareEvents"] - by.loc[dfm, "PyflicEvents"]).abs() \
            / by.loc[dfm, "FirmwareEvents"]
        assert (share < oq.DEFAULT_CONSTANTS["opto_event_disagreement_warn_fraction"]).all()
    assert by.loc[1, "FirmwareEvents"].isna().all()


def test_the_choice_rig_names_the_drifting_and_the_dead_led_groups(choice):
    for dfm_id in (1, 2):
        groups = _groups(choice, dfm_id)
        for chamber, case in CHOICE_PR_CASES.items():
            row = groups.loc[chamber]
            flags = _flags(row)
            if case == "drifting":
                assert row["Verdict"] == "failed"
                assert flags[0] == oq.UNEXPLAINED
                assert row["LikelyCause"] == oq.CAUSE_DRIFT
                ## Every lit second of it came from Activations no lick explains.
                assert row["ContactWithoutActivitySec"] == pytest.approx(
                    row["ContactSec"])
                assert row["FirmwareEventsWithoutActivity"] > 100
                assert oq.EVENT_DISAGREEMENT in flags
            elif case == "dead_led":
                assert row["Verdict"] == "warning"
                assert flags == [oq.UNLIT_FEEDING, oq.NO_LIGHT_EVENTS]
                assert row["UnlitFeedingEvents"] == row["ClosedLoopFeedingEvents"] > 50
                ## Never left Acclimation: never completed, so no mismatch.
                assert pd.isna(row["AcclimationActivations"])
            else:
                assert row["Verdict"] == "ok", (dfm_id, chamber, case, flags)
            assert row["Roles"] == f"{chamber} Self"


def test_activations_are_the_light_events_and_carry_their_requirement(choice):
    """Each trigger-well Activation is one event: the healthy groups'
    Acclimation ten, then Main Activations meeting 1, 11, 21, ...; the count
    is the simulator's own."""
    spec, results = simulated("choice")
    events = choice.opto.events_table()
    assert set(events["Source"]) == {oq.EVENT_SOURCE_ACTIVATIONS}
    groups = _groups(choice, 1)
    for chamber in (1, 2, 6):
        well = 2 * chamber - 1
        mine = events[(events["DFM"] == 1) & (events["Group"] == chamber)]
        assert (mine["Well"] == well).all()
        assert len(mine) == len(results[1].truth.activation_onset_ms[well])
        assert groups.loc[chamber, "LightEvents"] == len(mine)
        acclimation = mine[mine["Phase"] == "A"]
        assert len(acclimation) == 10 and (acclimation["FirmwareEvents"] == 1).all()
        main = mine[(mine["Phase"] == "M") & (mine["Mode"] == op.PROGRESSIVE_RATIO)]
        met = [m for m, p in zip(results[1].truth.requirement_met[well],
                                 results[1].truth.activation_phase[well])
               if m is not None and p == "M"]
        assert main["RequirementMet"].astype(int).tolist() == met
        assert met[:3] == [1, 11, 21]
        assert (main["FirmwareEvents"] == main["RequirementMet"]).all()
        assert main["Explained"].all()
        assert groups.loc[chamber, "AcclimationActivations"] == 10
        assert groups.loc[chamber, "AcclimationExpected"] == 10


def test_the_rows_are_the_windows(choice):
    intervals = choice.opto.interval_table()
    mine = intervals[(intervals["DFM"] == 1) & (intervals["Group"] == 1)]
    assert mine["ProgramInterval"].tolist() == [1, 2]
    assert mine["Interval"].tolist() == [1, 2]
    assert mine["Cycle"].tolist() == [1, 1]
    assert mine["Paradigm"].tolist() == ["Closed", "PR10"]
    assert mine["ParadigmType"].tolist() == ["ClosedLoop", "ProgressiveRatio"]
    assert mine["HoldMs"].tolist() == [500, 500]
    assert set(mine["LitSource"]) == {oq.LIT_SOURCE_ON_MS}
    ## Lit seconds are the exact OnMs sums of the window's rows.
    state = choice.dfms[1].paradigm
    runs = [r for r in state.interval_runs() if r.kind == "program"]
    assert mine["LitSec"].tolist() == pytest.approx(
        [state.lit_seconds(1, r.i0, r.i1) for r in runs])
    assert int(choice.opto.decay_samples(1)[-1]) == 3            # 500 ms at 5 Hz
    ## The same profile for a DFM the QC does not cover, from its rows.
    minutes = choice.dfms[1].raw_df["Minutes"].to_numpy(dtype=float)
    profile = oq.decay_profile(1, minutes, 5, None, choice.opto.program,
                               oq.OptoQCSettings(), state=state)
    assert np.array_equal(profile, choice.opto.result(1).decay_samples)
    ## The baseline lead-in has no Hold of its own: the design's fallback.
    assert profile[0] == oq.decay_samples_for(1000, 5)


def test_yoked_controls_keep_their_yoking(yoked):
    groups = _groups(yoked, 1)
    assert (groups["Verdict"] == "ok").all(), groups["Flags"]
    assert groups["Roles"].tolist() == ["1 Paired, 4 Yoked", "2 Paired, 5 Yoked",
                                        "3 Paired, 6 Yoked"]
    assert groups["TriggerWells"].tolist() == ["W1", "W3", "W5"]


def test_an_off_well_with_activations_breaks_the_yoking(tmp_path):
    def edit(rows):
        frame = rows[1]
        lit = np.flatnonzero(frame["OnMs1"].to_numpy(dtype=float) > 0)
        ## W7 is Off and linked to W1: give it an Activation of its own.
        frame["Activations7"] = pd.array(
            (np.arange(len(frame)) >= lit[len(lit) // 2]).astype(np.int64), dtype="Int64")

    e = load(tmp_path / "exp", "yoked", edit=edit)
    row = _groups(e, 1).loc[1]
    assert row["Verdict"] == "failed" and oq.YOKING_BROKEN in _flags(row)
    text = "\n".join(e.opto.lines())
    assert "W7 is Off and linked to a trigger well but counted 1 Activation(s)" in text
    assert _groups(e, 1).loc[2, "Verdict"] == "ok"


def test_linked_wells_whose_light_differs_break_the_yoking(tmp_path):
    def edit(rows):
        frame = rows[1]
        on = frame["OnMs7"].to_numpy(dtype=np.int64).copy()
        lit = np.flatnonzero(on > 0)
        on[lit[::20]] = np.maximum(on[lit[::20]] - 50, 0)        # 5% of lit records
        frame["OnMs7"] = pd.array(on, dtype="Int64")

    e = load(tmp_path / "exp", "yoked", edit=edit)
    row = _groups(e, 1).loc[1]
    assert row["Verdict"] == "failed" and _flags(row) == [oq.YOKING_BROKEN]
    assert "OnMs differ by more than 1 ms in" in "\n".join(e.opto.lines())
    ## Above the design's own fraction it passes.
    root = tmp_path / "lenient"
    e = load(root, "yoked", edit=edit)
    e.global_constants["opto_yoking_fail_fraction"] = 0.2
    assert _groups(e, 1).loc[1, "Verdict"] == "ok"


def test_a_row_paradigm_absent_from_the_program_fails_every_group(tmp_path):
    def edit(rows):
        frame = rows[1]
        frame["Paradigm"] = frame["Paradigm"].replace("PR10", "PR20")

    e = load(tmp_path / "exp", "choice1", edit=edit)
    result = e.opto.result(1)
    assert result.flags == [oq.PARADIGM_NOT_IN_PROGRAM]
    groups = _groups(e, 1)
    assert (groups["Verdict"] == "failed").all()
    assert all(oq.PARADIGM_NOT_IN_PROGRAM in _flags(r) for _, r in groups.iterrows())
    assert any("PR20 (Program Interval 2)" in n for n in result.notes)
    intervals = e.opto.interval_table()
    assert set(intervals.loc[intervals["ProgramInterval"] == 2, "Mode"]) == {oq.NOT_JUDGED}


def test_a_row_paradigm_other_than_the_printed_line_is_a_mismatch(tmp_path):
    """The rows win (ADR-0016): judged by the Paradigm they name, and the
    program flagged as disagreeing."""
    def edit(rows):
        frame = rows[1]
        frame["Paradigm"] = frame["Paradigm"].replace("Closed", "PR10")

    e = load(tmp_path / "exp", "choice1", edit=edit)
    result = e.opto.result(1)
    assert result.flags == [oq.PROGRAM_MISMATCH]
    assert any("Program Interval(s) 1 (PR10, printed Closed)" in n for n in result.notes)
    intervals = e.opto.interval_table()
    first = intervals[(intervals["Group"] == 1) & (intervals["ProgramInterval"] == 1)]
    assert first["Mode"].tolist() == [op.PROGRESSIVE_RATIO]


def test_an_acclimation_short_of_the_paradigms_count_warns(tmp_path):
    spec, results = simulated("choice1")
    truth = results[1].truth

    def edit(rows):
        frame = rows[1]
        ## Take W1's fifth Acclimation Activation out of the count.
        onset = truth.activation_onset_ms[1][[p for p in truth.activation_phase[1]]
                                             .index("A") + 4]
        values = frame["Activations1"].to_numpy(dtype=np.int64).copy()
        values[onset // 200:] -= 1
        frame["Activations1"] = pd.array(values, dtype="Int64")

    e = load(tmp_path / "exp", "choice1", edit=edit)
    groups = _groups(e, 1)
    row = groups.loc[1]
    assert row["Verdict"] == "warning" and _flags(row) == [oq.ACCLIMATION_COUNT_MISMATCH]
    assert (row["AcclimationActivations"], row["AcclimationExpected"]) == (9, 10)
    assert "W1 counted 9 Activations in Acclimation" in "\n".join(e.opto.lines())
    assert groups.loc[2, "Verdict"] == "ok"


def test_lost_records_warn_the_dfm(tmp_path):
    e = load(tmp_path / "exp", "choice", index_gaps={2: [(3000, 40)]})
    assert e.opto.result(2).flags == [oq.LOST_RECORDS]
    assert oq.LOST_RECORDS not in e.opto.result(1).flags
    assert all(oq.LOST_RECORDS in _flags(r) for _, r in _groups(e, 2).iterrows())
    assert any("40 record(s) (8.0 s) missing from Index in 1 gap(s)" in n
               for n in e.opto.result(2).notes)
    few = load(tmp_path / "few", "choice", index_gaps={2: [(3000, 10)]})
    assert oq.LOST_RECORDS not in few.opto.result(2).flags


def test_late_and_unknown_instruction_rows_warn_the_dfm(tmp_path):
    def edit(rows):
        frame = rows[1]
        on = frame["OnMs3"].to_numpy(dtype=np.int64).copy()
        on[5000:5011] = 230                                      # 11 late records
        frame["OnMs3"] = pd.array(on, dtype="Int64")
        interval = frame["Interval"].copy()
        interval.iloc[6000:6200] = pd.NA                         # 2% unknown
        frame["Interval"] = interval

    e = load(tmp_path / "exp", "choice1", edit=edit)
    flags = e.opto.result(1).flags
    assert flags == [oq.UNKNOWN_INSTRUCTION_ROWS, oq.LATE_RECORDS]
    notes = "\n".join(e.opto.result(1).notes)
    assert "11 record(s) with an OnMs above 200 ms" in notes
    assert "200 of the" in notes
    assert oq.UNKNOWN_INSTRUCTION in set(e.opto.interval_table()["Mode"])


def test_without_a_program_the_data_give_the_linkage_and_nothing_fails(tmp_path):
    e = load(tmp_path / "exp", "choice1", program=False)
    result = e.opto.result(1)
    assert result.program_status == oq.PROGRAM_NO_FILE
    assert result.flags == [oq.PROGRAM_MISSING]
    groups = _groups(e, 1)
    ## The dead LED's group never lit and counted nothing: the data cannot
    ## see it.  The rest are the identical-OnMs pairs, with their Roles.
    assert groups["Wells"].tolist() == ["W1, W2", "W3, W4", "W5, W6", "W9, W10",
                                        "W11, W12"]
    assert groups["Linkage"].isna().all()
    drifting = groups.loc[3]
    assert _flags(drifting) == [oq.UNEXPLAINED_NO_PROGRAM, oq.PROGRAM_MISSING]
    assert drifting["Verdict"] == "warning" and drifting["LikelyCause"] == oq.CAUSE_DRIFT
    assert pd.isna(drifting["AcclimationExpected"])
    notes = e.opto.experiment_notes()
    assert any(n.startswith("no Program.txt for DFM 1, recorded with DFM firmware 4.0.0")
               for n in notes)


def test_an_interval_beyond_the_printed_lines_is_judged_by_its_paradigm(tmp_path):
    spec, _results = simulated("choice1")
    text = program_text(spec)
    lines = text.splitlines()
    pr_line = next(i for i, line in enumerate(lines)
                   if line.startswith("(") and ", PR10, " in line)
    shortened = "\n".join(lines[:pr_line] + lines[pr_line + 1:]) + "\n"
    e = load(tmp_path / "exp", "choice1", program_text_override=shortened)
    result = e.opto.result(1)
    assert any("Program Interval(s) 2 are beyond the lines Program.txt prints" in n
               for n in result.notes)
    groups = _groups(e, 1)
    assert groups.loc[3, "Verdict"] == "failed"
    assert groups.loc[3, "LikelyCause"] == oq.CAUSE_DRIFT
    assert groups.loc[1, "Verdict"] == "ok"
    intervals = e.opto.interval_table()
    second = intervals[(intervals["Group"] == 1) & (intervals["ProgramInterval"] == 2)]
    assert second["Mode"].tolist() == [op.PROGRESSIVE_RATIO]
    assert second["Interval"].isna().all() and second["TriggerWells"].tolist() == ["W1"]


def test_a_recording_made_without_a_program_is_judged_every_well_off(tmp_path):
    simple = (FIXTURES / "Program_simple.txt").read_text(encoding="utf-8")
    lit = load(tmp_path / "lit", "choice1", program_text_override=simple)
    result = lit.opto.result(1)
    assert result.program_status == oq.PROGRAM_ALL_OFF and result.flags == []
    groups = _groups(lit, 1)
    assert (groups["Verdict"] == "failed").all()
    assert all(_flags(r) == [oq.LIGHT_WHILE_OFF] for _, r in groups.iterrows())
    assert (groups["LitWhileOffSec"] == groups["LitSec"]).all()

    def dark(rows):
        for w in range(1, 13):
            rows[1][f"OnMs{w}"] = pd.array(np.zeros(len(rows[1]), dtype=np.int64),
                                           dtype="Int64")
            rows[1][f"Activations{w}"] = pd.array(np.zeros(len(rows[1]), dtype=np.int64),
                                                  dtype="Int64")
        rows[1]["OptoCol1"] = 0

    e = load(tmp_path / "dark", "choice1", edit=dark, program_text_override=simple)
    e.optogenetics = "yes"
    table = e.opto.qc_table()
    assert table["Verdict"].tolist() == ["ok"]
    assert not any(oq.NO_PROGRAM_SECTION in f or oq.PROGRAM_MISSING in f
                   for f in table["Flags"])


def test_non_feeding_light_that_stays_on_through_feeding_warns(tmp_path):
    def edit(rows):
        frame = rows[4]
        for w in (1, 2):                                          # group 1, W1 + W2
            frame[f"OnMs{w}"] = pd.array(np.where(frame["Interval"].to_numpy(
                dtype=float, na_value=0) > 0, 200, 0).astype(np.int64), dtype="Int64")

    e = load(tmp_path / "exp", "one_of_each", edit=edit)
    groups = _groups(e, 4)
    assert _flags(groups.loc[1]) == [oq.NON_FEEDING_LIT_WHILE_FEEDING]
    assert groups.loc[1, "Verdict"] == "warning"
    assert (groups.drop(index=1)["Verdict"] == "ok").all()
    assert "under a NonFeeding Paradigm, whose light goes out while the fly feeds" in \
        "\n".join(e.opto.lines())


def test_a_fixed_ratio_counts_its_acclimation_and_its_ratio(tmp_path):
    e = load(tmp_path / "exp", "fixed_ratio")
    groups = _groups(e, 1)
    assert (groups["Verdict"] == "ok").all()
    assert (groups["AcclimationActivations"] == 3).all()
    assert (groups["AcclimationExpected"] == 3).all()
    events = e.opto.events_table()
    main = events[(events["Phase"] == "M")]
    assert set(main["RequirementMet"]) == {5} and set(main["FirmwareEvents"]) == {5}
    assert any("runs a fixed ratio, but the experiment type is" in n
               for n in e.opto.experiment_notes())


def test_a_repeating_open_loop_is_lit_then_off(tmp_path):
    e = load(tmp_path / "exp", "repeating")
    table = e.opto.qc_table()
    assert (table["Verdict"] == "ok").all()
    assert set(table["Paradigm"]) == {f"{op.OPEN_LOOP}, {op.LIGHTS_OFF}"}
    intervals = e.opto.interval_table()
    mine = intervals[intervals["Group"] == 1]
    assert mine["ProgramInterval"].tolist() == [1, 2, 1, 2, 1, 2]
    assert mine["Cycle"].tolist() == [1, 1, 2, 2, 3, 3]
    assert mine["Occurrence"].tolist() == [1, 1, 2, 2, 3, 3]


def test_generation_2_keeps_the_clock_schedule_and_leaves_the_new_columns_na(tmp_path):
    e = load(tmp_path / "exp", "choice1", writer=write_gen2_recording)
    table = e.opto.qc_table()
    assert set(table["Generation"]) == {2}
    for column in ("Roles", "FirmwareEvents", "PyflicEvents", "AcclimationActivations",
                   "AcclimationExpected", "FirmwareEventsWithoutActivity"):
        assert table[column].isna().all(), column
    intervals = e.opto.interval_table()
    assert set(intervals["LitSource"]) == {oq.LIT_SOURCE_OPTOCOL1}
    assert intervals["ProgramInterval"].isna().all() and intervals["Paradigm"].isna().all()
    assert set(e.opto.events_table()["Source"]) == {oq.EVENT_SOURCE_OPTOCOL1}
    assert any(n.startswith("DFM generations: DFM 1 generation 2")
               for n in e.opto.experiment_notes())


# ---------------------------------------------------------------------------
# Words, figures, editors
# ---------------------------------------------------------------------------

def test_the_summary_and_report_name_the_new_flags_with_their_numbers(choice, tmp_path):
    from pyflic.base import report_layout as rl

    lines = "\n".join(choice.opto.summary_lines())
    assert "Firmware 4.0.0 checks: opto_event_disagreement_warn_fraction=0.25" in lines
    assert "firmware events disagree under the ratio Paradigm's Main phase: W5" in lines
    assert "Activations whose onset had no pyflic lick or touch" in lines
    assert "DFM generations: DFM 1, 2 generation 3" in lines
    bullets = [b for b in choice.opto.report_qc_blocks() if isinstance(b, rl.Bullets)]
    assert any("firmware events disagree under the ratio Paradigm's Main phase" in item
               for b in bullets for item in b.items)
    tables = [b for b in choice.opto.report_qc_blocks() if isinstance(b, rl.Table)]
    verdicts = next(t.frame for t in tables if t.caption == "Opto light QC by linkage group")
    assert verdicts["Roles"].tolist()[:2] == ["1 Self", "2 Self"]


def test_the_figure_weights_by_on_ms_and_names_the_firmware_events(choice):
    fig = choice.opto.plot_dfm(1, binsize_min=5)
    panels = set(fig.data["Panel"].astype(str))
    assert any(p.endswith("firmware events, no lick (s per bin)") for p in panels)
    ## The stacked light adds up to the OnMs seconds.
    light = fig.data[fig.data["Panel"].astype(str).str.endswith("light (s per bin)")
                     & fig.data["Panel"].astype(str).str.startswith("Group 1 ")]
    assert light["Seconds"].sum() == pytest.approx(_groups(choice, 1).loc[1, "LitSec"])
    fig.draw()


def test_the_qc_viewer_tab_shows_roles():
    pytest.importorskip("PyQt6")
    from pyflic.base.qc_viewer import OptoTab

    assert ("Roles", "Roles") in OptoTab._COLUMNS


def test_a_ratio_paradigm_under_the_progressive_ratio_type_is_not_noted(tmp_path):
    from pyflic.base.experiment_types import get_experiment_type

    e = load(tmp_path / "fr", "fixed_ratio")
    e.experiment_type = get_experiment_type("ProgressiveRatio")
    assert not any("Program.txt runs" in n for n in e.opto.experiment_notes())
    closed = load(tmp_path / "closed", "yoked")
    closed.experiment_type = get_experiment_type("ProgressiveRatio")
    assert any("runs no progressive-ratio or fixed-ratio interval" in n
               for n in closed.opto.experiment_notes())


# ---------------------------------------------------------------------------
# The five constants
# ---------------------------------------------------------------------------

NEW_CONSTANTS = {"opto_event_disagreement_warn_fraction": 0.25,
                 "opto_yoking_fail_fraction": 0.01, "opto_lost_records_warn": 25,
                 "opto_unknown_rows_warn_fraction": 0.01, "opto_late_records_warn": 10}


def test_the_five_constants_are_defaults_fields_and_validated(tmp_path):
    from pyflic.base.yaml_lint import lint_flic_config

    for key, default in NEW_CONSTANTS.items():
        assert oq.DEFAULT_CONSTANTS[key] == default
    assert set(NEW_CONSTANTS) <= {f.key for f in oq.OPTO_CONSTANT_FIELDS}
    settings = oq.OptoQCSettings.from_constants({"opto_lost_records_warn": 100,
                                                 "opto_yoking_fail_fraction": 0.05})
    assert (settings.lost_records_warn, settings.yoking_fail_fraction) == (100, 0.05)
    assert settings.late_records_warn == 10
    problems = oq.opto_constant_problems({"opto_yoking_fail_fraction": 2,
                                          "opto_lost_records_warn": 2.5,
                                          "opto_unknown_rows_warn_fraction": "lots",
                                          "opto_late_records_warn": -1,
                                          "opto_event_disagreement_warn_fraction": -0.1})
    assert len(problems) == 5
    root = tmp_path / "exp"
    root.mkdir()
    cfg = _config([1])
    cfg["global"]["constants"] = {"opto_yoking_fail_fraction": 2}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    (root / "data").mkdir()
    issues = lint_flic_config(root / "flic_config.yaml")
    assert any(i.severity == "error" and "opto_yoking_fail_fraction" in i.message
               for i in issues)


@pytest.fixture(scope="module")
def qt_app():
    pytest.importorskip("PyQt6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    ## Held for the module: a QApplication nobody references is destroyed,
    ## and every widget with it.
    return QApplication.instance() or QApplication([])


def test_the_editors_show_a_row_for_each_constant(qt_app, tmp_path):
    from pyflic.base.config_editor import FLICConfigEditor
    from pyflic.base.design_editor import ProjectDesignDialog

    exp = tmp_path / "exp"
    (exp / "data").mkdir(parents=True)
    cfg = _config([1])
    cfg["global"]["optogenetics"] = True
    (exp / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    win = FLICConfigEditor(initial_path=exp)
    try:
        for key, default in NEW_CONSTANTS.items():
            widget = win._opto_constant_widgets[key]
            assert f"{default:g}" in widget.placeholderText()
    finally:
        win.close()
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text(yaml.safe_dump({"name": "P", "design": {"global": {
        "chamber_layout": "two_well", "optogenetics": True,
        "constants": {"opto_lost_records_warn": 50}}}}), encoding="utf-8")
    dialog = ProjectDesignDialog(start_dir=str(root))
    assert dialog.opto_number_edits["opto_lost_records_warn"].text() == "50"
    for key in NEW_CONSTANTS:
        assert key in dialog.opto_number_edits
    dialog.opto_number_edits["opto_late_records_warn"].setText("40")
    built = dialog._build_design()["global"]["constants"]
    assert built["opto_late_records_warn"] == 40 and built["opto_lost_records_warn"] == 50


# ---------------------------------------------------------------------------
# Trigger wells under an OpenLoop Paradigm
# ---------------------------------------------------------------------------

def test_an_open_loop_paradigm_has_no_trigger_wells():
    from pyflic.base import opto_roles as orl

    text = ("Start Time: 10/16/2026 23:34:00\nDuration: 20 min\nBaseline: Yes\n\n"
            "Paradigms:\n"
            "Open (OpenLoop): Frequency 40 Hz, PulseWidth 8 ms\n"
            "Closed (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 500 ms, "
            "MaxOnMs 0 ms, EventGapMs 100 ms\n\n"
            "***DFM 1***\nLinkage: 1,1,2,2,3,3,4,4,5,5,6,6\nProgram Type: Linear\n"
            "(10/16/2026 23:34:00) Lit, Open, 20,Off,20,Off,Off,Off,Off,Off,Off,Off,Off,Off, "
            "10 min\n"
            "(10/16/2026 23:44:00) Lit, Closed, Off,Off,20,Off,Off,Off,Off,Off,Off,Off,Off,"
            "Off, 10 min\n")
    section = op.parse_program(text).section(1)
    ## W1 is a level only under Open: lit regardless, never a trigger.
    assert section.trigger_wells() == (3,)
    view = orl.linkage_view(section, None, None)
    assert section.trigger_wells() == tuple(sorted(view.trigger_wells))


def test_legacy_programs_keep_every_level_well_a_trigger():
    """A legacy export has no OpenLoop type, so the change leaves every
    legacy section's trigger wells, and so paired_chambers, as they were."""
    from opto_fixtures import case_program, pr_program

    programs = [op.read_program(FIXTURES / "Program.txt"), op.parse_program(case_program()),
                op.parse_program(pr_program({1: (1, 4, 5)}, pi_direction="left")),
                op.parse_program(pr_program({2: (2, 3, 6)}, pi_direction="right"))]
    for program in programs:
        assert program.grammar == op.GRAMMAR_LEGACY
        for section in program.dfms.values():
            levels = {w for iv in section.intervals for w in iv.trigger_wells()}
            assert section.trigger_wells() == tuple(sorted(levels))
