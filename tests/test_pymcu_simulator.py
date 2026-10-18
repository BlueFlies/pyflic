"""pyflic against PyMCU's own simulator (C8 of ``docs/paradigm-analyses-plan.md``).

PyMCU's ``scripts/simulate_recording.py`` simulates flies lick by lick and
passes the firmware 4.0.0 records through PyMCU's real record parser, DFM
bookkeeping and data-file writer, so its recording is what an MCU writes,
made independently of pyflic's own simulator (``v4_fixtures``).  The design:
two DFMs of six two-well chambers with Linkage 1,1,2,2,...; each chamber's A
well is the Trigger Well under PR5 (ProgressiveRatio, Arithmetic, Step 5,
ActivationMs 500, Acclimation 10) and lights both of the chamber's LEDs; the
B wells are Off.  Beside the recording, a ``_truth`` folder says what every
well did.

``tests/pymcu_sim_runner.py`` runs the simulator with stand-ins for the
Pi's hardware modules.  The recording is analysed once, as a Custom
optogenetic two-well Project, and the light table, the light QC and the
``Messages.csv`` reader are checked against the truth.

Skipped unless the PyMCU checkout (``PYMCU_DIR``, default the sibling
checkout) has the simulator.  Slow: it runs the simulator (about 7 s) and a
basic analysis with QC.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import light_summary as ls
from pyflic.base import messages
from pyflic.base import opto_light
from pyflic.base.paradigm_state import GENERATION_PARADIGM, RECORD_MS
from pyflic.base.pr_light_qc import VERDICT_OK
from pyflic.base.project import Project

import pymcu_sim_runner

pytestmark = pytest.mark.slow

HERE = Path(__file__).resolve().parent
RUNNER = HERE / "pymcu_sim_runner.py"
PYMCU_DIR = Path(os.environ.get("PYMCU_DIR", "C:/Users/scott/Desktop/GithubLocal/PyMCU"))
SIMULATOR = PYMCU_DIR / "scripts" / "simulate_recording.py"
#: The seed is pinned, so a PyMCU change that alters the truth shows as a
#: failure to look at, not a flake.
SEED = 1

#: The simulator's design (its module constants).
DFM_IDS = (1, 2)
TRIGGER_WELLS = (1, 3, 5, 7, 9, 11)          # the A wells; the B wells are Off
LINKAGE_GROUPS_PER_DFM = 6

#: Detection as the simulator's flies need it: a 5 Hz record, the firmware's
#: threshold of 20 above the baseline.
PARAMS = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
          "tasting_maximum": 20, "samples_per_second": 5, "feeding_event_link_gap": 5,
          "baseline_window_minutes": 3, "pi_direction": "left"}
FACTORS = {"Line": [f"Line{d}" for d in DFM_IDS]}
#: The Design the recording is analysed under here.  S4 adds a Progressive
#: Ratio one beside it.
CUSTOM_DESIGN = {"chamber_layout": "two_well", "optogenetics": True, "transform_licks": False}

#: The C8 tolerances, in seconds, for the times the truth gives to the ms.
ACCLIMATION_END_TOLERANCE_S = 0.2
LIT_TOLERANCE_S = 0.01


@dataclass(frozen=True)
class Simulated:
    """One simulator run: the recording folder (``DFM1_0.csv``,
    ``DFM2_0.csv``, ``Messages.csv``, ``Program.txt``), its ``_truth``
    folder (``Summary.csv``, ``Activations.csv``, ``Bouts.csv``,
    ``Flies.csv``), and any of PyMCU's files the run changed."""

    recording: Path
    truth: Path
    pymcu_changes: tuple[str, ...]


@dataclass(frozen=True)
class Analysed:
    """The recording after basic analysis with QC, under ``CUSTOM_DESIGN``."""

    experiment: object
    light_wells: pd.DataFrame   # analysis/light_wells.csv: the whole recording, one row per well
    opto_qc: pd.DataFrame       # qc/opto/opto_light_qc.csv: one row per Linkage Group
    truth: pd.DataFrame         # the truth's Summary.csv: one row per Trigger Well


