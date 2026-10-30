---
status: accepted
---

# A Slice is a separate analysis of part of a recording

ADR-0008 retired the `analysis_<start>_<end>/` directories: a time window became a Facet,
a column of one analysis, so a Project could pool by label. That left one thing the old
directories did that a Facet cannot. A Facet splits one analysis, with one set of chambers
and one auto-removal, so a chamber whose well failed at hour 10 is either out of every
window or in all of them. The old ranged runs could exclude it from the 24-hour analysis and
keep it for the first 6 hours.

We add the **Slice**: a named part of a recording analysed as if the recording were only
that part, declared in the Design, with its own exclusion group, auto-removal cutoffs, QC
and outputs under `slices/<name>/`. A Slice's Combined Analysis pools by name, and only the
Members whose recording covers it.

## Decisions

- **Above Facets, not instead of them.** Facets keep splitting each Slice, intersected with
  it, an empty one dropped and listed. Facet labels come from the whole recording's windows,
  so a Facet pools under one name in every Slice.
- **Declared in the Design**, so every Member runs every Slice and "the same range" is one
  definition, not numbers that happen to match. Matching per-Member ranges would have made
  `0–360` and `0–360.0`, or `360→end` and `360–1440`, a judgement call, and broken
  ADR-0005's rule that the Design owns all of `global:`.
- **Clip, not cut.** Rows outside a Slice are dropped at load, before baselining,
  thresholds, event detection and auto-removal, so nothing outside the Slice can change it.
  The cost is that Slices do not add up to the whole recording: a bout crossing a boundary is
  split. Clipping follows Facets' `(start, end]` rule, so adjacent Slices share no row.
- **No inherited exclusions.** Each analysis — the whole recording or a Slice — has one own
  group, the only one its removals are written into, and `also_exclude:` groups it reads but
  never writes. Inheriting the whole recording's group would break the very case Slices
  exist for. Two analyses may not share an own group.
- **A Slice may override only the auto-removal cutoffs.** A 6-hour Slice needs a lower lick
  cutoff than 24 hours; detection settings stay the Design's.
- **Coverage with a tolerance.** A Member covers a Slice when every DFM reaches its end
  within `slice_tolerance_min` (default 5); otherwise it is left out of that Slice and says
  why in `slice.json`. Open-ended Slices are allowed, and the Project Report warns when the
  pooled Members' ends differ by more than the tolerance.
- **The whole recording is unchanged**: implicit, in `analysis/` and `qc/`.
- **No Slices under the Ratio analysis** (Progressive Ratio, Fixed Ratio): its Training/Test
  split sits at each group's own training end, which a Slice could clip away.
- **No comparisons across Slices.** Each has its own chamber population.

## Consequences

- Amends ADR-0008: windowed output directories return, named by Slice and declared once.
- An Experiment Script's `start`/`end` are retired in favour of `slice:`. A step that still
  states a window is skipped with a log line rather than run: in `analysis/` it overwrote
  the whole recording's summary. `pyflic lint` names the Slice to declare, and for each old
  `analysis_<a>_<b>/` folder the Slice that reproduces it; pyflic still never touches them.
- The Hub's Selection gains `omit.slices`; its runs, and a script's `run_*` steps, cover
  the whole recording and every Slice kept. *Analyze all* and a Batch Run cover every Slice.
- A Plot Spec names its Slice, so a figure stays regenerable from its Spec.
- The stale rule (ADR-0010) applies per Slice, and a Slice whose definition changed since
  its run also reads "re-run needed". A Member's `slice.json` describes its analysis of the
  Slice: a QC-only run writes one only where no analysis under another definition would be
  hidden by it, and a "not covered" record left by another definition is no verdict on the
  current one. The Project's `slices/<name>/` records no definition: its Combined Analysis
  is rebuilt from the Members' outputs, whose records already carry it.
- The feeding-summary disk cache is now keyed by the Design's `global:`, the chambers
  excluded and the Slice; before, an exclusion edit could return the summary from before it.
