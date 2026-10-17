"""Program Facets: an experiment's Facets taken from its Opto Program.

Decision 7 of ``docs/v4-data-plan.md``.  The Design key ``facet_source`` says
where the Facets come from:

* ``cutoffs`` (the default) — ``facet_cutoffs``, the same minute windows on
  every DFM (ADR-0008);
* ``program`` — one Facet per **Program Interval** of each DFM's program, its
  **Cycles** pooled, so a Facet of a Repeating program is several disjoint
  windows;
* ``program_cycles`` — one Facet per Program Interval and Cycle.

A Facet is labelled by its Paradigm's name, prefixed ``I<k> `` only when some
DFM runs that name in two Program Intervals (``I1 Open``, ``I2 Open``), with
`` C<n>`` added for ``program_cycles``.  The label depends on the name and
the Interval alone, never on the DFM, so pooling a Facet across DFMs (or
across the Members of a Project) pools chambers that ran the same Paradigm.

Generation 3 records which Program Interval and Cycle each row ran under
(``ParadigmState.interval_runs``); the baseline and rows under an unknown
instruction belong to no Facet (decision 30).  Generations 1 and 2 record
nothing of the kind, so their Facets come from the program's clock schedule,
laid out as the optogenetic light QC lays it out, and are noted as
approximate.  Either way a program section is required for every DFM: a
``facet_source`` of ``program`` without one is a load and a lint error.

The Progressive Ratio type owns its Facets (Training / Test per Chamber
Group, ADR-0013) and so owns ``facet_source``, as it owns ``facet_cutoffs``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

import numpy as np

#: The Design key.
FACET_SOURCE_KEY = "facet_source"
SOURCE_CUTOFFS = "cutoffs"
SOURCE_PROGRAM = "program"
SOURCE_PROGRAM_CYCLES = "program_cycles"
FACET_SOURCES: tuple[str, ...] = (SOURCE_CUTOFFS, SOURCE_PROGRAM, SOURCE_PROGRAM_CYCLES)
#: How each source reads in the editors' pickers and on the report cover.
SOURCE_LABELS: dict[str, str] = {
    SOURCE_CUTOFFS: "minute cutoffs (facet_cutoffs)",
    SOURCE_PROGRAM: "Program Intervals, Cycles pooled",
    SOURCE_PROGRAM_CYCLES: "Program Intervals and Cycles",
}
#: ``summary.txt``'s note for a DFM whose Program Facets come from the clock.
CLOCK_SCHEDULE_NOTE = "Program Facets from the clock schedule: approximate"


def normalize_source(value: Any) -> str:
    """*value* as one of :data:`FACET_SOURCES`; unset is ``cutoffs``.
    Raises ``ValueError`` for anything else."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return SOURCE_CUTOFFS
    text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if text not in FACET_SOURCES:
        raise ValueError(f"{value!r} is not a facet source")
    return text


def source_problem(value: Any, *, where: str = FACET_SOURCE_KEY) -> str | None:
    """Why *value* is not a ``facet_source``, or ``None``."""
    try:
        normalize_source(value)
    except ValueError:
        return (f"{where} is {value!r}; it must be one of "
                f"{', '.join(FACET_SOURCES)}")
    return None


def is_program_source(source: str | None) -> bool:
    """Whether *source* takes the Facets from the Opto Program."""
    return source in (SOURCE_PROGRAM, SOURCE_PROGRAM_CYCLES)


def program_problems(source: str, program, dfm_ids: Iterable[int], *,
                     program_error: str | None = None) -> list[str]:
    """Why Program Facets cannot be laid out for *dfm_ids* from *program* (an
    :class:`~pyflic.base.opto_program.OptoProgram` or ``None``): every DFM
    needs its own ``Program.txt`` section.  Empty for ``cutoffs``."""
    if not is_program_source(source):
        return []
    head = f"facet_source: {source} takes the Facets from data/Program.txt"
    if program is None:
        why = (f"which could not be used ({program_error})" if program_error
               else "and there is none")
        return [f"{head}, {why}"]
    missing = sorted(int(d) for d in dfm_ids if program.section(int(d)) is None)
    if missing:
        return [f"{head}, which has no section for DFM(s) "
                f"{', '.join(str(d) for d in missing)}"]
    return []


# ---------------------------------------------------------------------------
# One DFM's Program Interval runs
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ProgramRun:
    """Rows ``[i0, i1)`` of one DFM recorded under one Program Interval in
    one Cycle."""

    program_interval: int
    cycle: int | None
    paradigm: str
    i0: int
    i1: int


def _paradigm_name(program, dfm_id: int, k: int, recorded: str | None) -> str:
    """The name the data recorded, else the program's, else a placeholder."""
    if recorded:
        return str(recorded)
    interval = program.interval_for(dfm_id, k) if program is not None else None
    if interval is not None:
        return interval.paradigm.name
    return f"Interval {k}"


def recorded_runs(dfm, program=None) -> list[ProgramRun]:
    """Generation 3: the DFM's own record of its Program Intervals, without
    the baseline and the rows under an unknown instruction."""
    runs: list[ProgramRun] = []
    for run in dfm.paradigm.interval_runs():
        if run.kind != "program" or run.program_interval is None or run.i1 <= run.i0:
            continue
        k = int(run.program_interval)
        runs.append(ProgramRun(k, run.cycle, _paradigm_name(program, int(dfm.id), k,
                                                            run.paradigm),
                               int(run.i0), int(run.i1)))
    return runs


