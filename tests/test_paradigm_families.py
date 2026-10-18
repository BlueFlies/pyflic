"""The Paradigm Family registry (``pyflic/base/paradigm_families.py``).

Contract C5 of ``docs/paradigm-analyses-plan.md``: every mode maps to its
family (fixed length is closed loop in Acclimation), a program's families
are read from its Paradigms, the headline sets are decision 9's, the column
tuples are the streams', and every Paradigm type has its rule in words.
"""

from __future__ import annotations

import numpy as np
import pytest

from pyflic.base import opto_program as op
from pyflic.base import opto_qc as oq
from pyflic.base import paradigm_families as pf

from v4_fixtures import (
    choice_pr_spec,
    family_specs,
    fixed_ratio_spec,
    one_of_each_spec,
    program_text,
    repeating_open_loop_spec,
    stress_spec,
    yoked_controls_spec,
)


def program_of(spec) -> op.OptoProgram:
    return op.parse_program(program_text(spec))


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

MODE_FAMILIES = {
    op.OPEN_LOOP: (pf.OPEN_LOOP, pf.OPEN_LOOP),
    op.CLOSED_LOOP: (pf.CLOSED_LOOP, pf.CLOSED_LOOP),
    op.CLOSED_LOOP_MAX: (pf.CLOSED_LOOP, pf.CLOSED_LOOP),
    op.FIXED_INTERVAL: (pf.FIXED_LENGTH, pf.CLOSED_LOOP),
    op.PROGRESSIVE_RATIO: (pf.FIXED_LENGTH, pf.CLOSED_LOOP),
    op.FIXED_RATIO: (pf.FIXED_LENGTH, pf.CLOSED_LOOP),
    op.NON_FEEDING: (pf.NON_FEEDING, pf.NON_FEEDING),
}


@pytest.mark.parametrize("mode", sorted(MODE_FAMILIES))
def test_every_mode_maps_to_its_family(mode: str) -> None:
    main, acclimation = MODE_FAMILIES[mode]
    assert pf.family_of(mode) == main
    assert pf.family_of(mode, acclimation=True) == acclimation
    assert mode in pf.FAMILIES[main].modes


def test_off_unknown_and_not_judged_modes_have_no_family() -> None:
    for mode in (op.LIGHTS_OFF, op.UNKNOWN_PARADIGM, oq.UNKNOWN_INSTRUCTION, oq.NOT_JUDGED,
                 "unscheduled", None, np.nan, ""):
        assert pf.family_of(mode) is None and pf.family_of(mode, acclimation=True) is None
        assert pf.branch_of(mode) is None and pf.rule_figure(mode) is None


def test_every_paradigm_type_has_a_family() -> None:
    covered = {mode for family in pf.FAMILIES.values() for mode in family.modes}
    assert covered == {*op.PARADIGM_TYPES, op.CLOSED_LOOP_MAX}
    ## Each mode in exactly one family.
    assert sum(len(f.modes) for f in pf.FAMILIES.values()) == len(covered)


def test_the_branches_of_fixed_length() -> None:
    assert pf.branch_of(op.FIXED_INTERVAL) == pf.INTERVAL_BRANCH
    assert pf.branch_of(op.PROGRESSIVE_RATIO) == pf.RATIO_BRANCH
    assert pf.branch_of(op.FIXED_RATIO) == pf.RATIO_BRANCH
    for mode in (op.OPEN_LOOP, op.CLOSED_LOOP, op.CLOSED_LOOP_MAX, op.NON_FEEDING):
        assert pf.branch_of(mode) is None


