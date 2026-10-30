"""The report blocks of the yoked comparison, under every Experiment Type.

Decision 12 of ``docs/paradigm-analyses-plan.md``: wherever a Linkage Group
yokes one or more chambers to a Paired one, the paired fly's feeding minus
its yoked partners' is reported by treatment, with Progressive Ratio's
tests.  The table comes from :func:`analytics.yoked_comparison
<pyflic.base.analytics.yoked_comparison>` (a member) or the Project's
stacked ``<project>_YokedComparison.csv``; these functions turn it into
report blocks (:mod:`pyflic.base.report_layout`) for the reports to place:

* :func:`yoked_table_blocks`, the differences by treatment, each tested
  against zero (:func:`analytics.zero_tests
  <pyflic.base.analytics.zero_tests>`, the paired t-test with the Wilcoxon
  signed-rank test beside it), then compared between treatments; one
  treatment gets the one-treatment note in place of that comparison;
* :func:`yoked_figure_blocks`, the paired against the yoked value of each
  group, with the identity line.

Both give no block for a table with no row: a design without yoking has no
such subsection.  Terms are ``CONTEXT.md``'s: Paired Chamber, Yoked Chamber,
Linkage Group.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from . import report_content as rc
from . import report_layout as rl
from .analytics import treatment_comparisons, zero_tests
from .slices import is_whole_label

#: How each default metric reads in a label, with the unit it carries.
_NOUNS: dict[str, tuple[str, str]] = {"Licks": ("licks", ""), "Events": ("events", ""),
                                      "MedDuration": ("median duration", " (s)")}


def difference_columns(frame: pd.DataFrame | None) -> list[str]:
    """The ``d<m>`` columns of a yoked-comparison table, in its order: those
    with a ``Paired<m>`` beside them."""
    if frame is None:
        return []
    return [c for c in frame.columns
            if c.startswith("d") and f"Paired{c[1:]}" in frame.columns]


def yoked_windows(frame: pd.DataFrame | None) -> list[tuple[str, pd.DataFrame]]:
    """``[(window, rows), ...]`` the blocks read: one per Facet when the
    table has Facets, in their order, else its whole-recording rows, as the
    reports read the feeding summary."""
    if frame is None or frame.empty or "Facet" not in frame.columns:
        return []
    labels = list(dict.fromkeys(frame["Facet"].astype(str)))
    facets = [label for label in labels if not is_whole_label(label)] or labels
    return [(label, frame[frame["Facet"].astype(str) == label]) for label in facets]


def _label(column: str) -> str:
    """A ``d<m>`` column as a label template for :func:`report_content.metric_label`
    (``{A}``/``{B}``: the well names): report_content's own where it has one."""
    if column in rc.METRIC_LABELS:
        return column
    base = column[1:]
    well = ""
    if base[-1:] in ("A", "B") and base[:-1] in _NOUNS:
        base, well = base[:-1], "{" + base[-1] + "}"
    noun, unit = _NOUNS.get(base, (base, ""))
    if unit:
        return f"Δ {noun}{', ' + well if well else ''}{unit}"
    return f"Δ {well + ' ' if well else ''}{noun} (paired − yoked)"


def difference_rows(frames: Sequence[tuple[str, pd.DataFrame]], metrics: Sequence[str], *,
                    mixed_p0: Callable[[pd.DataFrame], float | None] | None = None
                    ) -> list[dict]:
    """The differences by treatment, as :func:`analytics.zero_tests
    <pyflic.base.analytics.zero_tests>` rows: its tests where a treatment
    has two groups whose differences are not all equal, and the treatment's
    n and mean, untested, where it has not, so that every treatment shows."""
    tested = {(r["metric"], r["phase"], r["treatment"]): r
              for r in zero_tests(frames, metrics, mixed_p0=mixed_p0)}
    rows: list[dict] = []
    for metric in metrics:
        for label, frame in frames:
            if frame is None or frame.empty or metric not in frame.columns:
                continue
            data = pd.DataFrame({"Treatment": frame["Treatment"].astype(str).str.strip(),
                                 "Value": pd.to_numeric(frame[metric], errors="coerce")})
            data = data.dropna(subset=["Value"])
            for treatment, sub in data[data["Treatment"] != ""].groupby("Treatment", sort=False):
                found = tested.get((metric, label, str(treatment)))
                if found is not None:
                    rows.append(found)
                    continue
                v = sub["Value"].to_numpy(dtype=float)
                rows.append({"metric": metric, "phase": label, "treatment": str(treatment),
                             "n": int(v.size), "mean": float(v.mean()),
                             "sem": float(v.std(ddof=1) / np.sqrt(v.size)) if v.size > 1
                             else np.nan,
                             "p_t": np.nan, "p_wilcoxon": None, "p_mixed": None,
                             "significant": False, "test": "not tested"})
    return rows


