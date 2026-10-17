# Plot catalogue

What each figure shows, when it is produced, and what to look for in it.

## QC plots

Written to the member's `qc/` folder for every DFM whenever QC runs — the Hub's **QC
reports** button, the `run_qc` script action, or `execute_basic_analysis()` from Python.
The Hub's **Basic analysis** skips them; QC is the QC panel's job. These are diagnostics,
not figures for a paper.

| Plot | Saved as | Shows |
|---|---|---|
| Raw signal | `qc/raw_signal/DFM{n}_raw.png` | Every well's unprocessed signal |
| Baselined signal | `qc/baselined/DFM{n}_baselined.png` | Every well after baseline subtraction, with thresholds drawn |
| Cumulative licks | `qc/cumulative_licks/DFM{n}_cumulative_licks.png` | Running lick total per well over time |
| Light explained by licks | `qc/opto/opto_light_dfm{n}.png` | Optogenetic experiments only: each linkage group's lit time, explained and unexplained by trigger-well licks |
| Program timeline | `qc/program/program_timeline_dfm{n}.png` | A DFM with a `Program.txt` section or firmware 4.0.0 data: its Program Intervals, and each well's Acclimation, Activations and light |

The **baselined signal with thresholds** is the most useful one in the set. It puts your
`feeding_threshold` and `feeding_minimum` lines directly on the trace, so whether they sit
in a sensible place is a visual question rather than a guess.

**Cumulative licks** curves reveal timing at a glance: a steady slope is steady feeding, a
plateau is a fly that stopped, a step is a burst. A well whose curve never leaves zero is
inactive and should be excluded.

**Light explained by licks** (`plot_opto_light`) is drawn for an optogenetic experiment of
any type, by basic analysis as well. One row per linkage group. The left panel is its lit
time per bin, stacked: grey-blue where a trigger-well lick or touch within the light's
Hold explains it, red where nothing does, purple where it was lit while every threshold
was `Off` (-1), and light grey where the light is not judged by licks (open loop,
NonFeeding). The right panel is orange: on a recording older than firmware 4.0.0, when
`data/Program.txt` allows it, the time the emulated firmware trigger read the trigger wells
above threshold with no lick or touch; on a firmware 4.0.0 recording, titled *firmware
events, no lick*, the light of Activations the firmware counted with no lick or touch at
their onset. Lit time there is `OnMs`, in milliseconds. Red beside orange in the same bins
is a drifting sensor. The strip carries the group's verdict. See
[Optogenetic experiments](concepts-optogenetics.md).

### Program timeline

**Program timeline** (`plot_program_timeline`) is drawn for every DFM that has something to
draw: firmware 4.0.0 data, or a `Program.txt` section. **QC reports** write it for each such
DFM, and basic analysis for each firmware 4.0.0 DFM.

- **The band at the top** is the program, one block per Program Interval, coloured by
  Paradigm type and labelled with the Paradigm's name (and `C<n>`, the Cycle, when the
  program repeats). Light grey is the baseline before the first instruction reached the DFM,
  hatched white an instruction outside the program, and dark grey a Paradigm whose type
  `Program.txt` does not give.
- **Below it, one lane per well**, labelled with its chamber and Role. Pale orange shading is
  Acclimation (Phase `A`), each black tick an Activation, and the blue strip the share of
  each bin the LED was on, from white (dark) to dark blue (lit throughout).

How to read it:

- **Each trigger well should leave Acclimation**, its shading ending, within the
  interval that started it. A well still shaded at the end never completed Acclimation.
- **Ticks should come where the fly fed.** Under a ratio Paradigm they thin out as the
  Requirement rises. A dense comb of ticks with a flat cumulative-licks curve is the light
  following the sensor.
- **A yoked well has no ticks** and the same blue strip as its paired partner. Ticks on a
  yoked well, or a strip that differs, is broken yoking.
