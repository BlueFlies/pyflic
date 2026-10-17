"""The light table: what each well's light did, in the feeding summary's shape.

Every optogenetic experiment, of any Experiment Type, gets one (decisions 6
and 16 of ``docs/v4-data-plan.md``): ``analysis/light_wells.csv``, one row
per well, and ``analysis/light_summary.csv``, one row per chamber, for every
DFM the optogenetic light QC covers, over the chambers the design assigns a
Treatment (the feeding summary's rows, after auto-removal).  They carry the
feeding summary's Treatment and design-factor columns, so the Combined
Analysis, the reports and the Plot Editor pool and test light behaviour as
they do feeding; :data:`HEADLINE_METRICS` are the columns tested between
treatments by default.

What a row can say depends on the recording's **Generation** (``CONTEXT.md``):

* **Generation 3** reads the firmware's own decisions from
  :attr:`DFM.paradigm <pyflic.base.dfm.DFM.paradigm>`: lit time exact from
  ``OnMs``, Activations, Acclimation (Phase ``A``), Firmware Events and the
  Requirements met under a ratio Paradigm, and the Paradigm, Program
  Interval and Cycle each row was recorded under.
* **Generations 1 and 2** have only ``OptoCol1``, the LEDs sampled once a
  record: ``LitSec`` counts the lit samples (``LitSource`` says which), and
  every firmware column is ``NA``.  ``LightOnsets``, the rising edges of a
  well's own light, is there on every generation: on generation 1 it is the
  nearest thing to an Activation count.  With a program, the Paradigm, its
  type and the Program Interval come from the program's clock schedule
  (approximate, as the generation-1 light QC's windows are).

The Paradigm **type** comes from ``Program.txt``: without the DFM's section
``ParadigmType`` and every type-specific column are ``NA`` (decision 4), and
a type-specific column is ``NA`` wherever the well ran no Paradigm of a type
that defines it:

* Acclimation columns: FixedInterval and the ratio types, with Acclimation;
* ``FirmwareEvents``, ``LastRequirementMet``, ``ProgressAtEnd``,
  ``EventsPerActivation``: the ratio types (ProgressiveRatio, FixedRatio);
* ``LockedOutContactSec``: FixedInterval in Main;
* ``UnlitSec``, ``Suppressions``: NonFeeding.

A window is the feeding summary's: one ``(a, b]`` range of minutes
(``(0, 0)`` the whole recording), or a list of them, as a Program Facet
pooling a Repeating program's Cycles has.  ``Paradigm``, ``ParadigmType``,
``ProgramInterval`` and ``Cycle`` hold the one value of the window, or
``mixed``; the baseline (Program Interval 0) and the rows of an unknown
instruction are left out of them (decision 30).

``Role`` is the chamber's (:mod:`pyflic.base.opto_roles`), except where the
Experiment Type assigns its own (Progressive Ratio's paired / yoked), which
it keeps everywhere.  :func:`with_light_columns` puts ``Role``, ``LitSec``
and ``Activations`` on the feeding summary's rows.
"""

from __future__ import annotations

from typing import Any, Iterable, NamedTuple, Sequence

import numpy as np
import pandas as pd

from . import opto_program as op
from . import windowing
from .paradigm_state import GENERATION_PARADIGM
from .utils import range_bounds, range_is_specified

#: The per-well table, ``analysis/light_wells.csv``.  The design's factor
#: columns follow ``Treatment``, as in the feeding summary.
LIGHT_WELL_COLUMNS: tuple[str, ...] = (
    "DFM", "Well", "Chamber", "Treatment", "Role", "Generation",
    "Paradigm", "ParadigmType", "ProgramInterval", "Cycle", "WindowMinutes",
    "LitSec", "LitFraction", "LitSource", "Activations", "ActivationsPerHour", "LightOnsets",
    "AcclimationActivations", "AcclimationEndMin", "AcclimationComplete",
    "FirmwareEvents", "LastRequirementMet", "ProgressAtEnd", "EventsPerActivation",
    "LockedOutContactSec", "UnlitSec", "Suppressions", "PyflicEvents", "PyflicLicks")

#: The per-chamber table, ``analysis/light_summary.csv``: counts and times
#: summed over the chamber's wells, except ``LitSec`` and ``LightOnsets``,
#: which describe the chamber's own light (lit while any of its wells is),
#: ``AcclimationEndMin`` (the latest) and ``AcclimationComplete`` (all).
LIGHT_CHAMBER_COLUMNS: tuple[str, ...] = (
    "DFM", "Chamber", "Treatment", "Role", "Generation",
    "Paradigm", "ParadigmType", "ProgramInterval", "Cycle", "WindowMinutes",
    "LitSec", "LitFraction", "LitSource", "Activations", "ActivationsPerHour", "LightOnsets",
    "AcclimationActivations", "AcclimationEndMin", "AcclimationComplete",
    "FirmwareEvents", "LastRequirementMet", "ProgressAtEnd", "EventsPerActivation",
    "LockedOutContactSec", "UnlitSec", "Suppressions", "EventsA", "EventsB")

