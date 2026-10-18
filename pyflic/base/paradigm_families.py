"""The Paradigm Families: which Paradigm types pyflic checks and summarises alike.

A **Paradigm Family** (``CONTEXT.md``) is a group of Paradigm types the
firmware lights by the same mechanism, so pyflic checks and summarises them
with the same code (``docs/paradigm-analyses-plan.md``, decisions 1, 2 and 9,
contract C5):

* **open loop**: OpenLoop, and any Well set ``On``; lit regardless of the fly;
* **closed loop**: ClosedLoop, and the Acclimation of the types that have
  one; contact lights the LED for the contact and its Hold;
* **fixed length**: FixedInterval, ProgressiveRatio and FixedRatio in Main;
  an earned Activation lasts exactly ``ActivationMs``.  Its *interval* branch
  (FixedInterval) is earned by contact once the lockout has passed, its
  *ratio* branch by the Firmware Event that meets the Requirement;
* **non-feeding**: NonFeeding; dark while the fly feeds.

A Well's family follows its Phase: a FixedInterval Well in Acclimation is
closed loop until its Acclimation ends.  ``Off`` Wells belong to no family.

:data:`FAMILIES` declares, per family, the columns each later stream fills:
its light-QC columns in ``opto_light_qc.csv`` (stream S1), its light-table
columns (S2), its headline metrics (decision 9) and its rule figure (S3).
The streams fill in the values; they do not rename the columns.  The
fixed-length family's two branches differ in their headline set and figure,
which :data:`BRANCH_HEADLINE` and :data:`BRANCH_FIGURE` hold.

Pure: it reads :mod:`pyflic.base.opto_program`'s modes and Paradigms only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from . import opto_program as op

OPEN_LOOP, CLOSED_LOOP, FIXED_LENGTH, NON_FEEDING = (
    "open loop", "closed loop", "fixed length", "non-feeding")
#: The families in the order every report and table lists them.
FAMILY_ORDER: tuple[str, ...] = (OPEN_LOOP, CLOSED_LOOP, FIXED_LENGTH, NON_FEEDING)
#: The fixed-length family's branches.
INTERVAL_BRANCH, RATIO_BRANCH = "interval", "ratio"
BRANCH_ORDER: tuple[str, ...] = (INTERVAL_BRANCH, RATIO_BRANCH)

#: Stream S3's rule-figure kinds (``rule_figures.py``).
FIGURE_ACTIVATION_LENGTH = "activation_length"
FIGURE_ONSET_SPACING = "onset_spacing"
FIGURE_REQUIREMENT_SERIES = "requirement_series"
FIGURE_RELIGHT_DELAY = "relight_delay"

#: The light-QC columns every family's groups get (stream S1): *interval
#: started late* and *DFM restarted*.
COMMON_QC_COLUMNS: tuple[str, ...] = ("IntervalLagSec", "Restarts")
#: The headline metric any member with Acclimation adds (decision 9).
ACCLIMATION_HEADLINE: tuple[str, ...] = ("AcclimationEndMin",)
#: The closed-loop headline metric that needs ``MaxOnMs`` (decision 9).
MAX_ON_HEADLINE = "CutOffs"


@dataclass(frozen=True)
class Family:
    """One Paradigm Family and the columns the streams fill for it."""

    key: str                          # OPEN_LOOP, CLOSED_LOOP, FIXED_LENGTH, NON_FEEDING
    title: str                        # "Open loop", "Closed loop", ...
    modes: tuple[str, ...]            # opto_program mode strings
    qc_columns: tuple[str, ...]       # S1's columns in opto_light_qc.csv
    summary_columns: tuple[str, ...]  # S2's columns in the light table
    headline: tuple[str, ...]         # decision 9; CutOffs only with MaxOnMs
    figure: str | None                # S3's rule figure kind; per branch for fixed length


FAMILIES: dict[str, Family] = {
    OPEN_LOOP: Family(
        key=OPEN_LOOP, title="Open loop", modes=(op.OPEN_LOOP,),
        qc_columns=("OpenLoopLitFraction",),
        summary_columns=("LicksPerMinLit", "LicksPerMinDark", "LightFeedingIndex"),
        headline=("LitSec", "LightFeedingIndex"),
        figure=None),
    CLOSED_LOOP: Family(
        key=CLOSED_LOOP, title="Closed loop", modes=(op.CLOSED_LOOP, op.CLOSED_LOOP_MAX),
        qc_columns=("ShortActivations", "OverMaxOnActivations", "CutOffs"),
        summary_columns=("MedianActivationSec", "CutOffs", "MainActivations"),
        headline=("Activations", "LitSec", "MedianActivationSec", MAX_ON_HEADLINE),
        figure=FIGURE_ACTIVATION_LENGTH),
    FIXED_LENGTH: Family(
        key=FIXED_LENGTH, title="Fixed length",
        modes=(op.FIXED_INTERVAL, op.PROGRESSIVE_RATIO, op.FIXED_RATIO),
        qc_columns=("WrongLengthActivations", "LockoutViolations", "MissedContacts",
                    "SeriesMismatches"),
        summary_columns=("MaxActivations", "RewardEfficiency", "MedianReturnSec",
                         "LockedOutContactSec", "MainActivations"),
        headline=("Activations", "RewardEfficiency", "MedianReturnSec",
                  "LastRequirementMet", "FirmwareEvents"),
        figure=None),
    NON_FEEDING: Family(
        key=NON_FEEDING, title="Non-feeding", modes=(op.NON_FEEDING,),
        qc_columns=("NonFeedingDarkSec", "RelightDelayMs", "OverMaxOnActivations"),
        summary_columns=("Suppressions", "MedianSuppressionSec"),
        headline=("LitFraction", "Suppressions"),
        figure=FIGURE_RELIGHT_DELAY),
}

#: The fixed-length family's headline set per branch (decision 9);
#: ``FAMILIES[FIXED_LENGTH].headline`` is the two together.
BRANCH_HEADLINE: dict[str, tuple[str, ...]] = {
    INTERVAL_BRANCH: ("Activations", "RewardEfficiency", "MedianReturnSec"),
    RATIO_BRANCH: ("Activations", "LastRequirementMet", "FirmwareEvents"),
}
#: The fixed-length family's rule figure per branch (stream S3).
BRANCH_FIGURE: dict[str, str] = {
    INTERVAL_BRANCH: FIGURE_ONSET_SPACING,
    RATIO_BRANCH: FIGURE_REQUIREMENT_SERIES,
}

_FAMILY_OF_MODE: dict[str, str] = {mode: f.key for f in FAMILIES.values() for mode in f.modes}
_BRANCH_OF_MODE: dict[str, str] = {
    op.FIXED_INTERVAL: INTERVAL_BRANCH,
    op.PROGRESSIVE_RATIO: RATIO_BRANCH,
    op.FIXED_RATIO: RATIO_BRANCH,
}


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def family_of(mode, *, acclimation: bool = False) -> str | None:
    """The family of a Well running *mode* (an ``opto_program`` mode
    string): fixed-length modes are closed loop while *acclimation* (the
    Well in Phase ``A``).  ``None`` for ``off``, an unknown or not-judged
    mode, and anything that is not a mode (``NaN``, ``None``)."""
    if not isinstance(mode, str):
        return None
    family = _FAMILY_OF_MODE.get(mode)
    if family == FIXED_LENGTH and acclimation:
        return CLOSED_LOOP
    return family


def branch_of(mode) -> str | None:
    """The fixed-length branch of *mode*: :data:`INTERVAL_BRANCH` for
    FixedInterval, :data:`RATIO_BRANCH` for the ratio types, else ``None``."""
    return _BRANCH_OF_MODE.get(mode) if isinstance(mode, str) else None


def rule_figure(mode, *, acclimation: bool = False) -> str | None:
    """S3's rule-figure kind for a Well running *mode*: its family's, or
    for fixed length its branch's; ``None`` for open loop (the Program
    timeline shows its schedule) and for modes in no family."""
    family = family_of(mode, acclimation=acclimation)
    if family == FIXED_LENGTH:
        return BRANCH_FIGURE[branch_of(mode)]
    return FAMILIES[family].figure if family is not None else None


# ---------------------------------------------------------------------------
# A program's families
# ---------------------------------------------------------------------------

def _intervals(program, dfm_ids) -> list[op.ProgramInterval]:
    if program is None or getattr(program, "grammar", None) == op.GRAMMAR_SIMPLE:
        return []
    ids = sorted(program.dfms) if dfm_ids is None else sorted({int(d) for d in dfm_ids})
    return [iv for d in ids if program.section(d) is not None
            for iv in program.section(d).intervals]


def _interval_modes(iv: op.ProgramInterval) -> tuple[set[str], set[str]]:
    """``(families, branches)`` an interval line runs: its Paradigm's for
    its level Wells (closed loop too with Acclimation), open loop for an
    ``On`` Well or for level Wells under OpenLoop.  A line whose Wells are
    all ``Off`` runs nothing."""
    families: set[str] = set()
    branches: set[str] = set()
    p = iv.paradigm
    if iv.open_wells():
        families.add(OPEN_LOOP)
    if iv.trigger_wells():
        if p.type == op.OPEN_LOOP:
            families.add(OPEN_LOOP)
        else:
            family = family_of(p.mode)
            if family is not None:
                families.add(family)
            branch = branch_of(p.mode)
            if branch is not None:
                branches.add(branch)
            if p.acclimation and p.type in op.ACCLIMATION_PARADIGMS:
                families.add(CLOSED_LOOP)
    return families, branches


def families_in(program, dfm_ids=None) -> list[str]:
    """The families of *program*'s Paradigms for *dfm_ids* (default every
    DFM section), in :data:`FAMILY_ORDER`: each interval line's Paradigm
    where some Well has a level threshold, closed loop as well for a
    Paradigm with Acclimation > 0, and open loop for a line with a Well
    ``On``.  ``[]`` without a program, or for the export of a recording made
    without one (every Well ``Off``)."""
    found: set[str] = set()
    for iv in _intervals(program, dfm_ids):
        found |= _interval_modes(iv)[0]
    return [f for f in FAMILY_ORDER if f in found]


def branches_in(program, dfm_ids=None) -> list[str]:
    """The fixed-length branches *program* runs for *dfm_ids*, in
    :data:`BRANCH_ORDER`: what to pass :func:`headline_metrics` in place of
    :data:`FIXED_LENGTH`, so a FixedInterval-only member is not given the
    ratio branch's headline metrics."""
    found: set[str] = set()
    for iv in _intervals(program, dfm_ids):
        found |= _interval_modes(iv)[1]
    return [b for b in BRANCH_ORDER if b in found]