def _pymcu_files() -> dict[str, tuple[int, int]]:
    """Every file of the PyMCU checkout but its git and venv folders, with
    its size and modification time."""
    files = {}
    for base, dirs, names in os.walk(PYMCU_DIR):
        dirs[:] = [d for d in dirs if d not in (".git", ".venv")]
        for name in names:
            path = Path(base) / name
            try:
                stat = path.stat()
            except OSError:      # gone between the listing and the look
                continue
            files[path.relative_to(PYMCU_DIR).as_posix()] = (stat.st_size, stat.st_mtime_ns)
    return files


def truth_origin_minutes(exp, dfm_id: int) -> float:
    """pyflic's ``Minutes`` at the truth's time 0, on DFM *dfm_id*.

    The truth counts ms from the start of record 1 (``Index`` 1).  pyflic's
    ``Minutes`` count from the whole second of the first row's time stamp,
    and PyMCU stamps a row at its record's end, so the two differ by the
    stamp's milliseconds less one record (572 ms here, as the simulator
    starts the clock 572 ms after the Program's Start Time).  A truth time
    in ms is ``truth_origin_minutes + ms / 60000`` in pyflic's minutes."""
    raw = exp.dfms[dfm_id].raw_df
    first = raw.loc[pd.to_numeric(raw["Index"], errors="coerce") == 1, "Minutes"]
    assert len(first) == 1, f"DFM {dfm_id} has {len(first)} rows with Index 1"
    return float(first.iloc[0]) - RECORD_MS / 60000.0


def build_project(root: Path, recording: Path, design: dict) -> Project:
    """A one-Member Project at *root* over a copy of *recording*, under
    *design* (the Design's ``global:``, to which ``PARAMS`` and the ``Line``
    factor are added).  Every chamber is assigned, ``Line<dfm id>``."""
    member = root / recording.name
    shutil.copytree(recording, member / "data")
    config = {"dfms": [{"id": d, "chambers": {c: f"Line{d}" for c in range(1, 7)}}
                       for d in DFM_IDS]}
    (member / "flic_config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": root.name,
         "design": {"global": {**design, "params": PARAMS, "experimental_design_factors": FACTORS}}},
        sort_keys=False))
    return Project(root)


@pytest.fixture(scope="module")
def simulated(tmp_path_factory: pytest.TempPathFactory) -> Simulated:
    if not SIMULATOR.is_file():
        pytest.skip(f"PyMCU's simulator not found at {SIMULATOR} (set PYMCU_DIR)")
    out = tmp_path_factory.mktemp("pymcu_sim")
    before = _pymcu_files()
    done = subprocess.run(
        [sys.executable, "-I", str(RUNNER), str(PYMCU_DIR), "--out", str(out), "--seed", str(SEED)],
        capture_output=True, text=True, errors="replace", timeout=600)
    after = _pymcu_files()
    assert done.returncode == 0, (f"PyMCU's simulator failed (exit {done.returncode}):\n{done.stderr}"
                                  f"\n--- its output ---\n{done.stdout[-2000:]}")
    truths = sorted(out.glob("SIMMCU_*_truth"))
    assert len(truths) == 1, f"expected one _truth folder in {out}, found {[t.name for t in truths]}"
    recording = truths[0].with_name(truths[0].name[:-len("_truth")])
    changes = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    return Simulated(recording, truths[0], tuple(changes))


@pytest.fixture(scope="module")
def analysed(simulated: Simulated, tmp_path_factory: pytest.TempPathFactory) -> Analysed:
    root = tmp_path_factory.mktemp("custom") / "pymcu_sim"
    project = build_project(root, simulated.recording, CUSTOM_DESIGN)
    exp = project.load_member(simulated.recording.name, parallel=False, use_disk_cache=False)
    exp.execute_basic_analysis(skip_qc=False)
    directory = Path(exp.experiment_dir)
    return Analysed(
        experiment=exp,
        light_wells=pd.read_csv(directory / "analysis" / ls.FILES["light_wells"]),
        opto_qc=pd.read_csv(directory / "qc" / opto_light.QC_SUBDIR / opto_light.QC_FILES["opto_light_qc"]),
        truth=pd.read_csv(simulated.truth / "Summary.csv"))


# ---------------------------------------------------------------------------
# The simulator run
# ---------------------------------------------------------------------------

def test_the_simulator_writes_a_recording_and_its_truth(simulated: Simulated) -> None:
    for name in ("DFM1_0.csv", "DFM2_0.csv", "Messages.csv", "Program.txt"):
        assert (simulated.recording / name).is_file(), name
    for name in ("Summary.csv", "Activations.csv", "Bouts.csv", "Flies.csv"):
        assert (simulated.truth / name).is_file(), name


