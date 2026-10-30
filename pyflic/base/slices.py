"""Slices: a separate analysis of part of a recording (ADR-0020).

A **Slice** is a named part of a recording, from a start minute to an end
minute or to the end of the recording, analysed as if the recording were only
that part.  The rows outside it are dropped at load, before baselining,
thresholds, event detection and auto-removal, so a well that fails at hour 10
cannot touch a Slice that ends at hour 6.  Each Slice has its own exclusion
groups (none inherited from the whole recording), may override the cutoffs
that drive auto-removal, and writes its own QC and results under
``slices/<name>/``.

The Design declares the Slices under ``global.slices:``, so every Member runs
every Slice its recording **covers** — reaches the Slice's end, within
``slice_tolerance_min`` — and a Slice's Combined Analysis pools those Members
alone.  The whole recording is the implicit Slice every experiment has: it is
not declared, and its outputs stay in ``analysis/`` and ``qc/``.

Facets still split each Slice: every Facet window is intersected with the
Slice, and one left empty is dropped.  A type whose Facets come from the data
(the Ratio analysis: Progressive Ratio and Fixed Ratio) has no Slices — its
Training/Test split sits at each group's own training end, which a Slice
could clip away.

Declared in ``global:`` (in ``project.yaml``'s design for a Member)::

    exclusion_group: general        # the whole recording's own group
    also_exclude: [dead]            # groups it also excludes, never writes
    slice_tolerance_min: 5
    slices:
      early:
        start: 0
        end: 360
        exclusion_group: early      # defaults to the Slice's name
        also_exclude: [dead]
        constants: {min_untransformed_licks_cutoff: 20}
      late:
        start: 360
        end: end                    # to the end of the recording
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

#: Where a Slice's outputs live, under an Experiment Directory or a Project.
DIRNAME = "slices"
#: The record a run writes into ``slices/<name>/``: the definition it ran
#: with, and whether the recording covered it.
RECORD_FILENAME = "slice.json"
#: How far short of a Slice's end a recording may stop and still cover it.
#: A nominal 24-hour run often ends at minute 1439.8, not 1440.
DEFAULT_TOLERANCE_MIN = 5.0
#: The ``end:`` spellings that mean "to the end of the recording".
OPEN_END_WORDS = frozenset({"end", "open", "inf", "infinity", ""})
#: The only ``constants:`` a Slice may override: the ones that decide which
#: chambers auto-removal takes out.  Detection settings stay project-wide, so
#: a Slice is the same analysis of fewer minutes.
AUTO_REMOVAL_CONSTANTS = frozenset({
    "min_untransformed_licks_cutoff",
    "exclude_failed_opto_chambers",
    "opto_unexplained_min_sec",
})
#: Names a Slice cannot take: the Hub and the scripts use them for the whole
#: recording and for every Slice at once.
RESERVED_NAMES = frozenset({"whole", "all", "none"})

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class SliceError(ValueError):
    """A ``slices:`` declaration that cannot be used."""


class SliceNotCovered(ValueError):
    """A Member's recording does not cover the Slice it was asked to load.

    Carries what the run records in ``slice.json``: the reason and each
    DFM's last minute.
    """

    def __init__(self, slice_: "Slice", reason: str, dfm_ends: Mapping[int, float]):
        super().__init__(f"Slice '{slice_.name}' {slice_.bounds_label()}: {reason}")
        self.slice = slice_
        self.reason = reason
        self.dfm_ends = {int(k): float(v) for k, v in dfm_ends.items()}


@dataclass(frozen=True)
class Slice:
    """One declared Slice of a Design."""

    name: str
    start: float
    #: ``None`` for a Slice that runs to the end of the recording.
    end: float | None
    exclusion_group: str
    also_exclude: tuple[str, ...] = ()
    constants: Mapping[str, Any] = field(default_factory=dict)

    @property
    def open_end(self) -> bool:
        return self.end is None

    @property
    def range_minutes(self) -> tuple[float, float]:
        """The pair the loaders clip by; ``0`` is their "to the end" sentinel."""
        return (float(self.start), 0.0 if self.end is None else float(self.end))

    @property
    def bounds(self) -> tuple[float, float]:
        """``(start, end]`` with the open end as ``inf``."""
        return (float(self.start), math.inf if self.end is None else float(self.end))

    @property
    def exclusion_groups(self) -> tuple[str, ...]:
        """Every group this Slice excludes: its own first."""
        return (self.exclusion_group,) + tuple(
            g for g in self.also_exclude if g != self.exclusion_group)

    def bounds_label(self) -> str:
        """``"(0, 360] min"`` / ``"(360, end] min"``."""
        end = "end" if self.end is None else _tidy(self.end)
        return f"({_tidy(self.start)}, {end}] min"

    def definition(self) -> dict:
        """What a run of this Slice depended on: compared with the record a
        run wrote to say whether its results still describe the Design."""
        return {
            "start": float(self.start),
            "end": None if self.end is None else float(self.end),
            "exclusion_group": self.exclusion_group,
            "also_exclude": list(self.also_exclude),
            "constants": {str(k): self.constants[k] for k in sorted(self.constants)},
        }


def _tidy(value: float):
    value = float(value)
    return int(value) if value.is_integer() else value


def _groups(value, where: str) -> tuple[str, ...]:
    if value is None or value == "":
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        raise SliceError(f"{where}: also_exclude must be a list of group names")
    out: list[str] = []
    for item in value:
        name = str(item).strip()
        if name and name not in out:
            out.append(name)
    return tuple(out)


def _end(value, where: str) -> float | None:
    if value is None or (isinstance(value, str) and value.strip().lower() in OPEN_END_WORDS):
        return None
    try:
        end = float(value)
    except (TypeError, ValueError):
        raise SliceError(f"{where}: end must be a minute or 'end', not {value!r}") from None
    if math.isinf(end):
        return None
    return end


def whole_recording_group(global_cfg: Mapping[str, Any] | None) -> str:
    """The whole recording's own exclusion group (``general`` by default)."""
    return str((global_cfg or {}).get("exclusion_group") or "general")


