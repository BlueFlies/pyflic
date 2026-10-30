"""The Paradigm state (``pyflic/base/paradigm_state.py``) against the simulator's truth.

Every method is checked on ``tests/v4_fixtures.py`` recordings, whose
:class:`SimTruth` says what the firmware did millisecond by millisecond.  The
record holding step ``t`` has ``Index`` ``t // 200 + 1``, so with no lost
records its row is ``t // 200``.
"""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pyflic.base import paradigm_state as ps

from v4_fixtures import (
    COLUMNS,
    DATA_COLUMNS,
    FAMILY_SPEC_KEYS,
    PARADIGM_COLUMNS as SIM_PARADIGM_COLUMNS,
    PR10,
    YOKED_LINKAGE,
    choice_pr_spec,
    family_specs,
    fixed_ratio_spec,
    one_of_each_spec,
    repeating_open_loop_spec,
    simulate,
    stress_spec,
    write_gen2_recording,
    write_v4_recording,
    yoked_controls_spec,
)

RECORD_MS = 200
WELLS = range(1, 13)

#: The ready-made experiment specs, on which every method is exact.
EXPERIMENTS = {
    "choice_pr": choice_pr_spec,
    "fixed_ratio": fixed_ratio_spec,
    "one_of_each": one_of_each_spec,
    "yoked_controls": yoked_controls_spec,
    "repeating_open_loop": repeating_open_loop_spec,
}
#: The Paradigm Family specs, by ``family_<key>``; ``family_restart`` restarts.
FAMILIES = [f"family_{key}" for key in FAMILY_SPEC_KEYS]
#: The ones without a restart, where the row of step t is t // 200.
CLEAN_FAMILIES = [f for f in FAMILIES if f != "family_restart"]


@lru_cache(maxsize=None)
def _simulated(name: str):
    if name.startswith("family_"):
        spec = family_specs()[name.removeprefix("family_")]
    else:
        spec = stress_spec() if name == "stress" else EXPERIMENTS[name]()
    return spec, simulate(spec)


def state_of(rows: pd.DataFrame) -> ps.ParadigmState:
    _base, columns = ps.split_paradigm_columns(rows)
    minutes = (rows["Index"].to_numpy(dtype=float) * RECORD_MS) / 60000.0
    return ps.ParadigmState.from_frame(columns, minutes=minutes, index=rows["Index"])


def runs(name: str):
    """``(dfm id, SimResult, ParadigmState)`` for every DFM of a spec."""
    _spec, results = _simulated(name)
    return [(dfm_id, r, state_of(r.rows)) for dfm_id, r in sorted(results.items())]


def row_of(ms: int) -> int:
    return int(ms) // RECORD_MS


def main_event_rows(truth, state: ps.ParadigmState, well: int) -> np.ndarray:
    """Rows of the Firmware Events Progress counts: started while the well
    was in Phase M under a ratio Paradigm."""
    starts = np.array([row_of(a) for a, _b in truth.event_spans_ms[well]], dtype=int)
    main = state.ratio_rows(well) & ~state.phase_a[:, well - 1]
    return starts[main[starts]] if starts.size else starts


# ---------------------------------------------------------------------------
# Generation and the split
# ---------------------------------------------------------------------------

def test_the_generation_comes_from_phase1(tmp_path: Path) -> None:
    spec, results = _simulated("choice_pr")
    rows = results[1].rows
    assert ps.detect_generation(rows[list(DATA_COLUMNS)]) == ps.GENERATION_FLAG
    assert ps.detect_generation(rows) == ps.GENERATION_PARADIGM

    write_gen2_recording(tmp_path / "na", spec, results=results)
    write_gen2_recording(tmp_path / "blank", spec, results=results, blank_missing=True)
    for folder in ("na", "blank"):
        gen2 = pd.read_csv(tmp_path / folder / "DFM1_0.csv")
        assert ps.detect_generation(gen2) == ps.GENERATION_EMPTY


