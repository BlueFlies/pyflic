"""Control Comparisons: what an Experiment Type's report leads with (ADR-0019).

A type's ``control:`` block names a **Role comparison** (two Roles from the
Opto Program), a **Treatment control** (one of its factors, whose control
level the Design names as ``global.control_level``), or both; the reports
put them first in their Results, the Role comparison first (``CONTEXT.md``,
*Control Comparison*).

* **Paired against Yoked** is the paired − yoked comparison pyflic already
  makes — the yoked comparison (:func:`analytics.yoked_comparison
  <pyflic.base.analytics.yoked_comparison>`, :mod:`yoked_report`) under the
  Paired and yoked module, the Paired-Yoked Difference under the Ratio
  module.  The reports move it to the front; nothing here recomputes it.
* **Any other pair** compares the chambers of the two Roles within each
  treatment and window (:func:`role_rows`): Welch's t on per-chamber
  metrics, from the feeding summary's ``Role`` column.
* **A Treatment control** compares each level of its factor with the
  control level, the other factors held at the same levels
  (:func:`control_rows`): Dunnett's test, the control as the reference.

The metrics are the yoked comparison's (:data:`analytics.YOKED_METRICS`,
per well on a two-well layout).  Pure: no Qt; the figures import plotting
when they are drawn.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from . import report_content as rc
from . import report_layout as rl
from .analytics import yoked_metric_columns
from .opto_roles import ROLE_PAIRED, ROLE_YOKED

#: The feeding-summary column a Role comparison reads.
ROLE_COLUMN = "Role"


# ---------------------------------------------------------------------------
# What the type declares
# ---------------------------------------------------------------------------

def role_pair(experiment_type) -> tuple[str, str] | None:
    """The type's Role comparison, ``(A, B)``, or ``None``."""
    definition = getattr(experiment_type, "definition", None)
    return None if definition is None else definition.roles


def treatment_control(experiment_type) -> str | None:
    """The factor of the type's Treatment control, or ``None``."""
    definition = getattr(experiment_type, "definition", None)
    return None if definition is None else definition.treatment_control


def is_paired_yoked(roles: Sequence[str] | None) -> bool:
    """Whether *roles* is Paired against Yoked, in either order."""
    return roles is not None and set(roles) == {ROLE_PAIRED, ROLE_YOKED}


def leads_paired_yoked(experiment_type) -> bool:
    """Whether the type's Role comparison is the paired − yoked one, which
    the reports move to the front instead of repeating it later."""
    return is_paired_yoked(role_pair(experiment_type))


# ---------------------------------------------------------------------------
# The statistics
# ---------------------------------------------------------------------------

def _metrics(frames: Sequence[tuple[str, pd.DataFrame]],
             metrics: Sequence[str] | None) -> list[str]:
    for _label, frame in frames:
        if frame is not None and not frame.empty:
            return yoked_metric_columns(frame, metrics)
    return []


def role_rows(frames: Sequence[tuple[str, pd.DataFrame]], roles: Sequence[str],
              metrics: Sequence[str] | None = None) -> list[dict]:
    """The chambers of Role *A* against those of Role *B*, per metric,
    window and treatment: one row each with ``metric, phase, treatment,
    role_a, n_a, mean_a, role_b, n_b, mean_b, diff`` (A's mean minus B's)
    and ``p`` (Welch's t; ``NaN`` with fewer than two chambers on a side,
    or no variance), ``significant`` and ``test``.  A frame without a
    ``Role`` column (a member that is not optogenetic) gives no rows."""
    from scipy import stats as sstats

    role_a, role_b = roles
    rows: list[dict] = []
    for metric in _metrics(frames, metrics):
        for label, frame in frames:
            if frame is None or frame.empty or ROLE_COLUMN not in frame.columns \
                    or metric not in frame.columns:
                continue
            data = pd.DataFrame({
                "Treatment": frame["Treatment"].astype(str).str.strip(),
                "Role": frame[ROLE_COLUMN].fillna("").astype(str),
                "Value": pd.to_numeric(frame[metric], errors="coerce")}).dropna(subset=["Value"])
            data = data[(data["Treatment"] != "") & data["Role"].isin((role_a, role_b))]
            for treatment, sub in data.groupby("Treatment", sort=False):
                va = sub.loc[sub["Role"] == role_a, "Value"].to_numpy(dtype=float)
                vb = sub.loc[sub["Role"] == role_b, "Value"].to_numpy(dtype=float)
                if not va.size or not vb.size:
                    continue
                p = np.nan
                if va.size >= 2 and vb.size >= 2:
                    _stat, p = sstats.ttest_ind(va, vb, equal_var=False)
                    p = float(p)
                rows.append({
                    "metric": metric, "phase": label, "treatment": str(treatment),
                    "role_a": role_a, "n_a": int(va.size), "mean_a": float(va.mean()),
                    "role_b": role_b, "n_b": int(vb.size), "mean_b": float(vb.mean()),
                    "diff": float(va.mean() - vb.mean()), "p": p,
                    "significant": bool(np.isfinite(p) and p < 0.05), "test": "Welch t"})
    return rows