def also_exclude(global_cfg: Mapping[str, Any] | None) -> tuple[str, ...]:
    """The groups the whole recording also excludes (``global.also_exclude``)."""
    try:
        return _groups((global_cfg or {}).get("also_exclude"), "also_exclude")
    except SliceError:
        return ()


def tolerance(global_cfg: Mapping[str, Any] | None) -> float:
    """``slice_tolerance_min``, or :data:`DEFAULT_TOLERANCE_MIN`."""
    raw = (global_cfg or {}).get("slice_tolerance_min")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_TOLERANCE_MIN
    return value if math.isfinite(value) and value >= 0 else DEFAULT_TOLERANCE_MIN


def parse_slices(global_cfg: Mapping[str, Any] | None) -> list[Slice]:
    """The Design's Slices, in the order declared.  Raises :class:`SliceError`
    on the first one that cannot be used (:func:`slice_problems` lists them
    all)."""
    problems, slices = _parse(global_cfg)
    if problems:
        raise SliceError(problems[0])
    return slices


def slice_problems(global_cfg: Mapping[str, Any] | None, experiment_type=None) -> list[str]:
    """Every reason the Design's ``slices:`` cannot be used, for the linter
    and the editors; empty when they can (or there are none)."""
    problems, slices = _parse(global_cfg)
    if slices and experiment_type is not None and not allows_slices(experiment_type):
        problems.append(refusal(experiment_type))
    return problems