def test_the_runner_leaves_pymcu_untouched(simulated: Simulated) -> None:
    assert not simulated.pymcu_changes, f"the run changed PyMCU's files: {list(simulated.pymcu_changes)}"


def test_the_runner_refuses_an_output_folder_inside_pymcu(tmp_path: Path) -> None:
    pymcu = str(tmp_path / "PyMCU")
    with pytest.raises(SystemExit):
        pymcu_sim_runner.simulator_args(["--out", str(tmp_path / "PyMCU" / "out")], pymcu)
    with pytest.raises(SystemExit):
        pymcu_sim_runner.simulator_args([f"--out={tmp_path / 'PyMCU'}"], pymcu)
    beside = str(tmp_path / "out")
    assert pymcu_sim_runner.simulator_args(["--out", beside, "--seed", "1"], pymcu) == [
        "--out", beside, "--seed", "1"]


def test_messages_csv_reads(simulated: Simulated) -> None:
    frame = messages.read(simulated.recording)
    assert list(frame.columns) == list(messages.MESSAGE_COLUMNS)
    assert not frame.empty
    assert frame["Time"].notna().all()
    texts = list(frame["Message"])
    assert "Recording started" in texts and "Recording ended" in texts
    assert messages.count(frame) >= len(frame)


# ---------------------------------------------------------------------------
# The light table and the light QC, under a Custom design
# ---------------------------------------------------------------------------

def test_the_recording_loads_as_generation_3(analysed: Analysed) -> None:
    exp = analysed.experiment
    assert sorted(exp.dfms) == list(DFM_IDS)
    assert {exp.dfms[d].generation for d in DFM_IDS} == {GENERATION_PARADIGM}
    assert exp.is_optogenetic


def test_the_light_table_matches_the_truth_on_every_trigger_well(analysed: Analysed) -> None:
    truth = analysed.truth
    # The simulator's design, so a change to it is seen here first.
    assert sorted(zip(truth["DFM"], truth["Well"])) == [(d, w) for d in DFM_IDS for w in TRIGGER_WELLS]
    assert truth["AcclimationEndMs"].notna().any(), "no well finished Acclimation: the time check is empty"
    wells = analysed.light_wells
    assert not wells.duplicated(["DFM", "Well"]).any(), "light_wells.csv has more than one row per well"
    m = truth.merge(wells, on=["DFM", "Well"], how="left", suffixes=("_truth", ""), validate="one_to_one")

    def number(column: str) -> np.ndarray:
        return pd.to_numeric(m[column], errors="coerce").to_numpy(dtype=float)

    # The truth's ms on pyflic's time base (truth_origin_minutes).
    # AcclimationEndMin is the stamp of the well's first Main row, the end of
    # the record in which its last Acclimation Activation ended, so it trails
    # the truth by less than one record: 0.005 to 0.175 s on seed 1.  LitSec
    # sums OnMs, which is exact.
    origin = m["DFM"].map({d: truth_origin_minutes(analysed.experiment, d) for d in DFM_IDS})
    acclimation_end_min = origin.to_numpy(dtype=float) + number("AcclimationEndMs") / 60000.0
    # (pyflic's column, the truth's in pyflic's unit, the tolerance in pyflic's unit)
    checks = [
        ("Activations", number("Activations_truth"), 0.0),
        ("AcclimationActivations", number("AcclimationActivations_truth"), 0.0),
        ("LastRequirementMet", number("Breakpoint"), 0.0),
        ("ProgressAtEnd", number("ProgressAtEnd_truth"), 0.0),
        ("AcclimationEndMin", acclimation_end_min, ACCLIMATION_END_TOLERANCE_S / 60.0),
        ("LitSec", number("LitMs") / 1000.0, LIT_TOLERANCE_S),
    ]
    misses = []
    for column, expected, tolerance in checks:
        ours = number(column)
        both_missing = np.isnan(ours) & np.isnan(expected)
        close = np.abs(ours - expected) <= tolerance + 1e-9
        for i in np.flatnonzero(~(both_missing | close)):
            misses.append(f"DFM {m['DFM'][i]} well {m['Well'][i]} {column}: pyflic {ours[i]}, truth {expected[i]}")
    assert not misses, "light_wells.csv differs from the truth:\n" + "\n".join(misses)