#: The light metrics tested between treatments by default (decision 16).
HEADLINE_METRICS: tuple[str, ...] = ("Activations", "LitSec", "FirmwareEvents",
                                     "AcclimationEndMin")

#: What :func:`with_light_columns` adds to an optogenetic feeding summary.
FEEDING_COLUMNS: tuple[str, ...] = ("Role", "LitSec", "Activations")

#: ``LitSource`` values.
SOURCE_ON_MS, SOURCE_OPTOCOL1 = "OnMs", "OptoCol1"
MIXED = "mixed"

#: Progressive Ratio's own Role words (``experiment_types.progressive_ratio``).
_PR_ROLES = ("paired", "yoked")

_COUNT_COLUMNS = ("Activations", "AcclimationActivations", "FirmwareEvents", "ProgressAtEnd",
                  "LockedOutContactSec", "UnlitSec", "Suppressions")


# ---------------------------------------------------------------------------
# Windows: one (a, b] range of minutes, or several
# ---------------------------------------------------------------------------

def _is_window_list(range_minutes: Any) -> bool:
    """Whether *range_minutes* is a list of ``(a, b)`` windows rather than one."""
    check = getattr(windowing, "is_window_list", None)
    if check is not None:
        return bool(check(range_minutes))
    try:
        first = range_minutes[0]
    except (TypeError, IndexError, KeyError):
        return False
    return isinstance(first, (tuple, list, np.ndarray))


def _row_mask(minutes: np.ndarray, range_minutes: Any) -> np.ndarray | None:
    """Rows of *minutes* inside the window, as the feeding summary selects
    them: ``(a, b]`` per window, an end of 0 open; ``None`` for every row.
    ``windowing.range_mask`` where it exists (stream 5b), else the same rule
    here."""
    shared = getattr(windowing, "range_mask", None)
    if shared is not None:
        return shared(minutes, range_minutes)
    if _is_window_list(range_minutes):
        mask = np.zeros(minutes.size, dtype=bool)
        for window in range_minutes:
            a, b = range_bounds(window)
            mask |= (minutes > a) & (minutes <= b)
        return mask
    if not range_is_specified(range_minutes):
        return None
    a, b = range_bounds(range_minutes)
    return (minutes > a) & (minutes <= b)


def _format_ranges(window: Any) -> str:
    """The ``FacetRange`` cell of one window or several."""
    if not _is_window_list(window):
        return windowing.format_range(window)
    shared = getattr(windowing, "format_ranges", None)
    if shared is not None:
        return shared(window)
    return " + ".join(windowing.format_range(w) for w in window)


class _Window(NamedTuple):
    """The rows of a window: their indices, the contiguous segments they
    form (for the Paradigm state's ``[i0, i1)`` questions), and the row after
    the last."""

    rows: np.ndarray
    segments: list[tuple[int, int]]
    end: int

    @property
    def size(self) -> int:
        return int(self.rows.size)

    def contains(self, at: np.ndarray) -> np.ndarray:
        """Which of the row indices *at* fall inside the window."""
        inside = np.zeros(np.asarray(at).size, dtype=bool)
        for a, b in self.segments:
            inside |= (at >= a) & (at < b)
        return inside


def _window(minutes: np.ndarray, range_minutes: Any) -> _Window:
    mask = _row_mask(minutes, range_minutes)
    rows = np.arange(minutes.size) if mask is None else np.flatnonzero(mask)
    if not rows.size:
        return _Window(rows, [], 0)
    breaks = np.flatnonzero(np.diff(rows) > 1)
    starts = np.concatenate(([rows[0]], rows[breaks + 1]))
    ends = np.concatenate((rows[breaks] + 1, [rows[-1] + 1]))
    return _Window(rows, [(int(a), int(b)) for a, b in zip(starts, ends)], int(rows[-1]) + 1)


# ---------------------------------------------------------------------------
# One DFM, prepared once
# ---------------------------------------------------------------------------

def type_owns_role(exp) -> bool:
    """Whether *exp*'s Experiment Type assigns each chamber its own Role
    (Progressive Ratio's paired / yoked), which the light layer then keeps
    rather than deriving one."""
    return callable(getattr(exp, "role_of", None))