def test_the_generation_survives_split_files_of_different_dtypes(tmp_path: Path) -> None:
    """An all-NA file reads Phase1 as float, a filled one as text; the
    concatenation is an object column of both."""
    spec, results = _simulated("choice_pr")
    write_v4_recording(tmp_path / "v4", spec, results=results, split_hours=0.1)
    write_gen2_recording(tmp_path / "gen2", spec, results=results, split_hours=0.1)
    v4 = [pd.read_csv(p) for p in sorted((tmp_path / "v4").glob("DFM1_*.csv"))]
    gen2 = [pd.read_csv(p) for p in sorted((tmp_path / "gen2").glob("DFM1_*.csv"))]
    assert len(v4) > 2
    assert gen2[0]["Phase1"].dtype.kind == "f" and v4[0]["Phase1"].dtype.kind != "f"
    mixed = pd.concat([gen2[0], *v4[1:]], ignore_index=True)
    assert ps.detect_generation(mixed) == ps.GENERATION_PARADIGM
    assert ps.detect_generation(pd.concat(gen2, ignore_index=True)) == ps.GENERATION_EMPTY
    assert ps.detect_generation(pd.concat(v4, ignore_index=True)) == ps.GENERATION_PARADIGM


def test_split_paradigm_columns() -> None:
    rows = _simulated("choice_pr")[1][1].rows
    assert ps.PARADIGM_COLUMNS == SIM_PARADIGM_COLUMNS
    base, columns = ps.split_paradigm_columns(rows)
    assert tuple(base.columns) == DATA_COLUMNS
    assert tuple(columns.columns) == SIM_PARADIGM_COLUMNS
    assert base.index.equals(rows.index) and columns.index.equals(rows.index)
    old = rows[list(DATA_COLUMNS)]
    same, none = ps.split_paradigm_columns(old)
    assert same is old and none is None


def test_the_state_reads_any_dtype_and_blank_missing_values(tmp_path: Path) -> None:
    """Interval, Cycle and Paradigm may arrive as Int64, float or text, and
    development builds wrote blanks: the state is the same."""
    spec, results = _simulated("choice_pr")
    write_v4_recording(tmp_path / "na", spec, results=results)
    write_v4_recording(tmp_path / "blank", spec, results=results, blank_missing=True)
    typed = state_of(results[1].rows)
    for frame in (pd.read_csv(tmp_path / "na" / "DFM1_0.csv"),
                  pd.read_csv(tmp_path / "blank" / "DFM1_0.csv"),
                  pd.read_csv(tmp_path / "na" / "DFM1_0.csv", dtype=str)):
        state = state_of(frame.assign(Index=pd.to_numeric(frame["Index"])))
        assert state.program_interval.dtype == "Int64" and state.paradigm.dtype == "string"
        assert state.program_interval.equals(typed.program_interval)
        assert state.cycle.equals(typed.cycle)
        assert state.paradigm.equals(typed.paradigm)
        for name in ("phase_a", "activations", "on_ms"):
            assert np.array_equal(getattr(state, name), getattr(typed, name)), name
        for name in ("requirement", "progress"):
            assert np.array_equal(getattr(state, name), getattr(typed, name), equal_nan=True), name


def test_a_blank_interval_at_the_start_is_the_baseline(tmp_path: Path) -> None:
    """Development builds wrote the lead-in's Interval blank
    (DataFileColumns.md: treat it as 0)."""
    spec, results = _simulated("choice_pr")
    write_v4_recording(tmp_path, spec, results=results, blank_missing=True)
    frame = pd.read_csv(tmp_path / "DFM1_0.csv")
    frame["Interval"] = frame["Interval"].astype(float)
    frame.loc[:24, "Interval"] = np.nan
    state = state_of(frame)
    assert state.program_interval[:25].tolist() == [0] * 25
    assert state.lead_in_rows() == 25 and not state.unknown_rows().any()


def test_subset_keeps_the_rows_selected() -> None:
    _dfm, _r, state = runs("choice_pr")[0]
    keep = state.minutes > 10.0
    part = state.subset(keep)
    assert len(part) == int(keep.sum())
    assert np.array_equal(part.on_ms, state.on_ms[keep])
    assert part.paradigm.equals(state.paradigm[keep])


