"""Facet windows: a time window is a column, not a directory (ADR-0008).

pyflic used to write windowed results into ``analysis_<start>_<end>/``, so an
output path was a function of the requested window.  Facets replace that: the
Project Design fixes ``facet_cutoffs``, every Member is windowed
identically, and the window travels with the data as a column.

**Windows are half-open — ``(start, end]``** (:func:`range_mask`).  That is
what makes a faceted analysis a true partition of the recording: a lick
landing exactly on a cutoff belongs to the phase before it and to nothing
else.  The final facet always runs to ``inf``, so nothing is lost at the tail.
A Slice (ADR-0020) clips the load by the same rule, and Facets are
intersected with it.

``(0, 0)`` remains pyflic's sentinel for "the whole recording".

A Program Facet (``facet_source: program``) is not one window but a union of
them, so ``range_minutes`` may also be a list of windows (see
:func:`is_window_list`).
"""

from __future__ import annotations

FULL_RANGE = (0.0, 0.0)


def is_full_range(range_minutes) -> bool:
    """True when *range_minutes* is the "whole recording" sentinel ``(0, 0)``.

    Compares the pair directly rather than summing it, so a genuine window such
    as ``(-5, 5)`` is not mistaken for the sentinel.
    """
    try:
        return tuple(float(v) for v in range_minutes) == FULL_RANGE
    except (TypeError, ValueError):
        return False


def normalize_cutoffs(cutoffs) -> list[float]:
    """Coerce a facet-cutoff argument into a list of floats.

    Accepts a single number or any numeric sequence.  ``None`` raises rather
    than defaulting, so a caller that forgets to pass cutoffs fails loudly
    instead of silently splitting the recording somewhere arbitrary and
    labelling the result as the user's configured facets.
    """
    if cutoffs is None:
        raise ValueError(
            "cutoffs must be a number or a sequence of numbers, not None. "
            "Set 'facet_cutoffs' under 'global:' in flic_config.yaml (or in "
            "the Project design), or pass cutoffs= explicitly."
        )
    if isinstance(cutoffs, bool):
        raise ValueError(f"Invalid cutoffs: {cutoffs!r}. Must be numeric.")
    if isinstance(cutoffs, (int, float)):
        values = [cutoffs]
    elif isinstance(cutoffs, (str, bytes)):
        raise ValueError(f"Invalid cutoffs: {cutoffs!r}. Must be a number or a sequence.")
    else:
        try:
            values = list(cutoffs)
        except TypeError as err:
            raise ValueError(
                f"Invalid cutoffs: {cutoffs!r}. Must be a number or a sequence of numbers."
            ) from err
    if not values:
        raise ValueError("cutoffs must contain at least one value.")
    try:
        return [float(v) for v in values]
    except (TypeError, ValueError) as err:
        raise ValueError(
            f"Invalid cutoffs: {cutoffs!r}. Every value must be numeric."
        ) from err


def _tidy_bound(value):
    """Render a whole-number boundary as an int.

    ``FacetRange`` cells and plot titles show these values, so ``10`` must not
    become ``10.0`` just because it passed through a float normalisation step.
    """
    if value == float("inf") or value != int(value):
        return value
    return int(value)


def facet_windows(cutoffs) -> list[tuple]:
    """Return the ``[(start, end), ...]`` windows implied by *cutoffs*.

    Boundaries are sorted and de-duplicated, the first window opens at 0 and the
    last runs to infinity.  Combined with the half-open rule the windows tile
    the recording exactly once.
    """
    values = sorted(set(normalize_cutoffs(cutoffs)))
    bounds = [0.0] + [v for v in values if v > 0.0] + [float("inf")]
    tidied = [_tidy_bound(b) for b in bounds]
    return [(tidied[i], tidied[i + 1]) for i in range(len(tidied) - 1)]


def minute_label(window) -> str:
    """A plain minute-range label for *window*, e.g. ``"10-70 min"``."""
    start, end = window
    if end == float("inf"):
        return f"{_tidy_bound(start)}+ min"
    return f"{_tidy_bound(start)}-{_tidy_bound(end)} min"


def format_range(window) -> str:
    """The canonical ``FacetRange`` cell for *window* — round-trips through
    :func:`parse_range`."""
    start, end = window
    return f"({_tidy_bound(start)}, {_tidy_bound(end)})"


def parse_range(value) -> tuple:
    """A ``FacetRange`` cell (``"(10, 70)"`` / ``"(70, inf)"``) back to a tuple."""
    if isinstance(value, tuple):
        return value
    inner = str(value).strip().strip("()")
    lo, _, hi = inner.partition(",")
    return (float(lo), float(hi))