class _DFMLight:
    """What every window of one DFM reads: its light per row and well (and
    the row before's, for onsets), its chambers and their Roles, and on
    generation 3 the Activations counted per row and, with a program, the
    Paradigm type each row ran and which wells ran it.  Built once per DFM
    object and program, and kept on the experiment."""

    def __init__(self, exp, dfm_id: int) -> None:
        dfm = exp.dfms[int(dfm_id)]
        self.dfm = dfm
        self.program = getattr(exp, "opto_program", None)
        self.dfm_id = int(dfm_id)
        self.generation = int(dfm.generation)
        self.sps = float(dfm.params.samples_per_second)
        self.minutes = pd.to_numeric(dfm.raw_df["Minutes"], errors="coerce").to_numpy(float)
        n = self.minutes.size
        state = dfm.paradigm if self.generation == GENERATION_PARADIGM else None
        self.state = state
        self.source = SOURCE_ON_MS if state is not None else SOURCE_OPTOCOL1
        self.steps = None
        if state is not None:
            self.on_ms = np.asarray(state.on_ms)
            self.lit = self.on_ms > 0
            ## Activations counted in each row; row 0's total predates the file.
            counts = np.asarray(state.activations)
            self.steps = np.clip(np.diff(counts, axis=0, prepend=counts[:1]), 0, None) \
                if n else np.zeros((0, op.N_WELLS), dtype=np.int64)
        else:
            self.on_ms = None
            self.lit = np.zeros((n, op.N_WELLS), dtype=bool)
            frame = dfm.lights_df
            if frame is not None:
                for w in range(1, op.N_WELLS + 1):
                    if f"W{w}" in frame.columns:
                        self.lit[:, w - 1] = frame[f"W{w}"].to_numpy()[:n].astype(bool)
        ## Before row 0 is taken as dark: a light on at the first record came on.
        self.lit_before = np.zeros_like(self.lit)
        self.lit_before[1:] = self.lit[:-1]
        self.licks = _matrix(dfm.lick_df, n, bool)
        self.events = _matrix(dfm.event_df, n, np.int64) > 0

        self.chambers = {int(ch.index): ch for ch in (dfm.chambers or [])}
        self.chamber_of = {int(w): c for c, ch in self.chambers.items() for w in ch.wells}
        self.section = (self.program.section(self.dfm_id)
                        if self.program is not None else None)
        if type_owns_role(exp):
            self.roles = {c: str(exp.role_of(self.dfm_id, c).role) for c in self.chambers}
        else:
            from .opto_roles import chamber_roles, dfm_linkage_view

            self.roles = chamber_roles(dfm_linkage_view(dfm, self.section), self.chamber_of)

        self.typed = state is not None and self.section is not None
        if self.typed:
            self._read_types()

    # -- generation 3 with a program ------------------------------------------

    def _read_types(self) -> None:
        """Per row: the Paradigm in force (by the name the row records) and
        its type; per row and well: whether the well ran that Paradigm (a
        level threshold in the row's Program Interval)."""
        state, program = self.state, self.program
        n = len(state)
        names = state.paradigm.to_numpy(dtype=object, na_value=None)
        codes, uniques = pd.factorize(pd.Series(names, dtype=object), use_na_sentinel=True)
        self.names = names
        ## An NA name is code -1, which indexes the trailing None.
        self.codes = np.asarray(codes)
        self.paradigm_by_code = [program.paradigms.get(str(u)) for u in uniques] + [None]
        self.row_type = np.asarray([p.type if p is not None else None
                                    for p in self.paradigm_by_code], dtype=object)[self.codes]
        self._type_masks: dict[tuple, np.ndarray] = {}
        self.trigger = np.zeros((n, op.N_WELLS), dtype=bool)
        fallback = list(self.section.trigger_wells())
        for run in state.interval_runs():
            if run.kind != "program":
                continue
            interval = program.interval_for(self.dfm_id, int(run.program_interval))
            for w in (interval.trigger_wells() if interval is not None else fallback):
                self.trigger[run.i0:run.i1, int(w) - 1] = True

    def type_rows(self, w: int, types: Iterable[str], win: _Window, *,
                  acclimation: bool = False) -> np.ndarray:
        """Per row of *win*: whether well *w* ran a Paradigm of one of *types*
        (with Acclimation, when *acclimation*)."""
        key = (tuple(types), bool(acclimation))
        rows = self._type_masks.get(key)
        if rows is None:
            ## Decided once per Paradigm name, then spread over the rows.
            per_code = [p is not None and p.type in key[0]
                        and (not acclimation or int(p.acclimation or 0) > 0)
                        for p in self.paradigm_by_code]
            rows = self._type_masks[key] = np.asarray(per_code, dtype=bool)[self.codes]
        return rows[win.rows] & self.trigger[win.rows, w - 1]

    def window(self, range_minutes: Any) -> _Window:
        return _window(self.minutes, range_minutes)


def _matrix(frame: pd.DataFrame | None, n: int, dtype) -> np.ndarray:
    out = np.zeros((n, op.N_WELLS), dtype=dtype)
    if frame is None:
        return out
    for w in range(1, op.N_WELLS + 1):
        if f"W{w}" in frame.columns:
            values = pd.to_numeric(frame[f"W{w}"], errors="coerce").fillna(0).to_numpy()
            out[:, w - 1] = values[:n].astype(dtype)
    return out


def _context(exp, dfm_id: int) -> _DFMLight:
    """The DFM's :class:`_DFMLight`, rebuilt when its DFM object or the
    program changed (a QC Viewer recompute swaps in re-detected DFMs)."""
    cache = getattr(exp, "_light_contexts", None)
    if cache is None:
        return _DFMLight(exp, dfm_id)
    entry = cache.get(int(dfm_id))
    if entry is not None and entry.dfm is exp.dfms[int(dfm_id)] \
            and entry.program is getattr(exp, "opto_program", None):
        return entry
    entry = cache[int(dfm_id)] = _DFMLight(exp, dfm_id)
    return entry


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _single(values: Iterable[Any]) -> Any:
    """The one distinct value, :data:`MIXED` for several, ``None`` for none."""
    seen = list(dict.fromkeys(v for v in values if v is not None))
    if not seen:
        return None
    return seen[0] if len(seen) == 1 else MIXED