def _stratum(row: pd.Series, others: Sequence[str]) -> str:
    return ", ".join(f"{f} {row[f]}" for f in others)


def control_rows(frames: Sequence[tuple[str, pd.DataFrame]], factor: str, control: str,
                 factors: Sequence[str] = (), metrics: Sequence[str] | None = None
                 ) -> list[dict]:
    """Each level of *factor* against its *control* level, per metric and
    window, the design's other *factors* held at the same levels (each
    combination of them is a ``stratum``): Dunnett's test on the chambers,
    the control as the reference.  One row per level with ``metric, phase,
    stratum, level, n, mean, control, n_control, mean_control, diff`` (the
    level's mean minus the control's), ``p``, ``significant`` and ``test``.
    A level or control with fewer than two chambers is left out of the test
    and its row has ``p`` NaN.  No rows when the frames have no column for
    *factor*."""
    from scipy import stats as sstats

    others = [f for f in factors if f != factor]
    rows: list[dict] = []
    for metric in _metrics(frames, metrics):
        for label, frame in frames:
            if frame is None or frame.empty or factor not in frame.columns \
                    or metric not in frame.columns:
                continue
            present = [f for f in others if f in frame.columns]
            data = frame[[factor, *present]].astype(str).copy()
            data["Value"] = pd.to_numeric(frame[metric], errors="coerce").to_numpy()
            data = data.dropna(subset=["Value"])
            groups = data.groupby(present, sort=False) if present else [((), data)]
            for _key, sub in groups:
                stratum = _stratum(sub.iloc[0], present) if present else ""
                base = sub.loc[sub[factor] == str(control), "Value"].to_numpy(dtype=float)
                levels = [lv for lv in dict.fromkeys(sub[factor]) if lv != str(control)]
                if not base.size or not levels:
                    continue
                samples = {lv: sub.loc[sub[factor] == lv, "Value"].to_numpy(dtype=float)
                           for lv in levels}
                tested = [lv for lv in levels if samples[lv].size >= 2]
                p_of: dict[str, float] = {}
                if tested and base.size >= 2:
                    try:
                        result = sstats.dunnett(*(samples[lv] for lv in tested), control=base)
                        p_of = {lv: float(p) for lv, p in zip(tested, result.pvalue)}
                    except ValueError:
                        p_of = {}
                for lv in levels:
                    v = samples[lv]
                    p = p_of.get(lv, np.nan)
                    rows.append({
                        "metric": metric, "phase": label, "stratum": stratum, "level": lv,
                        "n": int(v.size), "mean": float(v.mean()), "control": str(control),
                        "n_control": int(base.size), "mean_control": float(base.mean()),
                        "diff": float(v.mean() - base.mean()), "p": p,
                        "significant": bool(np.isfinite(p) and p < 0.05),
                        "test": "Dunnett"})
    return rows


# ---------------------------------------------------------------------------
# The report blocks
# ---------------------------------------------------------------------------

def _p_tone(value: Any) -> str | None:
    try:
        return "info" if float(value) < 0.05 else None
    except (TypeError, ValueError):
        return None


def _show_phase(frames: Sequence[tuple[str, pd.DataFrame]]) -> bool:
    return len(frames) > 1 or (bool(frames) and frames[0][0] != "Whole recording")