def max_on_in(program, dfm_ids=None) -> bool:
    """Whether a ClosedLoop Paradigm with ``MaxOnMs`` runs in *program* for
    *dfm_ids*: the closed-loop headline set then includes ``CutOffs``."""
    return any(iv.trigger_wells() and iv.paradigm.mode == op.CLOSED_LOOP_MAX
               for iv in _intervals(program, dfm_ids))


def acclimation_in(program, dfm_ids=None) -> bool:
    """Whether a Paradigm with Acclimation runs in *program* for *dfm_ids*."""
    return any(iv.trigger_wells() and iv.paradigm.acclimation
               and iv.paradigm.type in op.ACCLIMATION_PARADIGMS
               for iv in _intervals(program, dfm_ids))


def headline_metrics(families: Iterable[str], *, max_on: bool = False,
                     acclimation: bool = False) -> list[str]:
    """The headline metrics of *families* (decision 9), in
    :data:`FAMILY_ORDER`, each once.

    An item is a family key, or a fixed-length branch
    (:data:`INTERVAL_BRANCH`, :data:`RATIO_BRANCH`) standing for that branch
    alone; :data:`FIXED_LENGTH` itself gives both branches' sets.  ``CutOffs``
    joins closed loop only with *max_on* (a ClosedLoop with ``MaxOnMs``), and
    ``AcclimationEndMin`` comes last with *acclimation*.  ``None`` items are
    skipped; an unknown key is a ``ValueError``."""
    keys = {f for f in families if f is not None}
    unknown = keys - set(FAMILY_ORDER) - set(BRANCH_ORDER)
    if unknown:
        raise ValueError(f"not a Paradigm Family or branch: {', '.join(sorted(unknown))}")
    out: list[str] = []

    def add(names: Iterable[str]) -> None:
        out.extend(n for n in names if n not in out)

    for key in FAMILY_ORDER:
        if key == FIXED_LENGTH:
            branches = [b for b in BRANCH_ORDER if b in keys or FIXED_LENGTH in keys]
            for branch in branches:
                add(BRANCH_HEADLINE[branch])
        elif key in keys:
            add(n for n in FAMILIES[key].headline if max_on or n != MAX_ON_HEADLINE)
    if acclimation:
        add(ACCLIMATION_HEADLINE)
    return out