def _parse(global_cfg: Mapping[str, Any] | None) -> tuple[list[str], list[Slice]]:
    cfg = dict(global_cfg or {})
    node = cfg.get("slices")
    if node in (None, "", {}, []):
        return [], []
    problems: list[str] = []
    ## A mapping keyed by name; a list of {name: ...} entries is accepted too.
    if isinstance(node, list):
        entries = []
        for i, item in enumerate(node):
            if not isinstance(item, Mapping) or not item.get("name"):
                problems.append(f"slices[{i}]: each Slice needs a name")
                continue
            entries.append((item["name"], {k: v for k, v in item.items() if k != "name"}))
    elif isinstance(node, Mapping):
        entries = list(node.items())
    else:
        return ["slices: must be a mapping of Slice name to its start and end"], []
    ## YAML reads an unquoted 0_360 as the octal number 240 and 360_1440 as
    ## 3601440: a Slice named after its minutes must be quoted, or it would
    ## run under a number nobody wrote.
    named = []
    for name, body in entries:
        if not isinstance(name, str):
            problems.append(f"slices: a Slice name was read as the number {name!r}; quote a "
                            f"name that starts with a digit, e.g. '0_360':")
            continue
        named.append((name, body))
    entries = named

    whole_group = whole_recording_group(cfg)
    own_groups: dict[str, str] = {whole_group: "the whole recording"}
    slices: list[Slice] = []
    seen: set[str] = set()
    for name, body in entries:
        where = f"slices.{name}"
        if not _NAME_RE.match(name):
            problems.append(f"{where}: a Slice name is letters, digits, '_' and '-', "
                            f"starting with a letter or digit (it names a folder)")
            continue
        if name.lower() in RESERVED_NAMES:
            problems.append(f"{where}: '{name}' is reserved; choose another name")
            continue
        if name.lower() in seen:
            problems.append(f"{where}: two Slices are named '{name}'")
            continue
        seen.add(name.lower())
        if body is None:
            body = {}
        if not isinstance(body, Mapping):
            problems.append(f"{where}: must be a mapping with start and end")
            continue
        unknown = sorted(set(body) - {"start", "end", "exclusion_group", "also_exclude",
                                      "constants"})
        if unknown:
            problems.append(f"{where}: unknown key(s) {unknown}")
            continue
        try:
            start = float(body.get("start", 0) or 0)
        except (TypeError, ValueError):
            problems.append(f"{where}: start must be a minute, not {body.get('start')!r}")
            continue
        try:
            end = _end(body.get("end"), where)
            others = _groups(body.get("also_exclude"), where)
        except SliceError as err:
            problems.append(str(err))
            continue
        if not math.isfinite(start) or start < 0:
            problems.append(f"{where}: start must be a minute of 0 or more")
            continue
        if end is not None and end <= start:
            problems.append(f"{where}: end ({_tidy(end)}) must be after start ({_tidy(start)})")
            continue
        own = str(body.get("exclusion_group") or name).strip() or name
        ## An analysis's own group is where its removals are written, so two
        ## analyses sharing one would let a removal in one silently remove
        ## from the other.  Sharing is what also_exclude is for.
        if own in own_groups:
            problems.append(f"{where}: exclusion_group '{own}' is already the own group of "
                            f"{own_groups[own]}; list it under also_exclude to share it")
            continue
        own_groups[own] = f"Slice '{name}'"
        constants = body.get("constants") or {}
        if not isinstance(constants, Mapping):
            problems.append(f"{where}: constants must be a mapping")
            continue
        illegal = sorted(set(map(str, constants)) - AUTO_REMOVAL_CONSTANTS)
        if illegal:
            problems.append(f"{where}: constants {illegal} cannot vary by Slice; a Slice may "
                            f"override only {sorted(AUTO_REMOVAL_CONSTANTS)}")
            continue
        slices.append(Slice(name=name, start=start, end=end, exclusion_group=own,
                            also_exclude=others,
                            constants={str(k): v for k, v in constants.items()}))
    return problems, slices


def get_slice(global_cfg: Mapping[str, Any] | None, name: str) -> Slice:
    """The declared Slice *name*; raises :class:`SliceError` when the Design
    declares no such Slice or its declaration cannot be used."""
    for item in parse_slices(global_cfg):
        if item.name == name:
            return item
    raise SliceError(f"the design declares no Slice named '{name}'")


def usable_slices(global_cfg: Mapping[str, Any] | None, experiment_type=None) -> list[Slice]:
    """The Slices that can be used, ignoring any that cannot (the Project
    lists those as warnings); none under a type that has no Slices."""
    if experiment_type is not None and not allows_slices(experiment_type):
        return []
    return _parse(global_cfg)[1]


def slice_names(global_cfg: Mapping[str, Any] | None, experiment_type=None) -> list[str]:
    """The names of the usable Slices, ignoring any that cannot be used."""
    return [s.name for s in usable_slices(global_cfg, experiment_type)]


def allows_slices(experiment_type) -> bool:
    """False for a type whose Facets come from the data (the Ratio analysis)."""
    return not bool(getattr(experiment_type, "data_derived_facets", False))


def refusal(experiment_type) -> str:
    label = getattr(experiment_type, "display_name", None) or getattr(
        experiment_type, "name", "this type")
    return (f"experiment_type '{label}' has no Slices: its Training/Test Facets are split at "
            f"each Chamber Group's own training end, which a Slice could clip away")


# ---------------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------------