def role_blocks(frames: Sequence[tuple[str, pd.DataFrame]], roles: Sequence[str], *,
                plot_frame: pd.DataFrame | None = None, facet_col: str | None = None,
                well_names: dict | None = None, two_well: bool = True,
                pooled: bool = False) -> list[Any]:
    """The Role comparison's subsection: a heading, what it compares, the
    table of :func:`role_rows`, and a dot plot of the first metric by Role
    within each treatment.  A sentence instead of the table when no chamber
    of either Role has a value."""
    role_a, role_b = roles
    rows = role_rows(frames, roles)
    blocks: list[Any] = [
        rl.Heading(f"Role comparison: {role_a} against {role_b}", level=2),
        rl.Paragraph(
            f"The type's Role comparison: within each treatment, the {role_a} chambers' "
            f"feeding against the {role_b} chambers', one observation per chamber"
            + (", pooled across members." if pooled else ".")
            + "  The Roles come from the Opto Program's linkage and thresholds.")]
    if not rows:
        return blocks + [rl.Paragraph(
            f"No treatment has both {role_a} and {role_b} chambers with a value, so "
            f"nothing is compared.", color=rl.MUTED, italic=True)]
    show_phase = _show_phase(frames)
    records = []
    for r in rows:
        rec = {"Measure": rc.metric_label(r["metric"], well_names, two_well=two_well)}
        if show_phase:
            rec["Phase"] = r["phase"]
        rec.update({"Treatment": r["treatment"], "n": f"{r['n_a']} / {r['n_b']}",
                    "Mean": f"{rl.fmt_value(r['mean_a'])} / {rl.fmt_value(r['mean_b'])}",
                    "Difference": r["diff"], "p": r["p"]})
        records.append(rec)
    blocks += [
        rl.Table(pd.DataFrame(records), caption=f"{role_a} against {role_b}, by treatment",
                 formats={"p": rl.fmt_p}, status={"p": _p_tone}),
        rl.Paragraph(f"n and Mean read as {role_a} / {role_b}; Difference is {role_a} minus "
                     f"{role_b}.  Welch's t-test; untested with fewer than two chambers on "
                     f"a side.  Highlighted: p < 0.05.", size=rl.SIZE_SMALL, color=rl.MUTED)]
    if plot_frame is not None and ROLE_COLUMN in plot_frame.columns:
        metric = rows[0]["metric"]
        shown = plot_frame[plot_frame[ROLE_COLUMN].isin(roles)]
        label = rc.metric_label(metric, well_names, two_well=two_well)
        blocks.append(rl.Plot(
            lambda: rc.dot_plot(shown, metric, y_label=label, factors=[ROLE_COLUMN],
                                facet_col=facet_col or "Treatment"),
            height=3.0, title=f"{label}: {role_a} and {role_b}"))
    return blocks


def control_blocks(frames: Sequence[tuple[str, pd.DataFrame]], factor: str,
                   control: str | None, *, factors: Sequence[str] = (),
                   plot_frame: pd.DataFrame | None = None, facet_col: str | None = None,
                   well_names: dict | None = None, two_well: bool = True,
                   pooled: bool = False) -> list[Any]:
    """The Treatment control's subsection: a heading, what it compares, the
    table of :func:`control_rows`, and a dot plot of the first metric by
    the factor's levels.  A callout when the Design names no control level."""
    heading = rl.Heading(f"Treatment control: {factor}"
                         + (f" against {control}" if control else ""), level=2)
    if not control:
        return [heading, rl.Callout(
            f"The type compares every {factor} with a control, and the design names "
            f"none: set control_level to one of the levels of {factor}.", tone="warning")]
    rows = control_rows(frames, factor, control, factors)
    others = [f for f in factors if f != factor]
    held = (f", {', '.join(others)} held at the same level{'s' if len(others) > 1 else ''}"
            if others else "")
    blocks: list[Any] = [heading, rl.Paragraph(
        f"The type's Treatment control: each {factor} against {control}{held}, one "
        f"observation per chamber" + (", pooled across members." if pooled else "."))]
    if not rows:
        return blocks + [rl.Paragraph(
            f"No {factor} other than {control} has chambers beside {control}'s, so nothing "
            f"is compared.", color=rl.MUTED, italic=True)]
    show_phase = _show_phase(frames)
    show_stratum = any(r["stratum"] for r in rows)
    records = []
    for r in rows:
        rec = {"Measure": rc.metric_label(r["metric"], well_names, two_well=two_well)}
        if show_phase:
            rec["Phase"] = r["phase"]
        if show_stratum:
            rec["Held"] = r["stratum"]
        rec.update({"Comparison": f"{r['level']} vs {r['control']}",
                    "n": f"{r['n']} / {r['n_control']}",
                    "Mean": f"{rl.fmt_value(r['mean'])} / {rl.fmt_value(r['mean_control'])}",
                    "Difference": r["diff"], "p": r["p"]})
        records.append(rec)
    blocks += [
        rl.Table(pd.DataFrame(records), caption=f"{factor} against {control}",
                 formats={"p": rl.fmt_p}, status={"p": _p_tone}),
        rl.Paragraph(f"n and Mean read as the level / {control}; Difference is the level "
                     f"minus {control}.  Dunnett's test, {control} the reference; untested "
                     f"with fewer than two chambers.  Highlighted: p < 0.05.",
                     size=rl.SIZE_SMALL, color=rl.MUTED)]
    if plot_frame is not None and factor in plot_frame.columns:
        metric = rows[0]["metric"]
        label = rc.metric_label(metric, well_names, two_well=two_well)
        blocks.append(rl.Plot(
            lambda: rc.dot_plot(plot_frame, metric, y_label=label, factors=[factor],
                                facet_col=facet_col),
            height=3.0, title=f"{label} by {factor}"))
    return blocks