def test_the_rule_figures_are_s3s_kinds() -> None:
    assert pf.rule_figure(op.CLOSED_LOOP) == pf.rule_figure(op.CLOSED_LOOP_MAX) \
        == pf.FIGURE_ACTIVATION_LENGTH
    assert pf.rule_figure(op.FIXED_INTERVAL) == pf.FIGURE_ONSET_SPACING
    assert pf.rule_figure(op.PROGRESSIVE_RATIO) == pf.rule_figure(op.FIXED_RATIO) \
        == pf.FIGURE_REQUIREMENT_SERIES
    assert pf.rule_figure(op.NON_FEEDING) == pf.FIGURE_RELIGHT_DELAY
    assert pf.rule_figure(op.OPEN_LOOP) is None
    ## Acclimation is closed loop, whatever the Paradigm.
    assert pf.rule_figure(op.FIXED_RATIO, acclimation=True) == pf.FIGURE_ACTIVATION_LENGTH


# ---------------------------------------------------------------------------
# The registry's declarations
# ---------------------------------------------------------------------------

def test_the_families_are_in_order_and_keyed() -> None:
    assert pf.FAMILY_ORDER == ("open loop", "closed loop", "fixed length", "non-feeding")
    assert tuple(pf.FAMILIES) == pf.FAMILY_ORDER
    assert [f.title for f in pf.FAMILIES.values()] == ["Open loop", "Closed loop",
                                                        "Fixed length", "Non-feeding"]
    assert all(key == f.key for key, f in pf.FAMILIES.items())


def test_the_qc_columns_are_s1s() -> None:
    """S1's table, family by family; *interval started late* and *DFM
    restarted* apply to every family."""
    columns = {key: f.qc_columns for key, f in pf.FAMILIES.items()}
    assert columns == {
        pf.OPEN_LOOP: ("OpenLoopLitFraction",),
        pf.CLOSED_LOOP: ("ShortActivations", "OverMaxOnActivations", "CutOffs"),
        pf.FIXED_LENGTH: ("WrongLengthActivations", "LockoutViolations", "MissedContacts",
                          "SeriesMismatches"),
        pf.NON_FEEDING: ("NonFeedingDarkSec", "RelightDelayMs", "OverMaxOnActivations"),
    }
    assert pf.COMMON_QC_COLUMNS == ("IntervalLagSec", "Restarts")
    ## OpenLoopLitFraction is already a column of the QC table.
    assert "OpenLoopLitFraction" in oq.OPTO_QC_COLUMNS


def test_the_summary_columns_are_s2s() -> None:
    columns = {key: f.summary_columns for key, f in pf.FAMILIES.items()}
    assert columns == {
        pf.OPEN_LOOP: ("LicksPerMinLit", "LicksPerMinDark", "LightFeedingIndex"),
        pf.CLOSED_LOOP: ("MedianActivationSec", "CutOffs", "MainActivations"),
        pf.FIXED_LENGTH: ("MaxActivations", "RewardEfficiency", "MedianReturnSec",
                          "LockedOutContactSec", "MainActivations"),
        pf.NON_FEEDING: ("Suppressions", "MedianSuppressionSec"),
    }


def test_the_figures_are_declared() -> None:
    assert {k: f.figure for k, f in pf.FAMILIES.items()} == {
        pf.OPEN_LOOP: None, pf.CLOSED_LOOP: pf.FIGURE_ACTIVATION_LENGTH,
        pf.FIXED_LENGTH: None, pf.NON_FEEDING: pf.FIGURE_RELIGHT_DELAY}
    assert pf.BRANCH_FIGURE == {pf.INTERVAL_BRANCH: pf.FIGURE_ONSET_SPACING,
                                pf.RATIO_BRANCH: pf.FIGURE_REQUIREMENT_SERIES}


# ---------------------------------------------------------------------------
# Headline metrics (decision 9)
# ---------------------------------------------------------------------------