def clock_runs(dfm, program) -> list[ProgramRun]:
    """Generations 1 and 2: the program's Intervals laid out by clock time
    from its start, as the optogenetic light QC lays them out
    (``opto_qc._program_windows``): the rows from each scheduled start to
    its end, an Interval's later passes as Cycles 2, 3, …"""
    from .opto_light import recording_origin

    section = program.section(int(dfm.id)) if program is not None else None
    minutes = np.asarray(dfm.raw_df["Minutes"], dtype=float)
    if section is None or minutes.size == 0:
        return []
    origin = recording_origin(dfm.raw_df) or program.start or datetime(2000, 1, 1)
    anchor = program.start or origin
    data_end = origin + timedelta(minutes=float(minutes[-1]),
                                  seconds=1.0 / float(dfm.params.samples_per_second))
    end = program.resolved_end() or data_end
    runs: list[ProgramRun] = []
    for sched in section.schedule(anchor, end):
        a = (sched.start - origin).total_seconds() / 60.0
        b = (sched.end - origin).total_seconds() / 60.0
        i0 = int(np.searchsorted(minutes, a, side="left"))
        i1 = int(np.searchsorted(minutes, b, side="left"))
        if i1 > i0:
            runs.append(ProgramRun(int(sched.interval.index), int(sched.occurrence),
                                   sched.interval.paradigm.name, i0, i1))
    return runs


def rows_window(minutes: np.ndarray, i0: int, i1: int, record_min: float) -> tuple[float, float]:
    """Rows ``[i0, i1)`` as the ``(a, b]`` minute window that selects exactly
    them: from the previous row's minute to the last row's."""
    a = float(minutes[i0 - 1]) if i0 > 0 else float(minutes[0]) - float(record_min)
    return a, float(minutes[i1 - 1])


# ---------------------------------------------------------------------------
# Every DFM's Facets, labelled once for all of them
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FacetPlan:
    """The Program Facets of one experiment."""

    source: str
    #: The ordered union of every DFM's labels.
    labels: list[str]
    #: DFM -> ``[(label, [(a, b), ...]), ...]`` in the order its Facets began.
    windows: dict[int, list[tuple[str, list[tuple[float, float]]]]]
    #: DFMs whose Facets come from the clock schedule (generations 1 and 2).
    clock_dfms: tuple[int, ...] = ()
    #: Per DFM, the runs the windows were made from.
    runs: dict[int, list[ProgramRun]] = field(default_factory=dict)


def _merge(windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Windows in time order with touching ones joined: the Cycles of a
    one-Interval Repeating program run back to back."""
    out: list[tuple[float, float]] = []
    for a, b in sorted(windows):
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def plan(dfms: Mapping[int, Any], program, source: str) -> FacetPlan:
    """The Program Facets of *dfms* under *source* (``program`` or
    ``program_cycles``).  A DFM without a program section has none."""
    from .paradigm_state import GENERATION_PARADIGM

    runs: dict[int, list[ProgramRun]] = {}
    clock: list[int] = []
    minutes: dict[int, np.ndarray] = {}
    record_min: dict[int, float] = {}
    for dfm_id in sorted(int(d) for d in dfms):
        dfm = dfms[dfm_id]
        minutes[dfm_id] = np.asarray(dfm.raw_df["Minutes"], dtype=float)
        record_min[dfm_id] = 1.0 / (60.0 * float(dfm.params.samples_per_second))
        if program is None or program.section(dfm_id) is None:
            runs[dfm_id] = []
        elif getattr(dfm, "generation", None) == GENERATION_PARADIGM \
                and getattr(dfm, "paradigm", None) is not None:
            runs[dfm_id] = recorded_runs(dfm, program)
        else:
            runs[dfm_id] = clock_runs(dfm, program)
            clock.append(dfm_id)

    ## A name some DFM runs in two Program Intervals is told apart by its
    ## Interval on every DFM, so one name keeps one label everywhere.
    repeated: set[str] = set()
    for dfm_runs in runs.values():
        intervals: dict[str, set[int]] = {}
        for run in dfm_runs:
            intervals.setdefault(run.paradigm, set()).add(run.program_interval)
        repeated |= {name for name, ks in intervals.items() if len(ks) > 1}

    def label(run: ProgramRun) -> str:
        base = (f"I{run.program_interval} {run.paradigm}" if run.paradigm in repeated
                else run.paradigm)
        if source == SOURCE_PROGRAM_CYCLES:
            return f"{base} C{run.cycle if run.cycle is not None else 1}"
        return base

    labels: list[str] = []
    windows: dict[int, list[tuple[str, list[tuple[float, float]]]]] = {}
    for dfm_id, dfm_runs in runs.items():
        by_label: dict[str, list[tuple[float, float]]] = {}
        for run in dfm_runs:
            by_label.setdefault(label(run), []).append(
                rows_window(minutes[dfm_id], run.i0, run.i1, record_min[dfm_id]))
        windows[dfm_id] = [(name, _merge(ws)) for name, ws in by_label.items()]
        for name in by_label:
            if name not in labels:
                labels.append(name)
    return FacetPlan(source=source, labels=labels, windows=windows,
                     clock_dfms=tuple(clock), runs=runs)