# ---------------------------------------------------------------------------
# The rule in words
# ---------------------------------------------------------------------------

def _ms(value) -> str:
    return f"{int(value or 0)} ms"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _acclimation_clause(p: op.Paradigm) -> str:
    n = int(p.acclimation or 0)
    if n <= 0 or p.type not in op.ACCLIMATION_PARADIGMS:
        return ""
    which = "1 closed-loop Activation first (Acclimation), lit" if n == 1 else \
        f"{n} closed-loop Activations first (Acclimation), each lit"
    return f"; {which} during contact and for {_ms(p.activation_ms)} after"


def _event_clause(p: op.Paradigm) -> str:
    gap = p.event_gap_ms
    if gap is None:
        return "; no Firmware Event starts while the LED is lit"
    return (f"; a Firmware Event ends after {_ms(gap)} without contact, and none starts "
            f"while the LED is lit")


def _series_text(p: op.Paradigm) -> str:
    """The Requirement series of a ProgressiveRatio, its first values and
    its settings."""
    if p.series is None:
        return "Requirement series not stated (a pre-4.0.0 program)"
    shown = [p.requirement_for(k) for k in range(1, 5)]
    values = ", ".join(str(v) for v in shown)
    cap = int(p.cap) if p.cap else op.MAX_REQUIREMENT
    if p.series == op.SERIES_EXPONENTIAL:
        scale = 5.0 if p.scale is None else float(p.scale)
        rate = 0.2 if p.rate is None else float(p.rate)
        how = (f"Exponential, Scale {scale:g} and Rate {rate:g}: Scale * e^(Rate * k) - "
               f"Scale, rounded")
    else:
        first = 1 if p.first_requirement is None else int(p.first_requirement)
        step = 0 if p.step is None else int(p.step)
        how = f"Arithmetic, FirstRequirement {first} and Step {step}"
    return f"Requirements {values}, ... ({how}; at most the Cap {cap})"


