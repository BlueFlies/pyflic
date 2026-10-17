from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Sequence


_nsre = re.compile(r"(\d+)")

#: The Environmental Monitor's id.  PyMCU writes its records as
#: ``DFM99_<n>.csv`` beside the DFMs' (27 columns, ``W1``-``W6`` relay and
#: output states), so every DFM-id discovery skips it and the loader refuses
#: it (decision 5 of ``docs/v4-data-plan.md``).
ENVIRONMENTAL_MONITOR_ID = 99
ENVIRONMENTAL_MONITOR_MESSAGE = "DFM 99 is the Environmental Monitor, not a DFM"


def is_environmental_monitor(dfm_id) -> bool:
    """Whether *dfm_id* names the Environmental Monitor, not a DFM."""
    try:
        return int(dfm_id) == ENVIRONMENTAL_MONITOR_ID
    except (TypeError, ValueError):
        return False


def natural_key(s: str) -> list[object]:
    return [int(text) if text.isdigit() else text.lower() for text in _nsre.split(s)]


def natural_sorted(paths: Iterable[Path]) -> list[Path]:
    return sorted(list(paths), key=lambda p: natural_key(p.name))


def range_is_specified(rng: Sequence[float]) -> bool:
    return len(rng) == 2 and (float(rng[0]) + float(rng[1]) != 0.0)


def range_bounds(rng: Sequence[float]) -> tuple[float, float]:
    """``(start, end)`` for a specified range, with the open end resolved.

    ``0`` (and any non-positive end) is pyflic's "through the end of the
    recording" sentinel — ``windowing.as_range_minutes`` hands the tail Facet
    to the loaders as ``(start, 0)`` — so it becomes ``inf`` here instead of
    being read as a literal minute, which used to leave the last facet of
    every faceted experiment empty.
    """
    a, b = float(rng[0]), float(rng[1])
    if b <= 0.0:
        b = float("inf")
    return a, b