def _sum(values: Iterable[Any]) -> float:
    """Sum of the values that are there; NaN when none is."""
    present = [float(v) for v in values if v is not None and not pd.isna(v)]
    return float(sum(present)) if present else np.nan


def _per_hour(count: float, minutes: float) -> float:
    if pd.isna(count) or not minutes > 0:
        return np.nan
    return float(count) / (float(minutes) / 60.0)


def _fraction(seconds: float, minutes: float) -> float:
    if pd.isna(seconds) or not minutes > 0:
        return np.nan
    return float(seconds) / (float(minutes) * 60.0)


# ---------------------------------------------------------------------------
# What a window was recorded under
# ---------------------------------------------------------------------------

def _window_paradigm(ctx: _DFMLight, win: _Window) -> dict[str, Any]:
    """``Paradigm``, ``ParadigmType``, ``ProgramInterval`` and ``Cycle`` of
    the window: one value, ``mixed`` or ``None``."""
    out: dict[str, Any] = {"Paradigm": None, "ParadigmType": None,
                           "ProgramInterval": None, "Cycle": None}
    state = ctx.state
    if state is None:
        return _scheduled_paradigm(ctx, win, out)
    if not win.size:
        return out
    interval = state.program_interval.to_numpy(dtype=np.int64, na_value=-1)[win.rows]
    program = interval > 0
    if not program.any():
        return out
    rows = win.rows[program]
    names = state.paradigm.to_numpy(dtype=object, na_value=None)[rows]
    cycles = state.cycle.to_numpy(dtype=np.int64, na_value=-1)[rows]
    out["Paradigm"] = _single(str(v) for v in names if v is not None)
    out["ProgramInterval"] = _single(int(v) for v in interval[program])
    out["Cycle"] = _single(int(v) for v in cycles if v >= 0)
    if ctx.typed:
        out["ParadigmType"] = _single(op.TYPE_NAMES.get(t, t) for t in ctx.row_type[rows]
                                      if t is not None)
    return out


def _scheduled_paradigm(ctx: _DFMLight, win: _Window, out: dict) -> dict:
    """Generations 1 and 2: the Program Intervals the program's clock
    schedule puts in the window's minutes (the light QC's own windows on
    these generations), when there is a section and the file has dates."""
    program, section = ctx.program, ctx.section
    if section is None or not win.size or program.start is None:
        return out
    from datetime import timedelta

    from .opto_light import recording_origin

    origin = recording_origin(ctx.dfm.raw_df)
    end = program.resolved_end()
    if origin is None or end is None:
        return out
    schedule = section.schedule(program.start, end)
    hits = []
    for a, b in win.segments:
        t0 = origin + timedelta(minutes=float(ctx.minutes[a]))
        t1 = origin + timedelta(minutes=float(ctx.minutes[b - 1]))
        hits += [s for s in schedule if s.start <= t1 and s.end > t0]
    if not hits:
        return out
    out["Paradigm"] = _single(s.interval.paradigm.name for s in hits)
    out["ParadigmType"] = _single(s.interval.paradigm.type_name for s in hits)
    out["ProgramInterval"] = _single(int(s.interval.index) for s in hits)
    out["Cycle"] = _single(int(s.occurrence) for s in hits)
    return out


# ---------------------------------------------------------------------------
# One well over one window
# ---------------------------------------------------------------------------