- **The band should match the program you meant to run.** A hatched block after the start
  is the DFM running something outside the program. A dark-grey block is a Paradigm the
  `Program.txt` in `data/` does not know, which usually means it is the wrong file; every
  block is dark grey when there is no `Program.txt` at all.

On a recording older than firmware 4.0.0 the band is laid out from the program's clock
times, approximate, and the lanes show the sampled `OptoCol1` light only: no Acclimation and
no ticks. The bin width is the plot action's `binsize` (10 minutes by default; the Hub uses
its Analyze panel's **Bin size**). See
[Optogenetic experiments](concepts-optogenetics.md#the-program-timeline).

## Summary plots

### Feeding summary

Box-and-jitter panels grouped by treatment — or by factor combination when
[factors](config-factors.md) are declared. Written to `analysis/feeding_summary.png` by
basic analysis.

Which metrics are panelled depends on the experiment type:

- **Single-well:** `Licks`, `Events`, `MeanDuration`, `MedDuration`, `MeanTimeBtw`,
  `MedTimeBtw`, `MeanInt`, `MedianInt`
- **Two-well, hedonic, progressive-ratio:** `PI`, `EventPI`, and A/B pairs of `Licks`,
  `Events`, `MeanDuration`, `MedDuration`, `MeanTimeBtw`, `MedTimeBtw`, `MeanInt`,
  `MedianInt`

Facet labels use your `well_names` when you have set them, so panels read `Sucrose` and
`Yeast` rather than `A` and `B`.

Because each point is a chamber, this is the plot that shows you your *spread*. A treatment
difference resting on two outlying chambers is visible here and invisible in a bar chart.

### Binned metric by treatment

A time course: per-treatment mean with an SEM band, across time bins. Use it to ask when
feeding happened rather than how much.

Any feeding-summary column works as the metric, plus base names — `Licks`, `Events`,
`MeanDuration`, `MedDuration`, `MeanTimeBtw`, `MedTimeBtw`, `MeanInt`, `MedianInt` — which
resolve automatically for the chamber size.

For two-well experiments, the combining mode matters and the sensible choice differs by
metric: **`total`** (A+B) for counts like `Licks` and `Events`; **`mean_ab`** for durations
and intervals, since summing two durations is meaningless. `A` and `B` isolate one well.

Bin width is yours to choose. Narrow bins show structure but are noisy; wide bins are
smooth but can hide a short-lived effect entirely. Try more than one before concluding
there is nothing there.

### Sliding-window plots

Three actions share this shape, each summarising a window of data and advancing by a step —
both in minutes, defaulting to 60 and 30.

| Plot | Shows |
|---|---|
| `plot_moving_window` | Treatment mean ± SEM of any metric |
| `plot_moving_median_chambers` | Median bout duration, one line per chamber, faceted by treatment |
| `plot_moving_median_treatment` | Treatment mean ± SEM of median bout duration |

Where binned plots cut time into non-overlapping slices, these slide a window across it, so
a step smaller than the window gives overlapping data and a smoother curve. That smoothing
is cosmetic: adjacent points share data and are not independent observations, so do not
treat them as such in a test.

`..._chambers` is the diagnostic version — it shows whether an effect is consistent across
flies or driven by a few. `..._treatment` is the version for a figure.

## Choice-specific plots

**Well A vs Well B duration jitter**, faceted — a direct visual comparison of the two
options within each treatment.

**Cumulative preference index**, per DFM — how a preference developed over the session. A PI
that starts near zero and separates gradually is a different phenomenon from one that is
established from the first minutes, and only a cumulative view distinguishes them.

## Hedonic plots

**Hedonic feeding plot** — Well A against Well B median durations, faceted by treatment.
Duration is the measure of interest in these designs; see
[Experiment types](concepts-experiment-types.md).

## Light behaviour plots

Drawn for an optogenetic experiment of any type, from its
[light table](concepts-optogenetics.md#the-light-table): what the light did, one point per
chamber.

**Light behaviour dot plots** — in the experiment report's and the Project Report's *Light
behaviour* section. One dot plot per headline metric, by Treatment, per Facet when the
experiment has them: **Activations**, **Lit time (s)**, **Firmware Events** and
**Acclimation end (min)**. The diamond and bars are the treatment mean ± SEM, and the
treatment comparisons sit underneath. A metric no Paradigm of the experiment defines is left
out, and so is everything but lit time on a recording older than firmware 4.0.0. A
Progressive Ratio experiment shows its paired chambers only: a yoked fly's light is its
partner's.

**Light Publication Figures** — in a Project whose Combined Analysis has a light table, the
[Plot Editor](app-plot-editor.md) offers every numeric column of it as a faceted figure, on
the shape of `faceted_licks`: x = Treatment, one panel per Facet, dots with mean ± SEM. Each
is listed as *… (light, faceted)* and drawn from `<project>_LightSummary_Facet.csv`, or
`<project>_LightSummary.csv` when the members have no Facets.

| Plot id | Metric |
|---|---|
| `faceted_activations` | Activations |
| `faceted_litsec` | Lit time (s) |
| `faceted_firmwareevents` | Firmware Events |
| `faceted_acclimationendmin` | Acclimation end (min) |
| `faceted_litfraction` | Fraction of the time lit |
| `faceted_activationsperhour` | Activations per hour |
| `faceted_lightonsets` | Light onsets |
| `faceted_acclimationactivations` | Acclimation Activations |
| `faceted_lastrequirementmet` | Last Requirement met |
| `faceted_progressatend` | Progress at the end |
| `faceted_eventsperactivation` | Firmware Events per Activation |
| `faceted_lockedoutcontactsec` | Feeding while locked out (s) |
| `faceted_unlitsec` | Unlit time (s) |
| `faceted_suppressions` | Suppressions |

The first four are the headline metrics the reports test.

## Progressive-ratio plots

### Paired and yoked are never pooled

A Treatment in this type names *both* flies of a Chamber Group, so grouping by Treatment
alone would draw one cloud of points holding an effect together with its own control. The
yoked fly's PI is not a second measurement of the paired fly's preference — it is what the
paired fly is measured *against*, and averaging the two lands halfway to nothing.

So for a Progressive Ratio member the standard plots behave differently:

- The **dot plot** shows the **within-group difference**: one point is one Chamber Group's
  paired-minus-yoked value of the chosen metric, panelled by Facet (Training, then Test),
  with zero drawn as the null the points are read against. This is the unit the type is
  built on — a difference is always taken within a Chamber Group, never between group
  means. Any metric in the dropdown works, including the A/B combinations; the fixed set
  in `paired_yoked_diff.csv` is the same numbers for the metrics it stores.
- The **feeding summary**, the **binned time course** and the **sliding-window** plots
  split every group by role, so a treatment becomes two series — `w1118 · paired` and
  `w1118 · yoked` — rather than one.

Leave Start/End empty and the difference is taken over each group's own Training and Test
Facets. Give an explicit window and that one window is used for every group instead, with
the Facet column reading `Custom`: the Facets are per Chamber Group, so a single shared
window is a different question rather than a filter on the same one.

Project-level faceted publication figures in the [Plot Editor](app-plot-editor.md) panel by
Role when the Combined Analysis carries it. Use the pooled `<project>_PairedYokedDiff.csv`
or the Project Report for the paired − yoked *difference* statement across members.

### The type's own figures

**Cumulative difference curve** (`plot_pr_cumulative_diff`, and `timecourse_pr_diff` in a
Project) — the headline figure: paired-minus-yoked cumulative sucrose-well licks against
minutes since the chamber group's training end, one mean ± SEM curve per treatment with the
individual group traces faint behind. The mean runs only as far as the shortest group, so
every group is in every averaged point and the curve never jumps when one group's recording
ends; the faint traces run to each group's own end.

**Breaking point vs Test time** (`scatter_pr_breaking_point` in a Project) — one point per
chamber group from the stacked `pr_breaking_point.csv`: Breaking Point against `BreakMin`
(minutes since training end of the last counted Test light event), coloured by treatment.
Open symbols are censored (still responding at the end of the Test window).

**Breaking point by treatment** (`dot_pr_breaking_point` in a Project) — the same rows with
Treatment on the x axis and Breaking Point on y (no Phase/Role facets). Open symbols are
censored; mean ± SEM overlays each treatment.

**Training-aligned traces** (`plot_pr_cumulative_licks`) — per DFM, one panel per chamber
group: paired and yoked cumulative sucrose-well licks since training end, with the bins in
which the group's light was on drawn as points and lick-free light events as black rings on
the paired trace. A QC figure, not a result.

**Still-responding curve** (`plot_pr_still_responding`, and the first figure of the Project
Report's breaking point section) — per treatment, the fraction of paired flies whose
[breaking point](concepts-progressive-ratio.md#breaking-point) reached each ratio. It is a
Kaplan-Meier curve: a fly still responding when its Test window ended is censored, a lower
bound, and is drawn as a tick where it leaves the curve rather than counted as having
stopped.

**Breaking-point plots** (`plot_breaking_point`) — per DFM, one panel per chamber:
`DeltaLicks` per light-on period against minutes since training end, the paired panel's
strip giving the group's breaking point (`n+` when censored). A dashed line marks the break,
the last light event the breaking point counts, on both chambers of the group; onsets past
it are grey, and lick-free light events, which never count, are hollow red rings.

All of these require light data (`OptoCol1`).

### Did the paired fly earn its light? (QC)

The firmware lights a chamber group from its own reading of the paired chamber's Sucrose
Well *during* the run; pyflic counts licks *afterwards*, from the baselined signal. When a
Sucrose Well's resting level creeps up, the firmware reads it as continuous contact and
fires the light on its own schedule, while the baselined signal is flat and no licks are
recorded — so the light looks earned in every light-on number and nothing was earned. Two
figures show it, beside the training-aligned traces:

**Licks per light event** (`plot_pr_light_events`) — per DFM, one panel per chamber group:
the sucrose licks credited to each Test-phase light event, against the event's number. A
working progressive ratio climbs. Hollow red rings are **lick-free light events**, the
dashed line is the group's own trend, and the faint grey line is the requirement estimated
across the experiment (the median slope of the groups' first eight Test events). A long row
of red rings along zero is the light following the sensor, not the fly.

**Sucrose Well resting level** (`plot_pr_resting_level`) — per DFM, one panel per chamber
group: the paired chamber's Sucrose Well as its per-minute median raw signal over the whole
recording, against the median of the DFM's other Sucrose Wells (grey). Light onsets are the
rug along the bottom and the dashed line is training end. A well that creeps up while its
rug thickens is the cause behind the red rings.

Both are on the Hub's QC panel, in its *Optogenetics* group beside the **Light QC
table**.

Every panel's strip carries the group's light QC verdict. A group that failed — and so left
the analysis — stays in these three figures, its strip saying why; the result figures
(the cumulative difference curve, the dot plot) no longer contain it. See
[Light QC](concepts-progressive-ratio.md#light-qc) for the checks behind the verdict.

## Where plots are saved

Every figure the Hub's Plots panel draws is also written to the member's `analysis/` folder
(the file names are in [Script actions](scripts-actions.md#plot-actions)), and opens as a tab
in the output area. The Hub shows figures as static images, which paint fast and hold no live
canvas in memory. Publication figures are the [Plot Editor](app-plot-editor.md)'s, written
to the Project's `figures/`.

---

Related: [Summary metrics](concepts-metrics.md) · [Script actions](scripts-actions.md)
