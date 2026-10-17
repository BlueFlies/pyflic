"""Roles (``pyflic/base/opto_roles.py``): what each chamber was to the light.

From the Opto Program, from a generation-3 recording's own state, and (on
generation 1 without a program) not at all; and the Progressive Ratio
type's ``paired_from_program``, now read from the Roles, against the
implementation it replaced.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import yaml

from pyflic.base import opto_program as op
from pyflic.base import opto_roles as roles
from pyflic.base.experiment_types.progressive_ratio import CHAMBER_GROUPS, paired_from_program
from pyflic.base.paradigm_state import ParadigmState, split_paradigm_columns
from pyflic.base.yaml_config import load_experiment_yaml

from opto_fixtures import make_opto_dir, pr_program
from pr_fixtures import make_pr_experiment_dir
from v4_fixtures import (
    OFF,
    ON,
    IntervalSpec,
    one_of_each_spec,
    program_text,
    simulate,
    write_v4_recording,
    yoked_controls_spec,
)

FIXTURE = Path(__file__).parent / "fixtures" / "Program.txt"
CLOSED = op.Paradigm("Closed", op.CLOSED_LOOP, 40, 8, hold_ms=500, max_on_ms=0, event_gap_ms=100)
OPEN = op.Paradigm("Open", op.OPEN_LOOP, 40, 8)
TWO_WELL = roles.chamber_map()
P, Y, M, S, O, U = (roles.ROLE_PAIRED, roles.ROLE_YOKED, roles.ROLE_MUTUAL, roles.ROLE_SELF,
                    roles.ROLE_OPEN, roles.ROLE_UNLIT)


def section(linkage, *intervals) -> op.DFMProgram:
    """A DFM section of (thresholds, paradigm) intervals."""
    return op.DFMProgram(1, tuple(linkage), "Linear", tuple(
        op.ProgramInterval(k, None, False, tuple(thresholds), paradigm, 10.0)
        for k, (thresholds, paradigm) in enumerate(intervals, start=1)))


def state_of(rows) -> ParadigmState:
    _base, columns = split_paradigm_columns(rows)
    return ParadigmState.from_frame(columns, minutes=rows["Index"].to_numpy() * 0.2 / 60,
                                    index=rows["Index"])


def from_program(spec, dfm_id: int) -> dict[int, str]:
    view = roles.linkage_view(op.parse_program(program_text(spec)).section(dfm_id), None, None)
    assert view.source == roles.SOURCE_PROGRAM
    return roles.chamber_roles(view, TWO_WELL)


def from_data(results, dfm_id: int) -> dict[int, str]:
    view = roles.linkage_view(None, state_of(results[dfm_id].rows), None)
    assert view.source == roles.SOURCE_DATA
    return roles.chamber_roles(view, TWO_WELL)


# ---------------------------------------------------------------------------
# The acceptance cases
# ---------------------------------------------------------------------------

def test_yoked_controls_are_paired_and_yoked_with_and_without_the_program() -> None:
    spec = yoked_controls_spec()
    expected = {1: P, 2: P, 3: P, 4: Y, 5: Y, 6: Y}
    assert from_program(spec, 1) == expected
    assert from_data(simulate(spec), 1) == expected


def test_the_yoked_view_from_the_data() -> None:
    spec = yoked_controls_spec()
    view = roles.linkage_view(None, state_of(simulate(spec)[1].rows), None)
    assert view.trigger_wells == frozenset({1, 3, 5})
    assert sorted(view.groups.values()) == [(1, 2, 7, 8), (3, 4, 9, 10), (5, 6, 11, 12)]
    assert view.open_wells == frozenset()


def test_one_of_each_gives_open_for_the_open_loop_dfm() -> None:
    spec = one_of_each_spec()
    results = simulate(spec)
    everyone = range(1, 7)
    for source in (lambda d: from_program(spec, d), lambda d: from_data(results, d)):
        assert source(1) == {c: O for c in everyone}
        ## Every other DFM triggers at each chamber's A well, linked only to
        ## its own B well (CHOICE_LINKAGE): Self.
        for dfm_id in (2, 3, 4, 5, 6):
            assert source(dfm_id) == {c: S for c in everyone}, dfm_id


def test_linked_trigger_chambers_are_mutual_and_an_unlinked_one_is_self() -> None:
    linkage = (1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5)
    thresholds = (20, OFF) * 6
    got = roles.chamber_roles(roles.linkage_view(section(linkage, (thresholds, CLOSED)), None, None),
                              TWO_WELL)
    assert got == {1: M, 2: M, 3: S, 4: S, 5: S, 6: S}

    ## The same design from a generation-3 recording's own state.
    spec = yoked_controls_spec(minutes=15.0)
    dfm = spec.dfms[0]
    dfm = replace(dfm, linkage=linkage,
                  intervals=(IntervalSpec("Closed", True, thresholds, spec.duration_min),))
    results = simulate(replace(spec, dfms=(dfm,)))
    assert from_data(results, 1) == {1: M, 2: M, 3: S, 4: S, 5: S, 6: S}


def test_generation_1_without_a_program_is_unknown(tmp_path: Path) -> None:
    e = load_experiment_yaml(make_opto_dir(tmp_path / "opto", program=None),
                             parallel=False, use_disk_cache=False)
    dfm = e.dfms[1]
    view = roles.dfm_linkage_view(dfm, None)
    assert view.source == roles.SOURCE_NONE and view.groups
    assert set(view.trigger_wells) == {w for g in view.groups.values() for w in g}
    assert roles.chamber_roles(view, roles.dfm_chamber_map(dfm)) == \
        {c: roles.ROLE_UNKNOWN for c in range(1, 13)}
    ## With the program the same recording has Roles.
    e = load_experiment_yaml(make_opto_dir(tmp_path / "with"), parallel=False, use_disk_cache=False)
    view = roles.dfm_linkage_view(e.dfms[1], e.opto_program.section(1))
    got = roles.chamber_roles(view, roles.dfm_chamber_map(e.dfms[1]))
    ## opto_fixtures.WELL_CASES: 1-3 and 7 trigger, 5-6 On, the rest Off;
    ## every well its own Linkage Group.
    assert got == {1: S, 2: S, 3: S, 4: U, 5: O, 6: O, 7: S, 8: U, 9: U, 10: U, 11: U, 12: U}


def test_a_loaded_generation_3_dfm_reads_its_roles_from_the_data(tmp_path: Path) -> None:
    spec = yoked_controls_spec(minutes=10.0)
    write_v4_recording(tmp_path / "data", spec, program=False)
    cfg = {"global": {"chamber_layout": "two_well", "transform_licks": False,
                      "params": {"feeding_threshold": 20, "feeding_minimum": 10,
                                 "tasting_minimum": 5, "tasting_maximum": 20,
                                 "samples_per_second": 5, "pi_direction": "left"}},
           "dfms": [{"id": 1, "chambers": {c: "Ctrl" for c in range(1, 7)}}]}
    (tmp_path / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    e = load_experiment_yaml(tmp_path, parallel=False, use_disk_cache=False)
    dfm = e.dfms[1]
    view = roles.dfm_linkage_view(dfm, None)
    assert view.source == roles.SOURCE_DATA
    assert roles.chamber_roles(view, roles.dfm_chamber_map(dfm)) == \
        {1: P, 2: P, 3: P, 4: Y, 5: Y, 6: Y}


# ---------------------------------------------------------------------------
# The rules
# ---------------------------------------------------------------------------

def test_a_well_that_triggers_in_one_interval_and_is_on_in_another_is_a_trigger() -> None:
    linkage = (1, 1, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5)
    first = (20, OFF, OFF, OFF) + (OFF,) * 8
    second = (ON, OFF, OFF, OFF) + (OFF,) * 8
    view = roles.linkage_view(section(linkage, (first, CLOSED), (second, CLOSED)), None, None)
    assert view.trigger_wells == frozenset({1}) and view.open_wells == frozenset()
    assert roles.chamber_roles(view, TWO_WELL) == {1: P, 2: Y, 3: U, 4: U, 5: U, 6: U}


def test_open_loop_and_unlit_chambers() -> None:
    linkage = tuple(range(1, 13))
    thresholds = (ON, ON, ON, OFF, OFF, OFF, 20, OFF, OFF, OFF, OFF, OFF)
    got = roles.chamber_roles(roles.linkage_view(section(linkage, (thresholds, CLOSED)), None, None),
                              TWO_WELL)
    ## Chamber 2 has one On well in its own group: lit open loop.
    assert got == {1: O, 2: O, 3: U, 4: S, 5: U, 6: U}
    ## Under an OpenLoop Paradigm a level well is lit regardless: open, not a trigger.
    view = roles.linkage_view(section(linkage, (thresholds, OPEN)), None, None)
    assert 7 in view.open_wells and not view.trigger_wells
    assert roles.chamber_roles(view, TWO_WELL)[4] == O


def test_single_well_chambers_are_the_wells() -> None:
    assert roles.chamber_map(chamber_size=1) == {w: w for w in range(1, 13)}
    linkage = (1, 1) + tuple(range(2, 12))
    thresholds = (20,) + (OFF,) * 11
    got = roles.chamber_roles(roles.linkage_view(section(linkage, (thresholds, CLOSED)), None, None),
                              roles.chamber_map(chamber_size=1))
    assert got[1] == P and got[2] == Y and set(list(got.values())[2:]) == {U}


def test_without_any_source_every_role_is_unknown() -> None:
    view = roles.linkage_view(None, None, None)
    assert view == roles.LinkageView({}, frozenset(), frozenset(), roles.SOURCE_NONE)
    assert roles.chamber_roles(view, TWO_WELL) == {c: roles.ROLE_UNKNOWN for c in range(1, 7)}


def test_the_chamber_map_follows_the_chamber_sets(tmp_path: Path) -> None:
    e = load_experiment_yaml(make_pr_experiment_dir(tmp_path), parallel=False, use_disk_cache=False)
    dfm = e.dfms[1]
    sets = np.asarray(dfm.params.chamber_sets).tolist()
    assert roles.dfm_chamber_map(dfm) == {int(w): i + 1 for i, row in enumerate(sets) for w in row}
    assert roles.chamber_map([(2, 1), (4, 3)]) == {2: 1, 1: 1, 4: 2, 3: 2}


# ---------------------------------------------------------------------------
# Progressive Ratio: paired_from_program on the Roles
# ---------------------------------------------------------------------------

def _paired_before_roles(dfm_program, chamber_sets=None, pi_direction: str = "left"):
    """``paired_from_program`` as it was before it read the Roles."""
    sets = [tuple(int(w) for w in row) for row in (
        chamber_sets if chamber_sets is not None else tuple((2 * c - 1, 2 * c) for c in range(1, 7)))]
    chamber_of = {w: i + 1 for i, row in enumerate(sets) for w in row}
    triggers = set(dfm_program.trigger_wells())
    paired, problems, notes = [], [], []
    for g, (a, b) in CHAMBER_GROUPS.items():
        hit = sorted({chamber_of[w] for w in triggers if chamber_of.get(w) in (a, b)})
        if len(hit) == 1:
            paired.append(hit[0])
        elif not hit:
            problems.append(f"Program.txt has no trigger well in chamber group {g} "
                            f"(chambers {a}-{b})")
        else:
            own = sorted(w for w in triggers if chamber_of.get(w) in (a, b))
            problems.append(f"Program.txt has trigger wells in both chambers of group {g} "
                            f"({op.wells_label(own)})")
    if problems:
        return None, problems, notes
    for chamber in paired:
        if chamber > len(sets):
            continue
        left, right = sets[chamber - 1]
        well_a = left if str(pi_direction).lower() == "left" else right
        own = sorted(w for w in triggers if chamber_of.get(w) == chamber)
        if well_a not in own:
            notes.append(f"the trigger well of paired chamber {chamber} is "
                         f"{op.wells_label(own)}, which is well B under pi_direction "
                         f"{pi_direction}; the Sucrose Well is well A")
    return paired, problems, notes


def _cases():
    """Every DFM section the tests know, then random ones."""
    sample = op.read_program(FIXTURE)
    for dfm_id in sorted(sample.dfms):
        yield sample.section(dfm_id)
    for paired, pi in (({1: (1, 4, 5)}, "left"), ({1: (2, 3, 6)}, "right"), ({1: (1, 3, 5)}, "left")):
        yield op.parse_program(pr_program(paired, pi_direction=pi)).section(1)
    rng = np.random.default_rng(11)
    kinds = [CLOSED, replace(CLOSED, name="FI", type=op.FIXED_INTERVAL),
             replace(CLOSED, name="PR", type=op.PROGRESSIVE_RATIO)]
    for _ in range(300):
        linkage = tuple(int(v) for v in rng.integers(1, 7, size=12))
        intervals = []
        for _k in range(int(rng.integers(1, 4))):
            thresholds = tuple(rng.choice([20, 20, ON, OFF, OFF, OFF]).item() for _w in range(12))
            thresholds = tuple(int(t) if str(t).lstrip("-").isdigit() else t for t in thresholds)
            intervals.append((thresholds, kinds[int(rng.integers(len(kinds)))]))
        yield section(linkage, *intervals)
    ## Designs that can be derived: one trigger well in one chamber of each
    ## Chamber Group, on either side, under any linkage.
    for _ in range(300):
        linkage = tuple(int(v) for v in rng.integers(1, 7, size=12))
        thresholds: list = [rng.choice([ON, OFF, OFF]).item() for _w in range(12)]
        for a, b in CHAMBER_GROUPS.values():
            chamber = (a, b)[int(rng.integers(2))]
            well = 2 * chamber - int(rng.integers(2))
            thresholds[well - 1] = 20
            for w in {2 * a - 1, 2 * a, 2 * b - 1, 2 * b} - {well}:
                if thresholds[w - 1] == 20:
                    thresholds[w - 1] = OFF
        yield section(linkage, (tuple(thresholds), kinds[int(rng.integers(len(kinds)))]))


def test_paired_from_program_is_unchanged() -> None:
    swapped = [(2, 1), (4, 3), (6, 5), (8, 7), (10, 9), (12, 11)]
    n = 0
    for sec in _cases():
        for sets in (None, swapped):
            for pi in ("left", "right"):
                assert paired_from_program(sec, sets, pi) == _paired_before_roles(sec, sets, pi)
                n += 1
    assert n > 1000


def test_the_pr_programs_give_paired_and_yoked_roles() -> None:
    sec = op.parse_program(pr_program({1: (1, 4, 5)})).section(1)
    got = roles.chamber_roles(roles.linkage_view(sec, None, None), TWO_WELL)
    assert got == {1: P, 2: Y, 3: Y, 4: P, 5: P, 6: Y}
    assert paired_from_program(sec) == ([1, 4, 5], [], [])