def rule_sentence(paradigm: op.Paradigm) -> str:
    """The firmware's rule for *paradigm*, in words, with its settings: for
    example ``CL500 (closed loop): lit during contact and for 500 ms after;
    at most 2000 ms per light period, then dark until the bout ends (100 ms
    without contact)``.  The name is followed by the family, and for fixed
    length the branch.  Every Paradigm type has one; the light's frequency
    and pulse width are not part of the rule and are left to the program
    table."""
    p = paradigm
    name = p.name
    if p.type == op.OPEN_LOOP:
        return f"{name} (open loop): lit throughout, whatever the fly does; no Activations"
    if p.type == op.CLOSED_LOOP:
        text = f"{name} (closed loop): lit during contact and for {_ms(p.hold_ms)} after"
        if (p.max_on_ms or 0) > 0:
            gap = 100 if p.event_gap_ms is None else int(p.event_gap_ms)
            text += (f"; at most {_ms(p.max_on_ms)} per light period, then dark until the "
                     f"bout ends ({gap} ms without contact)")
        return text
    if p.type == op.FIXED_INTERVAL:
        activation = int(p.activation_ms or 0)
        lockout = int(p.lockout_ms or 0)
        if lockout >= activation and lockout > 0:
            when = f"once {lockout} ms have passed since the last start"
        elif lockout > 0:
            when = (f"as soon as the last Activation has ended (the {lockout} ms lockout "
                    f"is shorter), so held contact keeps it lit")
        else:
            when = "whenever it is not already lit, so held contact keeps it lit"
        return (f"{name} (fixed length, interval): a contact lights the LED for "
                f"{activation} ms {when}{_acclimation_clause(p)}")
    if p.type == op.NON_FEEDING:
        delay = _ms(p.on_delay_ms)
        if (p.max_on_ms or 0) > 0:
            lit = (f"lit {delay} after contact ends, for at most {_ms(p.max_on_ms)}; "
                   f"lit at the Interval's start without contact, for at most "
                   f"{_ms(p.max_on_ms)} too")
        else:
            lit = (f"lit {delay} after contact ends, until the next contact; lit at the "
                   f"Interval's start without contact")
        return f"{name} (non-feeding): dark during contact; {lit}"
    if p.type == op.PROGRESSIVE_RATIO:
        return (f"{name} (fixed length, ratio): the Firmware Event that meets the "
                f"Requirement lights the LED for {_ms(p.activation_ms)}; {_series_text(p)}"
                f"{_event_clause(p)}{_acclimation_clause(p)}")
    if p.type == op.FIXED_RATIO:
        ratio = p.ratio
        if ratio is None:
            which = "the Firmware Event that meets the Requirement (Ratio not stated)"
        elif int(ratio) <= 1:
            which = "every Firmware Event (Ratio 1)"
        else:
            which = f"every {_ordinal(int(ratio))} Firmware Event (Ratio {int(ratio)})"
        return (f"{name} (fixed length, ratio): {which} lights the LED for "
                f"{_ms(p.activation_ms)}{_event_clause(p)}{_acclimation_clause(p)}")
    return f"{name} ({p.type_name}): a rule pyflic does not know"