def yoked_table_blocks(frame: pd.DataFrame | None, *, well_names: dict | None = None,
                       two_well: bool = True, include_comparison: bool = True,
                       mixed_p: Callable[..., float | None] | None = None,
                       mixed_p0: Callable[[pd.DataFrame], float | None] | None = None
                       ) -> list[Any]:
    """The differences by treatment: per metric, window and treatment the
    groups' paired − yoked mean ± SEM tested against zero; then, with two
    treatments or more and *include_comparison*, the treatments compared
    (:func:`analytics.treatment_comparisons
    <pyflic.base.analytics.treatment_comparisons>`, one observation per
    group).  One treatment gets the one-treatment note in place of that
    comparison: the test against zero is still the design's question.
    *mixed_p* and *mixed_p0* add the mixed models when a Project pools
    members.  No block for an empty table."""
    frames = yoked_windows(frame)
    metrics = difference_columns(frame)
    if not frames or not metrics:
        return []
    show_phase = len(frames) > 1 or not is_whole_label(frames[0][0])
    labels = {m: _label(m) for m in metrics}
    rows = [{**r, "metric": labels[r["metric"]]}
            for r in difference_rows(frames, metrics, mixed_p0=mixed_p0)]
    blocks: list[Any] = rc.zero_test_table(
        rows, caption="Paired − yoked difference by treatment (one observation per group)",
        well_names=well_names, show_phase=show_phase)
    levels = rc.treatment_levels(frame)
    if len(levels) == 1:
        blocks.append(rc.single_treatment_note(levels[0]))
    elif include_comparison:
        compared = [{**r, "metric": labels[r["metric"]]}
                    for r in treatment_comparisons(frames, metrics, mixed_p=mixed_p)]
        blocks += rc.stats_table(compared, caption="Treatment comparisons: paired − yoked "
                                                   "difference", well_names=well_names,
                                 show_phase=show_phase, two_well=two_well)
    return blocks


def _metric_title(column: str, well_names: dict | None) -> str:
    """A metric column (``LicksA``) as a panel title (``Sucrose licks``)."""
    names = well_names or {}
    base, well = column, ""
    if column[-1:] in ("A", "B") and column[:-1] in _NOUNS:
        base, well = column[:-1], names.get(column[-1]) or column[-1]
    noun, unit = _NOUNS.get(base, (base, ""))
    if well:
        return f"{well} {noun}{unit}" if not unit else f"{noun.capitalize()}, {well}{unit}"
    return f"{noun.capitalize()}{unit}"


def yoked_figure(frame: pd.DataFrame, *, well_names: dict | None = None,
                 factors: Sequence[str] | None = None):
    """One point per yoked group: its Paired chamber's value (y) against
    the mean of its Yoked chambers' (x), a panel per metric, coloured by
    treatment (the first design factor present, else the Treatment), over
    the dashed identity line: above it, the paired fly fed more.  Each
    panel's axes cover the same range, so the line is its diagonal.  Raises
    :class:`report_layout.NothingToDraw` when no group has both values."""
    import plotnine as p9

    from .experiment import _OKABE_ITO

    columns = [c[1:] for c in difference_columns(frame)]
    present = [f for f in (factors or []) if f in frame.columns]
    colour = present[0] if present else "Treatment"
    long = []
    for column in columns:
        part = pd.DataFrame({
            "Metric": _metric_title(column, well_names),
            "Paired": pd.to_numeric(frame[f"Paired{column}"], errors="coerce"),
            "Yoked": pd.to_numeric(frame[f"Yoked{column}"], errors="coerce"),
            "Colour": frame[colour].astype(str) if colour in frame.columns else "",
        }).dropna(subset=["Paired", "Yoked"])
        long.append(part)
    data = pd.concat(long, ignore_index=True) if long else pd.DataFrame()
    if data.empty:
        raise rl.NothingToDraw("No yoked group has both a paired and a yoked value.")
    order = list(dict.fromkeys(data["Metric"]))
    data["Metric"] = pd.Categorical(data["Metric"], categories=order, ordered=True)
    ## Two invisible points per panel at its range's ends, on the diagonal,
    ## so x and y cover the same range and the identity line is the diagonal.
    by_metric = data.groupby("Metric", observed=True)[["Paired", "Yoked"]]
    lo, hi = by_metric.min().min(axis=1), by_metric.max().max(axis=1)
    span = pd.DataFrame({
        "Metric": pd.Categorical([*map(str, lo.index), *map(str, hi.index)],
                                 categories=order, ordered=True),
        "v": [*lo.to_numpy(dtype=float), *hi.to_numpy(dtype=float)]})
    levels = list(dict.fromkeys(data["Colour"]))
    palette = {lvl: _OKABE_ITO[i % len(_OKABE_ITO)] for i, lvl in enumerate(levels)}
    return (p9.ggplot(data, p9.aes("Yoked", "Paired"))
            + p9.geom_abline(intercept=0.0, slope=1.0, linetype="dashed", color="#7f7f7f",
                             size=0.6)
            + p9.geom_blank(p9.aes("v", "v"), data=span)
            + p9.geom_point(p9.aes(color="Colour"), size=2.4, alpha=0.85)
            + p9.facet_wrap("~ Metric", scales="free")
            + p9.scale_color_manual(values=palette)
            + p9.labs(x="Yoked (mean of the group's yoked chambers)", y="Paired",
                      color=colour)
            + p9.theme_classic(base_size=10.0)
            + p9.theme(strip_background=p9.element_rect(fill="#f0f0f0", color="black",
                                                         size=0.5),
                       legend_position="bottom"))


def yoked_figure_blocks(frame: pd.DataFrame | None, *, well_names: dict | None = None,
                        factors: Sequence[str] | None = None, height: float = 3.4
                        ) -> list[Any]:
    """:func:`yoked_figure` once per window the table holds (each Facet,
    else the whole recording), as report plots.  No block for an empty
    table."""
    windows = yoked_windows(frame)
    if not windows or not difference_columns(frame):
        return []
    caption = ("One point per yoked group: the paired chamber's value against the mean of "
               "its yoked chambers'.  Dashed: equal; above it, the paired fly's value is the "
               "larger.")
    blocks: list[Any] = []
    for label, rows in windows:
        title = ("Paired against yoked" if is_whole_label(label)
                 else f"Paired against yoked: {label}")
        blocks.append(rl.Plot(lambda rows=rows: yoked_figure(rows, well_names=well_names,
                                                             factors=factors),
                              height=height, title=title, caption=caption))
    return blocks