def test_headline_metrics_per_family() -> None:
    assert pf.headline_metrics([pf.OPEN_LOOP]) == ["LitSec", "LightFeedingIndex"]
    assert pf.headline_metrics([pf.CLOSED_LOOP]) == ["Activations", "LitSec",
                                                     "MedianActivationSec"]
    assert pf.headline_metrics([pf.CLOSED_LOOP], max_on=True) == [
        "Activations", "LitSec", "MedianActivationSec", "CutOffs"]
    assert pf.headline_metrics([pf.INTERVAL_BRANCH]) == ["Activations", "RewardEfficiency",
                                                         "MedianReturnSec"]
    assert pf.headline_metrics([pf.RATIO_BRANCH]) == ["Activations", "LastRequirementMet",
                                                      "FirmwareEvents"]
    assert pf.headline_metrics([pf.NON_FEEDING]) == ["LitFraction", "Suppressions"]
    assert pf.headline_metrics([pf.RATIO_BRANCH], acclimation=True)[-1] == "AcclimationEndMin"


def test_headline_metrics_pool_in_family_order_once_each() -> None:
    assert pf.headline_metrics([pf.NON_FEEDING, pf.OPEN_LOOP]) == [
        "LitSec", "LightFeedingIndex", "LitFraction", "Suppressions"]
    ## Fixed length without a branch is both branches.
    assert pf.headline_metrics([pf.FIXED_LENGTH]) == [
        "Activations", "RewardEfficiency", "MedianReturnSec", "LastRequirementMet",
        "FirmwareEvents"]
    assert pf.headline_metrics([pf.CLOSED_LOOP, pf.RATIO_BRANCH], acclimation=True) == [
        "Activations", "LitSec", "MedianActivationSec", "LastRequirementMet",
        "FirmwareEvents", "AcclimationEndMin"]
    assert pf.headline_metrics([]) == [] and pf.headline_metrics([None]) == []
    with pytest.raises(ValueError):
        pf.headline_metrics(["closed-loop"])


def test_a_programs_headline_metrics() -> None:
    """What a member's report asks for: its families, the fixed-length
    branches it runs, MaxOnMs and Acclimation, read from Program.txt."""
    choice = program_of(choice_pr_spec())
    families = [f for f in pf.families_in(choice) if f != pf.FIXED_LENGTH] + pf.branches_in(choice)
    assert pf.headline_metrics(families, max_on=pf.max_on_in(choice),
                               acclimation=pf.acclimation_in(choice)) == [
        "Activations", "LitSec", "MedianActivationSec", "CutOffs", "LastRequirementMet",
        "FirmwareEvents", "AcclimationEndMin"]


# ---------------------------------------------------------------------------
# A program's families
# ---------------------------------------------------------------------------

FAMILY_SPEC_FAMILIES = {
    "closed_max": ([pf.CLOSED_LOOP], [], True, False),
    "fixed_interval": ([pf.CLOSED_LOOP, pf.FIXED_LENGTH], [pf.INTERVAL_BRANCH], False, True),
    "non_feeding": ([pf.NON_FEEDING], [], False, False),
    "exponential": ([pf.CLOSED_LOOP, pf.FIXED_LENGTH], [pf.RATIO_BRANCH], False, True),
    "restart": ([pf.CLOSED_LOOP, pf.FIXED_LENGTH], [pf.RATIO_BRANCH], False, True),
}


@pytest.mark.parametrize("key", sorted(FAMILY_SPEC_FAMILIES))
def test_families_in_each_family_spec(key: str) -> None:
    program = program_of(family_specs()[key])
    families, branches, max_on, acclimation = FAMILY_SPEC_FAMILIES[key]
    assert pf.families_in(program) == families
    assert pf.branches_in(program) == branches
    assert pf.max_on_in(program) is max_on and pf.acclimation_in(program) is acclimation


