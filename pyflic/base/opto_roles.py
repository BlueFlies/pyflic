"""Roles: what each chamber of an optogenetic DFM was to the light.

A chamber's **Role** (decision 9 of ``docs/v4-data-plan.md``) says how its
light related to its own fly, in any design, not only Progressive Ratio:

* **Paired**: its Trigger Well switches a Linkage Group that also lights
  other chambers, and it is the only chamber of the group that can;
* **Yoked**: it shares a Linkage Group with a Paired (or Mutual) chamber and
  holds no Trigger Well of that group: lit when its partner earns light;
* **Mutual**: one of several chambers of one Linkage Group that each hold a
  Trigger Well;
* **Self**: its Trigger Well's group lights no other chamber;
* **Open**: lit regardless of its fly, every well ``On`` or in a group lit
  open loop;
* **Unlit**: none of the above.

Roles come from a :class:`LinkageView`, built by :func:`linkage_view` from
the best source there is: the Opto Program's DFM section (``Linkage:`` and
each Program Interval's thresholds), else, on a generation-3 recording, the
data (Trigger Wells from ``Activations``, Linkage from identical ``OnMs``,
decision 10), else, on a generation-1 or -2 recording, the wells lit
identically in ``OptoCol1``, which cannot tell a trigger from a yoked well,
so every Role is :data:`ROLE_UNKNOWN`.

Terms are ``CONTEXT.md``'s: **Linkage Group**, **Trigger Well**, **Paired
Chamber** / **Yoked Chamber**.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable, Mapping

import numpy as np

from . import opto_program as op

if TYPE_CHECKING:
    from .dfm import DFM
    from .paradigm_state import ParadigmState

ROLE_PAIRED, ROLE_YOKED, ROLE_MUTUAL, ROLE_SELF, ROLE_OPEN, ROLE_UNLIT, ROLE_UNKNOWN = \
    "Paired", "Yoked", "Mutual", "Self", "Open", "Unlit", ""

#: The Roles of a chamber holding a Trigger Well.
TRIGGER_ROLES: tuple[str, ...] = (ROLE_PAIRED, ROLE_MUTUAL, ROLE_SELF)

#: :attr:`LinkageView.source` values.
SOURCE_PROGRAM, SOURCE_DATA, SOURCE_NONE = "program", "data", "none"

#: When a chamber's wells give it more than one Role (its wells sit in
#: different Linkage Groups), the first of these wins: a chamber holding a
#: Trigger Well always has a trigger Role, and being lit by a partner says
#: more than being lit open loop in some other Interval.
_PRECEDENCE: tuple[str, ...] = (ROLE_MUTUAL, ROLE_PAIRED, ROLE_SELF, ROLE_YOKED, ROLE_OPEN,
                                ROLE_UNLIT)

#: The two-well chamber_sets default: chamber c is wells (2c-1, 2c).
_DEFAULT_CHAMBER_SETS: tuple[tuple[int, int], ...] = tuple(
    (2 * c - 1, 2 * c) for c in range(1, 7))


@dataclass(frozen=True)
class LinkageView:
    """One DFM's light circuits and which wells drive them.

    *groups* maps a label (the program's linkage number, or a running number
    for inferred groups) to its wells.  *trigger_wells* can switch their
    group's light; *open_wells* light theirs regardless of the fly and are
    never also trigger wells (a well that triggers in one Interval and is
    ``On`` in another counts as a trigger).  *source* is ``"program"``,
    ``"data"`` or ``"none"``.
    """

    groups: dict[str, tuple[int, ...]]
    trigger_wells: frozenset[int]
    open_wells: frozenset[int]
    source: str


def linkage_view(section: op.DFMProgram | None, state: ParadigmState | None,
                 lights: np.ndarray | None) -> LinkageView:
    """The DFM's :class:`LinkageView` from the best source available.

    * *section* (the Opto Program's DFM section): groups from ``Linkage:``;
      Trigger Wells are the wells with a level threshold in some Interval and
      open wells those ``On`` in some Interval, the union over the section's
      Intervals.  Under an OpenLoop Paradigm a level well is lit regardless
      (the firmware runs no rule for it), so it counts as open there.
    * else *state* (generation 3): Trigger Wells are the wells with
      Activations; groups are the lit wells with identical ``OnMs`` columns;
      open wells are the members of lit groups without a Trigger Well, whose
      light no Activation explains.  A trigger well whose fly never fed is
      unlit and so unseen.
    * else *lights* (``(n, 12)`` bool, ``OptoCol1`` unpacked): the wells lit
      identically over the whole recording, every lit well a possible
      trigger (the light QC's inference without a program).  Source
      ``"none"``: nothing says which well drove the light.
    """
    if section is not None:
        groups = {str(label): tuple(wells) for label, wells in section.linkage_groups().items()}
        trigger: set[int] = set()
        open_: set[int] = set()
        for iv in section.intervals:
            levels = set(iv.trigger_wells())
            if iv.paradigm.type == op.OPEN_LOOP:
                open_ |= levels
            else:
                trigger |= levels
            open_ |= set(iv.open_wells())
        return LinkageView(groups, frozenset(trigger), frozenset(open_ - trigger), SOURCE_PROGRAM)

    if state is not None:
        trigger = set(state.wells_with_activations())
        lit = np.asarray(state.lit()).any(axis=0) if len(state) else np.zeros(op.N_WELLS, bool)
        lit_wells = [w for w in range(1, op.N_WELLS + 1) if lit[w - 1]]
        found = state.identical_on_ms_groups(lit_wells)
        groups = {str(k): tuple(wells) for k, wells in enumerate(found, start=1)}
        open_ = {w for wells in found if not trigger & set(wells) for w in wells}
        return LinkageView(groups, frozenset(trigger), frozenset(open_), SOURCE_DATA)

    if lights is not None and np.asarray(lights).size:
        from .opto_qc import _inferred_groups

        matrix = np.asarray(lights, dtype=bool).reshape(-1, op.N_WELLS)
        inferred = _inferred_groups(matrix)
        groups = {str(label): tuple(wells) for label, wells in inferred.items()}
        lit = frozenset(w for wells in inferred.values() for w in wells)
        return LinkageView(groups, lit, frozenset(), SOURCE_NONE)
    return LinkageView({}, frozenset(), frozenset(), SOURCE_NONE)


def chamber_roles(view: LinkageView, chamber_of_well: Mapping[int, int]) -> dict[int, str]:
    """``{chamber: Role}`` for every chamber *chamber_of_well* names.

    Per Linkage Group: in a group spanning more than one chamber, a chamber
    holding one of the group's Trigger Wells is Paired when it is the only
    one and Mutual otherwise, and the group's other chambers are Yoked; a
    trigger chamber alone in its group is Self; the chambers of a group with
    an open well (a well ``On``, or lit open loop) are Open.  A chamber whose
    wells fall in several groups takes the first of Mutual, Paired, Self,
    Yoked, Open; one with none of them is Unlit.  Without a source
    (``view.source == "none"``) every chamber is :data:`ROLE_UNKNOWN`.
    """
    chamber_of = {int(w): int(c) for w, c in chamber_of_well.items()}
    chambers = sorted(set(chamber_of.values()))
    if view.source == SOURCE_NONE:
        return {c: ROLE_UNKNOWN for c in chambers}
    found: dict[int, set[str]] = {c: set() for c in chambers}
    ## A trigger or open well no group lists lights only itself.
    grouped = {w for wells in view.groups.values() for w in wells}
    alone = sorted((view.trigger_wells | view.open_wells) - grouped)
    for wells in (*view.groups.values(), *((w,) for w in alone)):
        members = {chamber_of[w] for w in wells if w in chamber_of}
        if not members:
            continue
        triggers = {chamber_of[w] for w in wells if w in chamber_of and w in view.trigger_wells}
        if triggers and len(members) > 1:
            role = ROLE_PAIRED if len(triggers) == 1 else ROLE_MUTUAL
            for c in members:
                found[c].add(role if c in triggers else ROLE_YOKED)
        elif triggers:
            for c in triggers:
                found[c].add(ROLE_SELF)
        elif any(w in view.open_wells for w in wells):
            for c in members:
                found[c].add(ROLE_OPEN)
    ## A chamber all of whose wells are On is Open whatever group they are in.
    for c in chambers:
        own = [w for w, cc in chamber_of.items() if cc == c]
        if own and all(w in view.open_wells for w in own):
            found[c].add(ROLE_OPEN)
    return {c: next((r for r in _PRECEDENCE if r in found[c]), ROLE_UNLIT) for c in chambers}


def chamber_map(chamber_sets: Iterable[Iterable[int]] | None = None, *,
                chamber_size: int = 2) -> dict[int, int]:
    """``{well: chamber}``: chamber *i* (from 1) holds the wells of row *i* of
    *chamber_sets* (the two-well default when ``None``); single-well, every
    well is its own chamber."""
    if int(chamber_size) == 1:
        return {w: w for w in range(1, op.N_WELLS + 1)}
    sets = _DEFAULT_CHAMBER_SETS if chamber_sets is None else chamber_sets
    return {int(w): i + 1 for i, row in enumerate(sets) for w in row}


def dfm_chamber_map(dfm: DFM) -> dict[int, int]:
    """``{well: chamber}`` for *dfm*, from its ``params.chamber_sets`` (two-well)
    or the identity (single-well)."""
    params = dfm.params
    if int(params.chamber_size) == 1:
        return chamber_map(chamber_size=1)
    return chamber_map(np.asarray(params.chamber_sets).tolist())


def dfm_linkage_view(dfm: DFM, section: op.DFMProgram | None) -> LinkageView:
    """:func:`linkage_view` for a loaded :class:`~pyflic.base.dfm.DFM`: its
    program *section*, its Paradigm state (generation 3) and the lights its
    ``OptoCol1`` shows."""
    lights = None
    frame = dfm.lights_df
    if frame is not None and len(frame):
        lights = frame[[f"W{w}" for w in range(1, op.N_WELLS + 1)]].to_numpy(dtype=bool)
    return linkage_view(section, dfm.paradigm, lights)