def coverage(slice_: Slice, dfm_ends: Mapping[int, float], tol: float) -> str | None:
    """Why a recording whose DFMs end at *dfm_ends* (minutes) does not cover
    *slice_*, or ``None`` when it does.  Every DFM must: a Member pooled
    under a Slice is a Member that recorded all of it."""
    short: list[str] = []
    for dfm_id in sorted(dfm_ends):
        last = float(dfm_ends[dfm_id])
        if not math.isfinite(last) or last <= slice_.start:
            short.append(f"DFM {dfm_id} ends at minute {last:.1f}, before the Slice starts")
        elif slice_.end is not None and last < slice_.end - tol:
            short.append(f"DFM {dfm_id} ends at minute {last:.1f}, short of the Slice's end "
                         f"at {_tidy(slice_.end)} (tolerance {_tidy(tol)} min)")
    return "; ".join(short) or None


def actual_end(slice_: Slice, dfm_ends: Mapping[int, float]) -> float:
    """The last minute the Slice holds data for: its end, or for an open
    Slice the earliest DFM end."""
    ends = [float(v) for v in dfm_ends.values() if math.isfinite(float(v))]
    last = min(ends) if ends else math.nan
    return last if slice_.end is None else min(float(slice_.end), last)


# ---------------------------------------------------------------------------
# The label of an unfaceted analysis
# ---------------------------------------------------------------------------

#: What a table calls the rows of an unfaceted analysis of the whole recording.
WHOLE_RECORDING_LABEL = "Whole recording"


def whole_label(slice_: Slice | None) -> str:
    """The label of an unfaceted analysis's rows: ``Whole recording``, or
    ``Slice <name>`` for a Slice, so a table never calls a Slice's minutes the
    whole recording."""
    return WHOLE_RECORDING_LABEL if slice_ is None else f"Slice {slice_.name}"


def is_whole_label(label) -> bool:
    """Whether *label* is :func:`whole_label`'s: the rows of an unfaceted
    analysis, the whole recording's or a Slice's, rather than a Facet."""
    text = str(label)
    return text == WHOLE_RECORDING_LABEL or text.startswith("Slice ")


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

def intersect_window(window: Sequence[float], bounds: tuple[float, float]):
    """``(a, b]`` intersected with the Slice's ``(start, end]``, or ``None``
    when nothing is left."""
    a = max(float(window[0]), float(bounds[0]))
    b = min(float(window[1]), float(bounds[1]))
    return (_tidy_bound(a), _tidy_bound(b)) if b > a else None


def intersect_windows(windows, bounds: tuple[float, float]) -> list[tuple]:
    """Each window intersected with the Slice, the empty ones dropped."""
    out = []
    for window in windows:
        kept = intersect_window(window, bounds)
        if kept is not None:
            out.append(kept)
    return out


def _tidy_bound(value: float):
    if math.isinf(value) or not float(value).is_integer():
        return value
    return int(value)


# ---------------------------------------------------------------------------
# Where outputs go, and the record a run leaves
# ---------------------------------------------------------------------------

def output_dir(root: str | Path, name: str) -> Path:
    """``<root>/slices/<name>``: a Slice's outputs under an Experiment
    Directory or a Project."""
    return Path(root) / DIRNAME / name


def write_record(root: str | Path, slice_: Slice, *, tol: float,
                 dfm_ends: Mapping[int, float], reason: str | None) -> Path:
    """Write ``slices/<name>/slice.json``: the definition the run used,
    whether the recording covered it, and where each DFM's data ended."""
    path = output_dir(root, slice_.name) / RECORD_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    ends = {str(int(k)): round(float(v), 4) for k, v in sorted(dfm_ends.items())}
    record = {
        "slice": slice_.name,
        "definition": slice_.definition(),
        "tolerance_min": float(tol),
        "covered": reason is None,
        "reason": reason,
        "dfm_end_minutes": ends,
        "actual_end_minutes": (None if not dfm_ends
                               else round(actual_end(slice_, dfm_ends), 4)),
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def read_record(root: str | Path, name: str) -> dict | None:
    """The ``slice.json`` a run of Slice *name* left, or ``None``."""
    path = output_dir(root, name) / RECORD_FILENAME
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def definition_changed(record: Mapping[str, Any] | None, slice_: Slice) -> bool:
    """Whether the Design's Slice differs from the one a run recorded: its
    results then describe bounds, groups or cutoffs nobody asks for now."""
    if not record:
        return False
    return dict(record.get("definition") or {}) != json.loads(json.dumps(slice_.definition()))