def as_range_minutes(window) -> tuple[float, float]:
    """A facet window as the ``range_minutes`` pair pyflic's loaders take.

    The open-ended tail becomes ``(start, 0)`` because ``0`` is pyflic's
    "through the end of the recording" sentinel — ``inf`` would be rejected by
    the range validators in ``dfm``.
    """
    start, end = window
    return (float(start), 0.0 if end == float("inf") else float(end))


# ---------------------------------------------------------------------------
# Several windows at once: a Program Facet (decision 7 of docs/v4-data-plan.md)
# ---------------------------------------------------------------------------
#
# A Program Facet pools the Cycles of a Repeating program, so its rows are a
# union of disjoint (a, b] windows.  ``range_minutes`` may therefore be a list
# of windows as well as one ``(a, b)`` pair; the summaries treat the list as
# one row mask, so a median is the median of the events inside the union, not
# an average of per-window medians.

def _is_pair(value) -> bool:
    return not isinstance(value, (str, bytes)) and hasattr(value, "__len__")


def is_window_list(range_minutes) -> bool:
    """True when *range_minutes* is a list of ``(a, b)`` windows rather than
    one ``(a, b)`` pair.  An empty list is a window list that selects
    nothing; ``(0, 0)`` stays the whole-recording sentinel."""
    if isinstance(range_minutes, (str, bytes)) or not hasattr(range_minutes, "__len__"):
        return False
    items = list(range_minutes)
    return len(items) != 2 or any(_is_pair(v) for v in items)


def window_bounds(range_minutes) -> list[tuple[float, float]]:
    """The ``(a, b]`` bounds of a window list, each open end (``0``, any
    non-positive end, or ``inf``) resolved to ``inf`` as
    :func:`pyflic.base.utils.range_bounds` does for one window."""
    out: list[tuple[float, float]] = []
    for window in range_minutes:
        a, b = float(window[0]), float(window[1])
        out.append((a, float("inf") if b <= 0.0 else b))
    return out


def window_mask(minutes, range_minutes):
    """``(n,)`` bool: which *minutes* fall in any window of the list."""
    import numpy as np

    values = np.asarray(minutes, dtype=float)
    mask = np.zeros(values.shape, dtype=bool)
    for a, b in window_bounds(range_minutes):
        mask |= (values > a) & (values <= b)
    return mask


def range_mask(minutes, range_minutes):
    """``(n,)`` bool for any ``range_minutes``: the rows whose *minutes* fall
    in the ``(a, b]`` window or in any window of a list; ``None`` for the
    whole-recording sentinel ``(0, 0)``.  What the feeding summary filters
    by, for a table of another kind to filter the same way."""
    import numpy as np

    from .utils import range_bounds, range_is_specified

    values = np.asarray(minutes, dtype=float)
    if is_window_list(range_minutes):
        return window_mask(values, range_minutes)
    if not range_is_specified(range_minutes):
        return None
    a, b = range_bounds(range_minutes)
    return (values > a) & (values <= b)


def range_key(range_minutes) -> tuple:
    """A hashable cache key for *range_minutes*: ``(a, b)`` as floats for one
    window (the key the feeding-summary cache has always used), a tuple of
    such pairs for a window list."""
    if is_window_list(range_minutes):
        return tuple((float(w[0]), float(w[1])) for w in range_minutes)
    return (float(range_minutes[0]), float(range_minutes[1]))


def range_span(range_minutes) -> tuple[float, float]:
    """``(start, end)`` for the ``StartMin`` / ``EndMin`` columns: the pair
    itself, or for a window list the first start and the last end.  An open
    end — the tail Facet's ``(start, 0)`` — reads ``inf``, as its
    ``FacetRange`` does; ``(0, 0)`` stays the whole-recording sentinel."""
    if not is_window_list(range_minutes):
        start, end = float(range_minutes[0]), float(range_minutes[1])
        if is_full_range(range_minutes):
            return start, end
        return start, (float("inf") if end <= 0.0 else end)
    windows = sorted(window_bounds(range_minutes))
    if not windows:
        return float("nan"), float("nan")
    return windows[0][0], windows[-1][1]


def format_ranges(windows, digits: int = 2) -> str:
    """The ``FacetRange`` cell of a Facet with one or more windows, each
    rounded to *digits* places for reading: ``"(0, 3); (15, 18)"``."""
    def bound(value: float):
        value = float(value)
        return _tidy_bound(value if value == float("inf") else round(value, digits))

    return "; ".join(f"({bound(a)}, {bound(b)})" for a, b in windows)
