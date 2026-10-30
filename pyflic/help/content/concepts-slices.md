# Slices: analysing part of a recording on its own

A **Slice** is a named part of a recording — say the first 6 hours, or hours 6 to 24 —
analysed as if the recording were only that part. It has its own excluded chambers, its own
QC and its own results, in its own folder. Use one when a part of the experiment needs to be
judged on its own: a chamber whose well dried at hour 10 belongs out of the 24-hour analysis
but is fine for the first 6 hours.

A Slice is not a [Facet](concepts-facets.md). A Facet is a column that splits *one*
analysis into windows, all with the same chambers. A Slice is a *separate analysis*, with its
own chambers. Facets still split each Slice.

## Slices in the design

Slices are declared once, in the design, so every member runs every Slice:

```yaml
global:
  exclusion_group: general        # the whole recording's own exclusion group
  also_exclude: [dead]            # groups the whole recording also excludes
  slice_tolerance_min: 5
  slices:
    first_6h:
      start: 0
      end: 360
      also_exclude: [dead]
      constants: {min_untransformed_licks_cutoff: 20}
    last_18h:
      start: 360
      end: end                    # to the end of the recording
      also_exclude: [dead]
```

- `start` and `end` are minutes. `end: end` runs to the end of each recording.
- A name is letters, digits, `_` and `-`; it names a folder. `whole`, `all` and `none` are
  reserved.
- `constants:` may change only the cutoffs that decide which chambers auto-removal takes
  out (`min_untransformed_licks_cutoff`, `exclude_failed_opto_chambers`,
  `opto_unexplained_min_sec`): a 6-hour Slice needs a lower lick cutoff than 24 hours.
  Detection settings stay the design's, so a Slice is the same analysis of fewer minutes.

The **whole recording** is always analysed too, exactly as before: its results stay in
`analysis/` and `qc/`. Slices may overlap, and they are never compared with one another.

## What a Slice does

The rows outside the Slice are dropped when the data is loaded, before the baseline, the
thresholds, event detection and auto-removal. Nothing outside the Slice can change its
results. A Slice's windows include their end minute and exclude their start, as Facets' do,
so `first_6h` and `last_18h` share no sample and lose none at minute 360.

Its outputs go in `slices/<name>/` inside the experiment directory: `analysis/`, `qc/`, the
experiment report, and `slice.json`, which records the Slice's definition and where each
DFM's data ended.

## Exclusions

Each Slice has its **own exclusion group** in `remove_chambers.csv`: the one the QC Viewer
writes to when you exclude a chamber while viewing that Slice. It is the Slice's name unless
you set `exclusion_group:`. A Slice inherits nothing from the whole recording's group.

To exclude a chamber everywhere — a fly dead from the start — list it once in a shared
group, such as `dead`, and name that group under `also_exclude:` for the whole recording and
for each Slice. A chamber that fails at hour 10 goes only in the whole recording's group:
it leaves the 24-hour analysis and stays in `first_6h`.

## Coverage

A member **covers** a Slice when every DFM's recording reaches the Slice's end, within
`slice_tolerance_min` (5 minutes by default; a 24-hour run often ends at minute 1439.8).
A member that does not cover a Slice is left out of it — its `slice.json` says why — and the
Project's results for that Slice name it rather than pooling part of a Slice.

A Slice that runs to `end` covers any recording that reaches its start. Members then pool
spans of different lengths under one name, so the Project Report warns when their ends are
more than the tolerance apart.

## In a Project

Each Slice has its own Combined Analysis, Project Report and figures, in `slices/<name>/`
at the Project root, pooled from the members that cover it. **Analyze all** and a Batch
Run's `run_all_analyses` run the whole recording and every Slice; building the Combined
Analysis or the Project Report does the same. A publication figure's Plot Spec names the
Slice it draws from (`slice:`), blank for the whole recording.

## Scripts and the Hub

A script step works on the Slice its `slice:` parameter names, or the script's; with
neither, on the whole recording. The `start` and `end` a step once took are retired: a step
that still states a window is skipped, and `pyflic lint` names the Slice to declare instead.

`run_qc`, `run_analysis` and `run_plots`, like the Hub's buttons, run the whole recording and
every Slice the Selection keeps (`omit: slices:` leaves one out).

## Progressive Ratio and Fixed Ratio

A type with the Ratio analysis has no Slices. Its Training and Test Facets are split at each
Chamber Group's own training end, which a Slice could clip away.

## Coming from `analysis_0_360/`

Older pyflic wrote ranged runs into `analysis_<start>_<end>/`. A Slice is that, done so a
Project can pool it: declared once, with its own exclusions, never overwritten by another
range. pyflic never reads, moves or deletes the old folders; `pyflic lint` lists them with the
Slice that reproduces each.