def test_no_well_but_the_trigger_wells_has_activations(analysed: Analysed) -> None:
    wells = analysed.light_wells
    assert len(wells) == 12 * len(DFM_IDS), "light_wells.csv should have every well of both DFMs"
    triggering = set(zip(analysed.truth["DFM"], analysed.truth["Well"]))
    others = wells[[key not in triggering for key in zip(wells["DFM"], wells["Well"])]]
    counted = others[pd.to_numeric(others["Activations"], errors="coerce").fillna(0) != 0]
    assert counted.empty, f"wells off the truth's list have Activations:\n{counted[['DFM', 'Well', 'Activations']]}"


def test_every_opto_qc_verdict_is_ok(analysed: Analysed) -> None:
    qc = analysed.opto_qc
    assert len(qc) == LINKAGE_GROUPS_PER_DFM * len(DFM_IDS)
    bad = qc[qc["Verdict"] != VERDICT_OK]
    assert bad.empty, f"opto QC verdicts not ok:\n{bad[['DFM', 'Group', 'Verdict', 'Flags']].to_string()}"


# ---------------------------------------------------------------------------
# P0-ledger (C3): the ledger against the truth's Activations.csv
# ---------------------------------------------------------------------------
# ``activation_ledger.ledger`` of each DFM's Paradigm state, from
# ``analysed.experiment``, against the truth's Activations.csv, by well and
# Activation number.

#: Activations the ledger times exactly on seed 1 (unoverlapped, ``Timing``
#: exact), of the truth's 191: the other one began in the record after the
#: one where its Well's previous light went out, which the ledger cannot
#: tell from light already on (``Overlap``).  A PyMCU change shows here.
LEDGER_EXACT_ACTIVATIONS = 190
TRUTH_ACTIVATIONS = 191


def test_the_ledger_is_the_truths_activations(simulated: Simulated, analysed: Analysed) -> None:
    from pyflic.base import activation_ledger as al

    truth = pd.read_csv(simulated.truth / "Activations.csv")
    exp = analysed.experiment
    exact = 0
    misses = []
    for dfm_id in DFM_IDS:
        state = exp.dfms[dfm_id].paradigm
        groups = exp.opto.program.section(dfm_id).linkage_groups()
        book = al.ledger(state, linked={w: g for g in groups.values() for w in g})
        assert set(book["Well"]) <= set(TRIGGER_WELLS)
        for well in TRIGGER_WELLS:
            mine = book[book["Well"] == well].reset_index(drop=True)
            theirs = truth[(truth["DFM"] == dfm_id) & (truth["Well"] == well)] \
                .sort_values("StartMs", kind="stable").reset_index(drop=True)
            assert len(mine) == len(theirs), (dfm_id, well)
            ## Activation by Activation: its Kind and Number, and the Requirement met.
            assert mine["Phase"].tolist() == ["A" if k == "Acclimation" else "M"
                                              for k in theirs["Kind"]], (dfm_id, well)
            main = theirs["Kind"] == "Main"
            assert mine.loc[main, "K"].tolist() == theirs.loc[main, "Number"].tolist()
            met = mine["RequirementMet"].notna()
            assert mine.loc[met, "RequirementMet"].tolist() == \
                theirs.loc[met, "RequirementMet"].astype(int).tolist()
            for ours, row in zip(mine.itertuples(), theirs.itertuples()):
                if ours.Overlap or ours.Timing != al.TIMING_EXACT:
                    continue
                exact += 1
                if (ours.OnsetMs, ours.LitMs) != (row.StartMs, row.LitMs):
                    misses.append(f"DFM {dfm_id} W{well} {row.Kind} {row.Number}: ledger "
                                  f"{ours.OnsetMs} for {ours.LitMs} ms, truth {row.StartMs} "
                                  f"for {row.LitMs} ms")
    assert not misses, "the ledger differs from Activations.csv:\n" + "\n".join(misses)
    assert (exact, len(truth)) == (LEDGER_EXACT_ACTIVATIONS, TRUTH_ACTIVATIONS)


# ---------------------------------------------------------------------------
# S4: the same recording as Progressive Ratio
# ---------------------------------------------------------------------------
# ``build_project`` over ``simulated.recording`` with a ProgressiveRatio Design
# and no ``paired_chambers`` loads (decision 13), and every breaking point and
# ``BreakRequirement`` matches the truth.