def test_families_in_the_other_specs() -> None:
    every = list(pf.FAMILY_ORDER)
    assert pf.families_in(program_of(choice_pr_spec())) == [pf.CLOSED_LOOP, pf.FIXED_LENGTH]
    assert pf.families_in(program_of(fixed_ratio_spec())) == [pf.CLOSED_LOOP, pf.FIXED_LENGTH]
    assert pf.families_in(program_of(yoked_controls_spec())) == [pf.CLOSED_LOOP]
    ## Open, every Well On, then every Well Off: open loop only.
    assert pf.families_in(program_of(repeating_open_loop_spec())) == [pf.OPEN_LOOP]
    assert pf.families_in(program_of(stress_spec())) == every
    one = program_of(one_of_each_spec())
    assert pf.families_in(one) == every
    assert pf.branches_in(one) == [pf.INTERVAL_BRANCH, pf.RATIO_BRANCH]
    ## DFM by DFM: OpenLoop, ClosedLoop, FixedInterval, NonFeeding, Closed then
    ## PR10 (with Acclimation), FixedRatio (without).
    assert [pf.families_in(one, [d]) for d in range(1, 7)] == [
        [pf.OPEN_LOOP], [pf.CLOSED_LOOP], [pf.FIXED_LENGTH], [pf.NON_FEEDING],
        [pf.CLOSED_LOOP, pf.FIXED_LENGTH], [pf.FIXED_LENGTH]]
    assert pf.families_in(one, [3, 4]) == [pf.FIXED_LENGTH, pf.NON_FEEDING]
    assert pf.branches_in(one, [6]) == [pf.RATIO_BRANCH]
    ## A DFM the program lacks has none.
    assert pf.families_in(one, [9]) == []


def test_families_in_without_a_program() -> None:
    from pathlib import Path

    assert pf.families_in(None) == [] and pf.branches_in(None) == []
    simple = op.read_program(Path(__file__).parent / "fixtures" / "Program_simple.txt")
    assert simple.grammar == op.GRAMMAR_SIMPLE
    assert pf.families_in(simple) == [] and not pf.max_on_in(simple)


def test_families_in_a_legacy_program() -> None:
    """A pre-4.0.0 export: its Paradigms are inferred from F/P/D/L/M, a
    threshold of 0 is On."""
    from opto_fixtures import case_program

    assert pf.families_in(op.parse_program(case_program())) == [pf.OPEN_LOOP, pf.CLOSED_LOOP]
    assert pf.families_in(op.parse_program(case_program(delay=60000))) == [
        pf.OPEN_LOOP, pf.FIXED_LENGTH]


# ---------------------------------------------------------------------------
# The rule in words
# ---------------------------------------------------------------------------

def _paradigms():
    found = {}
    for spec in (*family_specs().values(), choice_pr_spec(), one_of_each_spec(), stress_spec(),
                 fixed_ratio_spec()):
        found.update(program_of(spec).paradigms)
    return found


RULES = {
    "Open": "Open (open loop): lit throughout, whatever the fly does; no Activations",
    "CL": "CL (closed loop): lit during contact and for 500 ms after",
    "CL500": ("CL500 (closed loop): lit during contact and for 500 ms after; at most 2000 ms "
              "per light period, then dark until the bout ends (100 ms without contact)"),
    "FI10s": ("FI10s (fixed length, interval): a contact lights the LED for 1000 ms once "
              "10000 ms have passed since the last start"),
    "FI500": ("FI500 (fixed length, interval): a contact lights the LED for 1500 ms as soon "
              "as the last Activation has ended (the 500 ms lockout is shorter), so held "
              "contact keeps it lit; 3 closed-loop Activations first (Acclimation), each lit "
              "during contact and for 1500 ms after"),
    "NF1000": ("NF1000 (non-feeding): dark during contact; lit 1000 ms after contact ends, "
               "until the next contact; lit at the Interval's start without contact"),
    "NFMax5s": ("NFMax5s (non-feeding): dark during contact; lit 1000 ms after contact ends, "
                "for at most 5000 ms; lit at the Interval's start without contact, for at most "
                "5000 ms too"),
    "PR10": ("PR10 (fixed length, ratio): the Firmware Event that meets the Requirement lights "
             "the LED for 500 ms; Requirements 1, 11, 21, 31, ... (Arithmetic, FirstRequirement "
             "1 and Step 10; at most the Cap 200); a Firmware Event ends after 100 ms without "
             "contact, and none starts while the LED is lit; 10 closed-loop Activations first "
             "(Acclimation), each lit during contact and for 500 ms after"),
    "PRExp": ("PRExp (fixed length, ratio): the Firmware Event that meets the Requirement "
              "lights the LED for 500 ms; Requirements 1, 2, 4, 6, ... (Exponential, Scale 5 "
              "and Rate 0.2: Scale * e^(Rate * k) - Scale, rounded; at most the Cap 65535); a "
              "Firmware Event ends after 100 ms without contact, and none starts while the LED "
              "is lit; 2 closed-loop Activations first (Acclimation), each lit during contact "
              "and for 500 ms after"),
    "FR3": ("FR3 (fixed length, ratio): every 3rd Firmware Event (Ratio 3) lights the LED for "
            "500 ms; a Firmware Event ends after 100 ms without contact, and none starts while "
            "the LED is lit; 2 closed-loop Activations first (Acclimation), each lit during "
            "contact and for 500 ms after"),
    "FR1": ("FR1 (fixed length, ratio): every 3rd Firmware Event (Ratio 3) lights the LED for "
            "40 ms; a Firmware Event ends after 150 ms without contact, and none starts while "
            "the LED is lit; 1 closed-loop Activation first (Acclimation), lit during contact "
            "and for 40 ms after"),
}