def test_a_subset_from_mid_recording_knows_what_its_first_row_changed() -> None:
    """Review C11: a range that starts mid-recording keeps the row before
    its first, so an Activation counted on its first row is its own, and two
    adjacent ranges' Activations add up to the whole's."""
    _dfm, _r, state = runs("choice_pr")[0]
    well = next(w for w in WELLS if state.activation_onsets(w).size > 2)
    onsets = state.activation_onsets(well)
    row = int(onsets[len(onsets) // 2])
    keep = state.minutes > state.minutes[row - 1]       # the range starts on the onset
    part, head = state.subset(keep), state.subset(~keep)
    assert np.array_equal(part.activations_before, state.activations[row - 1])
    assert np.array_equal(part.on_ms_before, state.on_ms[row - 1])
    assert 0 in part.activation_onsets(well).tolist()
    for w in WELLS:
        assert (head.activation_onsets(w).size + part.activation_onsets(w).size
                == state.activation_onsets(w).size), w
    ## A state that starts with the recording has no row before.
    assert state.activations_before is None and head.activations_before is None
    assert 0 not in head.activation_onsets(well).tolist()


# ---------------------------------------------------------------------------
# Program Intervals
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [*EXPERIMENTS, "stress", *CLEAN_FAMILIES])
def test_interval_runs_follow_the_schedule(name: str) -> None:
    for _dfm, r, state in runs(name):
        schedule = r.truth.schedule
        starts = [row_of(ms) for ms, *_ in schedule] + [len(state)]
        ## The lead-in names no Paradigm (PyMCU writes NA before the program).
        expected = [ps.IntervalRun(0, None, None, 0, starts[0], "baseline")]
        expected += [ps.IntervalRun(interval, cycle, paradigm, starts[k], starts[k + 1], "program")
                     for k, (_ms, interval, cycle, paradigm) in enumerate(schedule)]
        assert state.interval_runs() == expected
        assert state.lead_in_rows() == starts[0] == 25
        assert not state.unknown_rows().any()
        assert not state.late_rows().any()


def test_repeating_runs_count_cycles() -> None:
    (_dfm, _r, state), = runs("repeating_open_loop")
    program = [(run.program_interval, run.cycle) for run in state.interval_runs()[1:]]
    assert program == [(1, 1), (2, 1), (1, 2), (2, 2), (1, 3), (2, 3)]


def test_unknown_and_late_rows() -> None:
    rows = _simulated("choice_pr")[1][1].rows.copy()
    rows["Interval"] = rows["Interval"].astype("Float64")
    rows.loc[400:409, "Interval"] = pd.NA      # an instruction outside the Program
    rows.loc[400:409, "Cycle"] = pd.NA
    rows.loc[500, "OnMs7"] = 231               # a late record
    state = state_of(rows)
    assert np.flatnonzero(state.unknown_rows()).tolist() == list(range(400, 410))
    assert np.flatnonzero(state.late_rows()).tolist() == [500]
    unknown = [run for run in state.interval_runs() if run.kind == "unknown"]
    assert [(run.i0, run.i1, run.program_interval, run.cycle) for run in unknown] == \
        [(400, 410, None, None)]
    assert state.lead_in_rows() == 25


def test_index_gaps(tmp_path: Path) -> None:
    spec, results = _simulated("choice_pr")
    write_v4_recording(tmp_path, spec, results=results, index_gaps={1: [(100, 7), (2000, 1)]})
    frame = pd.read_csv(tmp_path / "DFM1_0.csv")
    state = state_of(frame)
    assert [(i, n) for i, n, _m in state.index_gaps()] == [(100, 7), (2000, 1)]
    minute = state.index_gaps()[0][2]
    assert minute == pytest.approx(100 * RECORD_MS / 60000.0)
    assert state_of(results[1].rows).index_gaps() == []


# ---------------------------------------------------------------------------
# Restarts and Paradigm-state runs (docs/paradigm-analyses-plan.md, C2)
# ---------------------------------------------------------------------------

def row_of_index(state: ps.ParadigmState, ms: int) -> int:
    """The row of the record holding step *ms*, whatever records are missing."""
    (row,) = np.flatnonzero(state.index == int(ms) // RECORD_MS + 1)
    return int(row)


def test_restarts_find_every_restart_of_the_restart_spec() -> None:
    found = 0
    for _dfm, r, state in runs("family_restart"):
        expected = []
        for down, resume, missing in r.truth.restarts_ms:
            row = down // RECORD_MS              # rows 0 .. row-1 hold Index 1 .. row
            idle = (resume - down) // RECORD_MS - missing
            expected.append(ps.RestartSpan(row=row, resume_row=row + idle, missing=missing,
                                           minute=float(state.minutes[row])))
            ## The gap, then the idle rows, then the instruction again.
            assert state.index[row] - state.index[row - 1] == missing + 1
            assert state.unknown_rows()[row:row + idle].all() and not state.unknown_rows()[row + idle]
            assert state.index[row + idle] == resume // RECORD_MS + 1
        assert state.restarts() == expected and len(expected) == 1
        assert expected[0].minute == pytest.approx((r.truth.restarts_ms[0][0] / RECORD_MS
                                                    + r.truth.restarts_ms[0][2] + 1) * RECORD_MS / 60000)
        found += len(expected)
    assert found == 2


@pytest.mark.parametrize("name", [*EXPERIMENTS, "stress", *CLEAN_FAMILIES])
def test_restarts_find_nothing_on_the_other_specs(name: str) -> None:
    for _dfm, _r, state in runs(name):
        assert state.restarts() == []


def test_a_gap_alone_or_unknown_rows_alone_are_no_restart(tmp_path: Path) -> None:
    spec, results = _simulated("choice_pr")
    ## Lost records: a gap, then the same Paradigm.
    write_v4_recording(tmp_path, spec, results=results, index_gaps={1: [(1000, 25)]})
    assert state_of(pd.read_csv(tmp_path / "DFM1_0.csv")).restarts() == []
    ## An instruction outside the program without a gap.
    rows = results[1].rows.copy()
    rows["Interval"] = rows["Interval"].astype("Float64")
    rows.loc[400:409, ["Interval", "Cycle"]] = pd.NA
    rows.loc[400:409, "Paradigm"] = pd.NA
    assert state_of(rows).restarts() == []
    ## Both, but the gap ends before the unknown rows begin.
    gapped = rows[(rows["Index"] < 300) | (rows["Index"] > 320)].reset_index(drop=True)
    assert state_of(gapped).restarts() == []
    ## A gap straight into them is one.
    gapped = rows[(rows["Index"] < 380) | (rows["Index"] > 400)].reset_index(drop=True)
    (span,) = state_of(gapped).restarts()
    assert (span.row, span.resume_row, span.missing) == (379, 389, 21)


def test_a_restart_running_to_the_end_resumes_at_the_end() -> None:
    _dfm, r, state = runs("family_restart")[0]
    (span,) = state.restarts()
    cut = state.subset(np.arange(len(state)) < span.row + 2)
    (end,) = cut.restarts()
    assert (end.row, end.resume_row, end.missing) == (span.row, len(cut), span.missing)


@pytest.mark.parametrize("name", [*EXPERIMENTS, "stress", *FAMILIES])
def test_state_runs_are_the_runs_between_paradigm_starts(name: str) -> None:
    for _dfm, r, state in runs(name):
        state_runs = state.state_runs()
        assert state_runs[0][0] == 0 and state_runs[-1][1] == len(state)
        assert all(a < b for a, b in state_runs)
        assert all(b == a2 for (_a, b), (a2, _b) in zip(state_runs, state_runs[1:]))
        starts = state._paradigm_starts()
        assert [a for a, _b in state_runs] == np.flatnonzero(starts).tolist()
        ## Without a restart: the lead-in, then a run per change of name in the schedule.
        if not r.truth.restarts_ms:
            names = [p for _ms, _k, _c, p in r.truth.schedule]
            expected = [0] + [row_of(ms) for k, (ms, _k, _c, p) in enumerate(r.truth.schedule)
                              if k == 0 or p != names[k - 1]]
            assert [a for a, _b in state_runs] == expected


def test_state_runs_split_at_a_restart() -> None:
    for _dfm, r, state in runs("family_restart"):
        (span,) = state.restarts()
        lead = state.lead_in_rows()
        assert state.state_runs() == [(0, lead), (lead, span.row), (span.row, span.resume_row),
                                      (span.resume_row, len(state))]
        ## The run after the restart starts as the firmware did: a new Paradigm's first row.
        assert state._paradigm_starts()[span.resume_row]
        assert state.paradigm[span.resume_row] == state.paradigm[span.row - 1]


def test_a_restart_changes_nothing_else() -> None:
    """Training stays the first Main row under a ratio Paradigm and the
    Acclimation end the end of the first Acclimation run, though the wells
    acclimate again after the restart; the onsets are still the truth's."""
    (_dfm, r, state), _closed = runs("family_restart")
    (span,) = state.restarts()
    for w in range(1, 13, 2):
        first, *again = state.acclimation_runs(w)
        assert [run[0] for run in again] == [span.resume_row]
        assert state.acclimation_end(w) == first[1] == row_of(r.truth.acclimation_end_ms[w])
        assert state.training_end(w) == first[1] < span.row
        onsets = [row_of_index(state, ms) for ms in r.truth.activation_onset_ms[w]]
        assert state.activation_onsets(w).tolist() == onsets
        assert [state.requirement_met(w, o) for o in state.activation_onsets(w)] == r.truth.requirement_met[w]
    ## The Activations carry on through the gap and the idle rows.
    assert (np.diff(state.activations, axis=0) >= 0).all()
    assert (state.activations[span.row:span.resume_row] == state.activations[span.row - 1]).all()


# ---------------------------------------------------------------------------
# Activations and light
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [*EXPERIMENTS, "stress", *CLEAN_FAMILIES])
def test_activation_onsets_are_the_truths(name: str) -> None:
    repeated = 0
    for _dfm, r, state in runs(name):
        for w in WELLS:
            expected = np.array([row_of(ms) for ms in r.truth.activation_onset_ms[w]], dtype=int)
            onsets = state.activation_onsets(w)
            assert np.array_equal(onsets, expected), (w, onsets[:5], expected[:5])
            repeated += int((np.bincount(onsets) > 1).sum()) if onsets.size else 0
            assert state.activations_between(w, 0, len(state)) == expected.size
            for i0, i1 in ((0, len(state) // 3), (len(state) // 3, len(state)), (50, 51)):
                assert state.activations_between(w, i0, i1) == \
                    int(((expected >= i0) & (expected < i1)).sum())
    if name == "stress":
        assert repeated > 0          # rises of 2 in one row were exercised


def test_wells_with_activations() -> None:
    for name in EXPERIMENTS:
        for _dfm, r, state in runs(name):
            expected = {w for w in WELLS if r.truth.activation_onset_ms[w]}
            assert state.wells_with_activations() == frozenset(expected)


@pytest.mark.parametrize("name", [*EXPERIMENTS, "stress", *CLEAN_FAMILIES])
def test_lit_seconds_are_the_on_ms_total(name: str) -> None:
    for _dfm, r, state in runs(name):
        n = len(state)
        for w in WELLS:
            assert round(state.lit_seconds(w, 0, n) * 1000) == r.truth.on_ms_total[w]
            half = n // 2
            assert state.lit_seconds(w, 0, half) + state.lit_seconds(w, half, n) == \
                pytest.approx(state.lit_seconds(w, 0, n))
            ## A record a well's own light touched is lit.
            lit = state.lit()[:, w - 1]
            for a, b in r.truth.lit_spans_ms[w]:
                assert lit[row_of(a):row_of(b - 1) + 1].all()


def test_identical_on_ms_groups_find_the_linkage() -> None:
    (_dfm, r, state), = runs("yoked_controls")
    lit = [w for w in WELLS if state.lit()[:, w - 1].any()]
    groups = {}
    for well, label in enumerate(YOKED_LINKAGE, start=1):
        groups.setdefault(label, []).append(well)
    assert len(lit) == 12
    assert state.identical_on_ms_groups(lit) == [tuple(g) for g in groups.values()]
    assert state.identical_on_ms_groups([3, 1, 2]) == [(1, 2), (3,)]


# ---------------------------------------------------------------------------
# Ratio Paradigms, Acclimation and Training
# ---------------------------------------------------------------------------

def test_ratio_rows_acclimation_and_training_on_the_choice_spec() -> None:
    for _dfm, r, state in runs("choice_pr"):
        pr10_row = next(row_of(ms) for ms, _k, _c, name in r.truth.schedule if name == "PR10")
        n = len(state)
        for w in WELLS:
            end_ms = r.truth.acclimation_end_ms[w]
            if w % 2 == 0:
                ## B wells are Off: Phase M, Requirement NA, no Training.
                assert not state.ratio_rows(w).any()
                assert state.acclimation_runs(w) == []
                assert state.acclimation_end(w) is None and state.training_end(w) is None
                continue
            assert np.flatnonzero(state.ratio_rows(w)).tolist() == list(range(pr10_row, n))
            end = None if end_ms is None else row_of(end_ms)
            assert state.acclimation_runs(w) == [(pr10_row, n if end is None else end)]
            assert state.acclimation_end(w) == end
            assert state.training_end(w) == end


def test_training_ends_at_the_first_ratio_row_without_acclimation() -> None:
    spec = choice_pr_spec()
    spec = replace(spec, paradigms={**spec.paradigms, "PR10": replace(PR10, acclimation=0)})
    for _dfm, r in simulate(spec).items():
        state = state_of(r.rows)
        pr10_row = next(row_of(ms) for ms, _k, _c, name in r.truth.schedule if name == "PR10")
        for w in range(1, 13, 2):
            assert state.acclimation_runs(w) == [] and state.acclimation_end(w) is None
            assert state.training_end(w) == pr10_row


def test_training_needs_a_ratio_paradigm() -> None:
    """Acclimation under FixedInterval is not Training, nor is ClosedLoop."""
    for dfm_id, _r, state in runs("one_of_each"):
        ends = {w: state.training_end(w) for w in range(1, 13, 2)}
        if dfm_id in (5, 6):
            assert all(end is not None for end in ends.values()), dfm_id
        else:
            assert all(end is None for end in ends.values()), dfm_id


@pytest.mark.parametrize("name", [*EXPERIMENTS, *CLEAN_FAMILIES])
def test_requirement_met_is_the_truths(name: str) -> None:
    for _dfm, r, state in runs(name):
        for w in WELLS:
            onsets = state.activation_onsets(w)
            assert [state.requirement_met(w, o) for o in onsets] == r.truth.requirement_met[w]
        assert state.requirement_met(1, 0) is None
        assert state.requirement_met(1, len(state)) is None


def test_requirement_met_on_the_stress_spec_misses_only_new_paradigm_rows() -> None:
    """The documented edge: an Activation in the first row of a new Paradigm
    met a Requirement no row shows."""
    checked = 0
    for _dfm, r, state in runs("stress"):
        starts = state._paradigm_starts()
        for w in WELLS:
            for onset, met in zip(state.activation_onsets(w), r.truth.requirement_met[w]):
                got = state.requirement_met(w, onset)
                checked += 1
                if got != met:
                    assert starts[onset] or starts[onset - 1], (w, onset, got, met)
    assert checked > 1000


def test_an_acclimation_activation_meets_no_requirement() -> None:
    for _dfm, r, state in runs("choice_pr"):
        for w in range(1, 13, 2):
            phases = r.truth.activation_phase[w]
            for onset, phase in zip(state.activation_onsets(w), phases):
                if phase == "A":
                    shown = state.requirement[onset - 1, w - 1]
                    assert np.isnan(shown) or shown == 1    # the row shows the first Main one
                    assert state.requirement_met(w, onset) is None


@pytest.mark.parametrize("name", [*EXPERIMENTS, *CLEAN_FAMILIES])
def test_firmware_events_between_are_the_truths(name: str) -> None:
    rng = np.random.default_rng(3)
    for _dfm, r, state in runs(name):
        n = len(state)
        windows = [(0, n), (0, n // 2), (n // 2, n)] + \
            [tuple(sorted(rng.integers(0, n + 1, size=2))) for _ in range(20)]
        for w in WELLS:
            rows = main_event_rows(r.truth, state, w)
            for i0, i1 in windows:
                expected = int(((rows >= i0) & (rows < i1)).sum())
                assert state.firmware_events_between(w, i0, i1) == expected, (w, i0, i1)
            ## A rise in Progress is a row where a Main Event started.
            rises = state.firmware_event_rises(w)
            assert set(rises.tolist()) <= set(rows.tolist())


def test_firmware_events_count_the_requirements_met() -> None:
    """Under PR10 every Main Activation met its Requirement exactly: the
    Events up to the last onset are the Requirements' sum."""
    for _dfm, r, state in runs("choice_pr"):
        for w in range(1, 13, 2):
            onsets = state.activation_onsets(w)
            met = [m for m in (state.requirement_met(w, o) for o in onsets) if m is not None]
            if not met:
                continue
            last = int(onsets[-1])
            assert state.firmware_events_between(w, 0, last + 1) == \
                sum(met) + int(state.progress[last, w - 1])
            assert met == [min(1 + 10 * k, 200) for k in range(len(met))]


def test_the_column_tuple_is_pymcus() -> None:
    assert ps.PARADIGM_COLUMNS == COLUMNS[len(DATA_COLUMNS):]
    assert len(ps.PARADIGM_COLUMNS) == 63