def _well_values(ctx: _DFMLight, w: int, win: _Window) -> dict[str, Any]:
    """Every metric of :data:`LIGHT_WELL_COLUMNS` for well *w* over *win*,
    plus ``_Main`` (its Main ratio Activations) for the chamber's
    EventsPerActivation."""
    col, rows = w - 1, win.rows
    minutes = win.size / ctx.sps / 60.0
    lit = ctx.lit[rows, col]
    if ctx.on_ms is not None:
        lit_sec = float(ctx.on_ms[rows, col].sum()) / 1000.0
    else:
        lit_sec = float(np.count_nonzero(lit)) / ctx.sps
    out: dict[str, Any] = {
        "WindowMinutes": minutes, "LitSec": lit_sec,
        "LitFraction": _fraction(lit_sec, minutes), "LitSource": ctx.source,
        "LightOnsets": float(np.count_nonzero(lit & ~ctx.lit_before[rows, col])),
        "PyflicEvents": float(np.count_nonzero(ctx.events[rows, col])),
        "PyflicLicks": float(np.count_nonzero(ctx.licks[rows, col])),
        "Activations": np.nan, "ActivationsPerHour": np.nan,
        "AcclimationActivations": np.nan, "AcclimationEndMin": np.nan,
        "AcclimationComplete": None, "FirmwareEvents": np.nan,
        "LastRequirementMet": np.nan, "ProgressAtEnd": np.nan,
        "EventsPerActivation": np.nan, "LockedOutContactSec": np.nan,
        "UnlitSec": np.nan, "Suppressions": np.nan, "_Main": np.nan,
    }
    state = ctx.state
    if state is None or not win.size:
        return out
    activations = float(ctx.steps[rows, col].sum())
    out["Activations"] = activations
    out["ActivationsPerHour"] = _per_hour(activations, minutes)
    if not ctx.typed:
        return out
    out.update(_acclimation(ctx, w, win))
    out.update(_ratio(ctx, w, win))
    fixed = ctx.type_rows(w, (op.FIXED_INTERVAL,), win)
    if fixed.any():
        main = fixed & ~state.phase_a[rows, col]
        locked = main & ctx.licks[rows, col] & (ctx.on_ms[rows, col] == 0)
        out["LockedOutContactSec"] = float(np.count_nonzero(locked)) / ctx.sps
    nonfeeding = ctx.type_rows(w, (op.NON_FEEDING,), win)
    if nonfeeding.any():
        on_ms = ctx.on_ms[rows, col]
        out["UnlitSec"] = max(0.0, float(np.count_nonzero(nonfeeding)) / ctx.sps
                              - float(on_ms[nonfeeding].sum()) / 1000.0)
        went_dark = nonfeeding & ctx.lit_before[rows, col] & ~lit
        out["Suppressions"] = float(np.count_nonzero(went_dark))
    return out


def _acclimation(ctx: _DFMLight, w: int, win: _Window) -> dict[str, Any]:
    """The Acclimation columns: defined where the well ran a FixedInterval or
    ratio Paradigm with Acclimation in the window.  The end is the first row
    in Main after the window's first run in Phase ``A``; a well still in
    ``A`` when the window ends has none and is not complete."""
    if not ctx.type_rows(w, op.ACCLIMATION_PARADIGMS, win, acclimation=True).any():
        return {}
    state, col = ctx.state, w - 1
    runs = [(a, b) for a, b in state.acclimation_runs(w)
            if any(a < sb and b > sa for sa, sb in win.segments)]
    if not runs:
        return {"AcclimationActivations": 0.0}
    count = 0.0
    for a, b in runs:
        for sa, sb in win.segments:
            lo, hi = max(a, sa), min(b, sb)
            if lo < hi:
                count += float(ctx.steps[lo:hi, col].sum())

    def ended(end: int) -> bool:
        return end < win.end and end < len(state)

    first_end = runs[0][1]
    return {
        "AcclimationActivations": count,
        "AcclimationEndMin": float(state.minutes[first_end]) if ended(first_end) else np.nan,
        "AcclimationComplete": ended(runs[-1][1]),
    }


def _ratio(ctx: _DFMLight, w: int, win: _Window) -> dict[str, Any]:
    """The ratio columns: defined where the well ran ProgressiveRatio or
    FixedRatio in the window."""
    if not ctx.type_rows(w, op.RATIO_PARADIGMS, win).any():
        return {}
    state, col, rows = ctx.state, w - 1, win.rows
    events = float(sum(state.firmware_events_between(w, a, b) for a, b in win.segments))
    shown = ~np.isnan(state.requirement[rows, col])
    main = float(ctx.steps[rows, col][shown & ~state.phase_a[rows, col]].sum())
    last = np.flatnonzero(shown)
    progress = (float(np.nan_to_num(state.progress[rows[last[-1]], col], nan=0.0))
                if last.size else np.nan)
    return {
        "FirmwareEvents": events,
        "LastRequirementMet": _last_requirement(ctx, w, win),
        "ProgressAtEnd": progress,
        "EventsPerActivation": events / main if main > 0 else np.nan,
        "_Main": main,
    }


def _last_requirement(ctx: _DFMLight, w: int, win: _Window) -> float:
    """The Requirement the window's last Main ratio Activation met.  An
    Activation on the first row of a Paradigm (no row before shows its
    Requirement) met the Paradigm's first one."""
    state, col = ctx.state, w - 1
    onsets = state.activation_onsets(w)
    for r in onsets[win.contains(onsets)][::-1]:
        met = state.requirement_met(w, int(r))
        if met is not None:
            return float(met)
        starts = r > 0 and ctx.names[r] != ctx.names[r - 1]
        paradigm = ctx.paradigm_by_code[ctx.codes[r]]
        if starts and paradigm is not None and paradigm.type in op.RATIO_PARADIGMS \
                and not state.phase_a[r, col] and ctx.trigger[r, col]:
            first = paradigm.requirement_for(1)
            if first is not None:
                return float(first)
    return np.nan


# ---------------------------------------------------------------------------
# A chamber over one window
# ---------------------------------------------------------------------------