@pytest.mark.parametrize("name", sorted(RULES))
def test_the_rule_in_words(name: str) -> None:
    assert pf.rule_sentence(_paradigms()[name]) == RULES[name]


def test_every_paradigm_type_and_setting_has_its_rule() -> None:
    """Every Paradigm of every spec: the name, then the family, and the
    settings that shape the light."""
    seen_types = set()
    for p in _paradigms().values():
        text = pf.rule_sentence(p)
        seen_types.add(p.type)
        family = pf.family_of(p.mode)
        branch = pf.branch_of(p.mode)
        label = f"{family}, {branch}" if branch else family
        assert text.startswith(f"{p.name} ({label}): "), text
        for value in (p.hold_ms if p.type == op.CLOSED_LOOP else None, p.activation_ms,
                      p.on_delay_ms, p.max_on_ms or None, p.lockout_ms or None, p.ratio):
            if value is not None:
                assert f"{value}" in text, (p.name, value, text)
        if p.acclimation:
            assert f"{p.acclimation} closed-loop Activation" in text
        if p.type in op.RATIO_PARADIGMS:
            assert f"after {p.event_gap_ms} ms without contact" in text
    assert seen_types == set(op.PARADIGM_TYPES)


def test_the_rule_of_settings_the_specs_lack() -> None:
    zero_lockout = op.Paradigm(name="FI0", type=op.FIXED_INTERVAL, frequency_hz=40,
                               pulse_width_ms=8, activation_ms=800, lockout_ms=0)
    assert pf.rule_sentence(zero_lockout) == (
        "FI0 (fixed length, interval): a contact lights the LED for 800 ms whenever it is "
        "not already lit, so held contact keeps it lit")
    every = op.Paradigm(name="FR1x", type=op.FIXED_RATIO, frequency_hz=40, pulse_width_ms=8,
                        activation_ms=500, ratio=1, event_gap_ms=100)
    assert pf.rule_sentence(every).startswith(
        "FR1x (fixed length, ratio): every Firmware Event (Ratio 1) lights the LED for 500 ms")
    ## A pre-4.0.0 progressive ratio has no Requirement series.
    legacy = op.paradigm_from_legacy(op.OptoParams(frequency=40, pulse_width=8, decay=500,
                                                   delay=10, max_time_on=200))
    assert legacy.type == op.PROGRESSIVE_RATIO
    text = pf.rule_sentence(legacy)
    assert "Requirement series not stated (a pre-4.0.0 program)" in text
    assert text.startswith(f"{legacy.name} (fixed length, ratio): ")