#: The Design S4 analyses the recording under: no ``paired_chambers``, so the
#: Chamber Groups come from Program.txt's Linkage, one chamber each.
PR_DESIGN = {"experiment_type": "ProgressiveRatio", "optogenetics": True, "transform_licks": False,
             "well_names": {"A": "Sucrose", "B": "Yeast"}}


def test_the_recording_loads_as_progressive_ratio_in_twelve_solo_groups(
        simulated: Simulated, tmp_path_factory: pytest.TempPathFactory) -> None:
    from pyflic.base.pdf_report import build_experiment_report
    from pyflic.base.progressive_ratio_experiment import (
        NO_YOKED_CONTROLS,
        ProgressiveRatioExperiment,
    )

    root = tmp_path_factory.mktemp("progressive") / "pymcu_sim"
    project = build_project(root, simulated.recording, PR_DESIGN)
    exp = project.load_member(simulated.recording.name, parallel=False, use_disk_cache=False)
    assert isinstance(exp, ProgressiveRatioExperiment)
    ## Twelve solo groups: every chamber its own group, Paired, with no Yoked.
    groups = {d: [(g.number, g.paired, g.yoked) for g in gs]
              for d, gs in exp.chamber_groups_by_dfm().items()}
    assert groups == {d: [(c, c, None) for c in range(1, 7)] for d in DFM_IDS}
    assert exp.training_table()["YokedChamber"].isna().all()
    assert exp.paired_yoked_diff().empty

    truth = pd.read_csv(simulated.truth / "Activations.csv")
    summary = pd.read_csv(simulated.truth / "Summary.csv").set_index(["DFM", "Well"])
    breaking = exp.breaking_point_summary().set_index(["DFM", "Group"])
    ledger = exp.light_events_ledger()
    nonfeeders = []
    for dfm_id in DFM_IDS:
        origin = truth_origin_minutes(exp, dfm_id)
        for group in exp.chamber_groups(dfm_id):
            gt = exp.group_training(dfm_id, group.number)
            assert gt.sucrose_well == 2 * group.paired - 1          # the chamber's A well
            fly = summary.loc[(dfm_id, gt.sucrose_well)]
            events = exp.light_events_table(dfm_id, group.number)
            test = events[events["Facet"] == "Test"]
            main = truth[(truth["DFM"] == dfm_id) & (truth["Well"] == gt.sucrose_well)
                         & (truth["Kind"] == "Main")].sort_values("StartMs", kind="stable")
            ## Count, onset and Requirement met.  The onset is the stamp of the
            ## record the Activation started in, on pyflic's time base.
            assert len(test) == len(main), (dfm_id, group.number)
            onset = origin + (np.floor(main["StartMs"].to_numpy() / RECORD_MS) + 1) * RECORD_MS / 60000.0
            np.testing.assert_allclose(test["RecordingMinute"].to_numpy(dtype=float), onset,
                                       rtol=0, atol=1e-6)
            assert [int(v) for v in test["Requirement"]] == [int(v) for v in main["RequirementMet"]]
            if fly["Kind"] == "nonfeeder":
                ## Never out of Acclimation: no Test phase, no breaking point.
                assert gt.training_complete is False
                assert (dfm_id, group.number) not in breaking.index
                nonfeeders.append((dfm_id, group.number))
                continue
            row = breaking.loc[(dfm_id, group.number)]
            counted = ledger[(ledger["DFM"] == dfm_id) & (ledger["Group"] == group.number)
                             & ledger["Counted"]]
            assert row["BreakRequirement"] == int(counted["Requirement"].iloc[-1])
            if row["Censored"]:
                assert row["BreakRequirement"] == int(fly["Breakpoint"])
    assert nonfeeders == [(1, 5), (2, 4)]
    assert breaking["Censored"].all()                         # 2 h of Test, gap 120 min

    ## The report builds with no red box, says once that there are no yoked
    ## controls, and names the two flies that never finished training.
    doc = build_experiment_report(exp, metrics=("Licks", "Events", "MedDuration"))
    texts = " ".join(t.get_text() for fig in doc._render_pages() for t in fig.texts)
    assert "could not be drawn" not in texts
    assert texts.count(NO_YOKED_CONTROLS.capitalize()) == 1
    assert "Training never completed in DFM 1 group 5; DFM 2 group 4; the chamber of each " \
           "was excluded." in texts