def _chamber_light(ctx: _DFMLight, wells: Sequence[int], win: _Window) -> tuple[float, int]:
    """``(LitSec, LightOnsets)`` of the chamber's own light: lit while any of
    its wells is; on generation 3 the per-record maximum of their ``OnMs``,
    since linked wells share one light and a sum would count it twice."""
    cols = [int(w) - 1 for w in wells]
    if not cols or not win.size:
        return 0.0, 0
    lit = ctx.lit[win.rows][:, cols].any(axis=1)
    before = ctx.lit_before[win.rows][:, cols].any(axis=1)
    if ctx.on_ms is not None:
        seconds = float(ctx.on_ms[win.rows][:, cols].max(axis=1).sum()) / 1000.0
    else:
        seconds = float(np.count_nonzero(lit)) / ctx.sps
    return seconds, int(np.count_nonzero(lit & ~before))


def _chamber_values(ctx: _DFMLight, chamber: int, wells: dict[int, dict],
                    win: _Window) -> dict[str, Any]:
    ch = ctx.chambers[chamber]
    values = list(wells.values())
    minutes = win.size / ctx.sps / 60.0
    lit_sec, onsets = _chamber_light(ctx, list(wells), win)
    out: dict[str, Any] = {"WindowMinutes": minutes, "LitSec": lit_sec,
                           "LitFraction": _fraction(lit_sec, minutes),
                           "LitSource": ctx.source, "LightOnsets": float(onsets)}
    for column in _COUNT_COLUMNS:
        out[column] = _sum(v[column] for v in values)
    out["ActivationsPerHour"] = _per_hour(out["Activations"], minutes)
    acclimated = [v for v in values if v["AcclimationComplete"] is not None]
    if acclimated:
        complete = all(bool(v["AcclimationComplete"]) for v in acclimated)
        ends = [v["AcclimationEndMin"] for v in acclimated]
        out["AcclimationComplete"] = complete
        out["AcclimationEndMin"] = (max(float(e) for e in ends)
                                    if complete and all(pd.notna(e) for e in ends) else np.nan)
    else:
        out["AcclimationComplete"] = None
        out["AcclimationEndMin"] = np.nan
    met = [float(v["LastRequirementMet"]) for v in values if pd.notna(v["LastRequirementMet"])]
    out["LastRequirementMet"] = max(met) if met else np.nan
    main = _sum(v["_Main"] for v in values)
    out["EventsPerActivation"] = (out["FirmwareEvents"] / main
                                  if pd.notna(out["FirmwareEvents"]) and pd.notna(main)
                                  and main > 0 else np.nan)
    well_a = getattr(ch, "well_a", None)
    if well_a is not None:
        out["EventsA"] = wells[int(well_a)]["PyflicEvents"]
        out["EventsB"] = wells[int(ch.well_b)]["PyflicEvents"]
    else:
        out["EventsA"] = values[0]["PyflicEvents"] if values else np.nan
        out["EventsB"] = np.nan
    return out


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

def _rows(exp, dfm_id: int, range_minutes: Any,
          chambers: Iterable[int] | None = None) -> tuple[list[dict], list[dict]]:
    """``(well rows, chamber rows)`` of one DFM over one window, for the
    chambers the design assigns a Treatment (of *chambers*, when given)."""
    ctx = _context(exp, dfm_id)
    win = ctx.window(range_minutes)
    wanted = None if chambers is None else {int(c) for c in chambers}
    head = {"Generation": ctx.generation, **_window_paradigm(ctx, win)}
    well_rows: list[dict] = []
    chamber_rows: list[dict] = []
    for chamber in sorted(ctx.chambers):
        if wanted is not None and chamber not in wanted:
            continue
        treatment = exp.design.treatment_for(ctx.dfm_id, chamber)
        if treatment is None:
            continue
        ident = {"DFM": ctx.dfm_id, "Chamber": chamber, "Treatment": treatment,
                 "Role": ctx.roles.get(chamber, "")}
        wells = {int(w): _well_values(ctx, int(w), win)
                 for w in sorted(ctx.chambers[chamber].wells)}
        for w, values in wells.items():
            well_rows.append({**ident, "Well": w, **head, **values})
        chamber_rows.append({**ident, **head, **_chamber_values(ctx, chamber, wells, win)})
    return well_rows, chamber_rows


def _frame(exp, rows: list[dict], columns: Sequence[str], lead: Sequence[str] = ()) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=[*lead, *columns]) if rows else \
        pd.DataFrame(columns=[*lead, *columns])
    for column in ("ProgramInterval", "Cycle", "Paradigm", "ParadigmType", "AcclimationComplete"):
        df[column] = df[column].astype(object).where(df[column].notna(), None)
    if df.empty:
        return df
    return exp._append_factor_columns(df) if hasattr(exp, "_append_factor_columns") else df


def _dfm_ids(exp) -> list[int]:
    return list(exp.opto.dfm_ids()) if getattr(exp, "is_optogenetic", False) else []


def light_wells(exp, *, range_minutes: Any = (0, 0)) -> pd.DataFrame:
    """One row per well of every assigned chamber of every DFM the
    optogenetic light QC covers, over *range_minutes* (the feeding summary's
    ``(a, b]``, or a list of them; ``(0, 0)``: the whole recording).
    Columns :data:`LIGHT_WELL_COLUMNS`, the design's factors after
    ``Treatment``."""
    rows = [r for d in _dfm_ids(exp) for r in _rows(exp, d, range_minutes)[0]]
    return _frame(exp, rows, LIGHT_WELL_COLUMNS)


def light_summary(exp, *, range_minutes: Any = (0, 0)) -> pd.DataFrame:
    """One row per assigned chamber of every DFM the optogenetic light QC
    covers (:data:`LIGHT_CHAMBER_COLUMNS`), over *range_minutes*."""
    rows = [r for d in _dfm_ids(exp) for r in _rows(exp, d, range_minutes)[1]]
    return _frame(exp, rows, LIGHT_CHAMBER_COLUMNS)


def facet_windows(exp, dfm_id: int) -> list[tuple[str, Any, list[int] | None]]:
    """``[(label, range_minutes, chambers or None), ...]``: the Facets one DFM
    is split by, each window as the feeding summary takes it.

    * Progressive Ratio: each Chamber Group's own (:meth:`group_windows`);
    * the experiment's per-DFM Facets (``facet_windows_for``, Program
      Facets), when it has them: each a label and one or more windows, the
      list passed through;
    * else the shared ``facet_cutoffs`` windows.
    """
    group_windows = getattr(exp, "group_windows", None)
    if callable(group_windows) and type_owns_role(exp):
        groups: dict[int, list[int]] = {}
        for ch in exp.dfms[int(dfm_id)].chambers or []:
            groups.setdefault(int(exp.role_of(dfm_id, int(ch.index)).group), []).append(
                int(ch.index))
        return [(label, window, chambers) for group, chambers in groups.items()
                for label, window in group_windows(dfm_id, group)]
    per_dfm = getattr(exp, "facet_windows_for", None)
    if callable(per_dfm):
        return [(label, windows, None) for label, windows in per_dfm(dfm_id)]
    return [(label, window, None)
            for label, window in zip(exp.facet_labels(), exp.facet_windows())]


def _as_range(window: Any) -> Any:
    """A Facet window as ``range_minutes``: one ``(a, b)`` through
    :func:`windowing.as_range_minutes`, a list as it is."""
    return window if _is_window_list(window) else windowing.as_range_minutes(window)


def _facet_tables(exp) -> tuple[pd.DataFrame, pd.DataFrame]:
    wells: list[dict] = []
    chambers: list[dict] = []
    for dfm_id in _dfm_ids(exp):
        for label, window, which in facet_windows(exp, dfm_id):
            lead = {"Facet": label, "FacetRange": _format_ranges(window)}
            w_rows, c_rows = _rows(exp, dfm_id, _as_range(window), which)
            wells += [{**lead, **r} for r in w_rows]
            chambers += [{**lead, **r} for r in c_rows]
    lead = ("Facet", "FacetRange")
    out = []
    for rows, columns, keys in ((wells, LIGHT_WELL_COLUMNS, ["DFM", "Chamber", "Well"]),
                                (chambers, LIGHT_CHAMBER_COLUMNS, ["DFM", "Chamber"])):
        df = _frame(exp, rows, columns, lead)
        if not df.empty:
            labels = list(dict.fromkeys([*map(str, exp.facet_labels()),
                                         *df["Facet"].astype(str)]))
            df["_o"] = df["Facet"].astype(str).map({l: i for i, l in enumerate(labels)})
            df = df.sort_values(["_o", *keys], kind="stable").drop(columns="_o")
            df = df.reset_index(drop=True)
        out.append(df)
    return out[0], out[1]


def light_wells_facet(exp) -> pd.DataFrame:
    """:func:`light_wells` once per Facet, stacked, led by ``Facet`` and
    ``FacetRange`` as :meth:`Experiment.feeding_summary_facet` is; empty when
    the experiment is not faceted."""
    return _facet_tables(exp)[0]


def light_summary_facet(exp) -> pd.DataFrame:
    """:func:`light_summary` once per Facet, stacked (see
    :func:`light_wells_facet`)."""
    return _facet_tables(exp)[1]


#: ``analysis/`` file names of the four tables, keyed as basic analysis
#: returns them.
FILES: dict[str, str] = {
    "light_wells": "light_wells.csv",
    "light_summary": "light_summary.csv",
    "light_wells_facet": "light_wells_facet.csv",
    "light_summary_facet": "light_summary_facet.csv",
}


def write(exp, out_dir=None, *, range_minutes: Any = (0, 0)) -> dict:
    """Write the light tables into ``analysis/`` and return their paths.
    The ``_facet`` files are written only for a faceted experiment, as
    ``feeding_summary_facet.csv`` is: an absent file means "no Facets"."""
    from pathlib import Path

    if out_dir is None:
        if exp.analysis_dir is None:
            raise ValueError("experiment_dir must be set to write the light tables.")
        out_dir = exp.analysis_dir
    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    wells_facet, summary_facet = _facet_tables(exp)
    tables = {
        "light_wells": light_wells(exp, range_minutes=range_minutes),
        "light_summary": light_summary(exp, range_minutes=range_minutes),
        "light_wells_facet": wells_facet,
        "light_summary_facet": summary_facet,
    }
    written: dict = {}
    for key, frame in tables.items():
        if key.endswith("_facet") and frame.empty:
            continue
        path = out / FILES[key]
        frame.to_csv(path, index=False, na_rep="NA")
        written[key] = path
    return written


# ---------------------------------------------------------------------------
# The feeding summary's light columns
# ---------------------------------------------------------------------------

def with_light_columns(exp, df: pd.DataFrame, range_minutes: Any = (0, 0)) -> pd.DataFrame:
    """*df* (per-chamber feeding-summary rows over *range_minutes*, one
    ``(a, b]`` window or a list) with ``Role`` after ``Chamber`` and
    ``LitSec`` and ``Activations`` after the ``OptoOn_sec`` columns, on an
    optogenetic experiment.

    Redone on every call, as the light QC's columns are: a summary read back
    from the disk cache carries whatever they said when it was written.  A
    ``Role`` the Experiment Type writes (Progressive Ratio) is never touched;
    rows of a DFM the light QC does not cover get an empty Role and NaN.
    """
    if df is None or df.empty or "DFM" not in df.columns or "Chamber" not in df.columns:
        return df
    owns_role = type_owns_role(exp)
    stale = [c for c in FEEDING_COLUMNS if c in df.columns and not (c == "Role" and owns_role)]
    if stale:
        df = df.drop(columns=stale)
    if not getattr(exp, "is_optogenetic", False):
        return df
    covered = set(exp.opto.dfm_ids())
    keys = list(zip(pd.to_numeric(df["DFM"]).astype(int), pd.to_numeric(df["Chamber"]).astype(int)))
    found: dict[tuple[int, int], tuple[str, float, float]] = {}
    for dfm_id in sorted({d for d, _c in keys if d in covered and d in exp.dfms}):
        ctx = _context(exp, dfm_id)
        win = ctx.window(range_minutes)
        for chamber, ch in ctx.chambers.items():
            cols = [int(w) - 1 for w in ch.wells]
            lit_sec, _onsets = _chamber_light(ctx, ch.wells, win)
            activations = (float(ctx.steps[win.rows][:, cols].sum())
                           if ctx.steps is not None else np.nan)
            found[(dfm_id, chamber)] = (ctx.roles.get(chamber, ""), lit_sec, activations)
    df = df.copy()
    if not owns_role:
        df.insert(list(df.columns).index("Chamber") + 1, "Role",
                  [found[k][0] if k in found else "" for k in keys])
    anchor = [i for i, c in enumerate(df.columns) if str(c).startswith("OptoOn_sec")]
    at = (anchor[-1] + 1) if anchor else len(df.columns)
    df.insert(at, "LitSec", [found[k][1] if k in found else np.nan for k in keys])
    df.insert(at + 1, "Activations", [found[k][2] if k in found else np.nan for k in keys])
    return df


# ---------------------------------------------------------------------------
# For the reports
# ---------------------------------------------------------------------------

def behaviour_rows(frame: pd.DataFrame | None) -> pd.DataFrame | None:
    """The rows whose light is their own, for comparing light behaviour
    between treatments.  A Progressive Ratio yoked fly's light is its
    partner's (its Activations are 0 by construction and its lit time a
    copy), so a table carrying that type's ``paired`` / ``yoked`` Role keeps
    the paired rows; every other table is kept whole."""
    if frame is None or frame.empty or "Role" not in frame.columns:
        return frame
    roles = frame["Role"].fillna("").astype(str).str.strip()
    known = set(roles[roles != ""])
    if known and known <= set(_PR_ROLES):
        return frame[roles == "paired"]
    return frame


def has_generation_2(frame: pd.DataFrame | None) -> bool:
    """Whether a saved light table has any generation-2 row."""
    if frame is None or frame.empty or "Generation" not in frame.columns:
        return False
    return bool((pd.to_numeric(frame["Generation"], errors="coerce") == 2).any())


#: What a member recorded from a DFM whose firmware predates 4.0.0 (generation
#: 2) says wherever its Training would show (decision 15).
NO_TRAINING_INFORMATION = "no training information (firmware older than 4.0.0)"


def no_training_information(exp) -> bool:
    """Whether a loaded experiment has a DFM without Training information.

    The Experiment Type is asked first when it can answer
    (``training_information()``, Progressive Ratio): a text answer of
    ``"none"`` or one starting "no training information" means none.
    Otherwise, any DFM recorded as generation 2 (``training_info ==
    "none"``)."""
    ask = getattr(exp, "training_information", None)
    if callable(ask):
        try:
            answer = ask()
        except Exception:  # noqa: BLE001 - a status line must not fail
            answer = None
        if isinstance(answer, str):
            text = answer.strip().lower()
            return text == "none" or text.startswith("no training information")
    dfms = getattr(exp, "dfms", None) or {}
    return any(getattr(d, "training_info", None) == "none" for d in dfms.values())
