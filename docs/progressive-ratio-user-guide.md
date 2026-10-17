# Analysing a Progressive Ratio assay with pyflic

A guide for researchers running Progressive Ratio (PR) experiments on the
FLIC. It explains what pyflic measures, which settings you control and how
to choose them, how to read each figure, and what the statistics do and do
not let you conclude.

You do not need to read code to use it. For installing and starting pyflic,
see [Getting Started](GETTING_STARTED.md). For the quality-control checks
every experiment gets, including the optogenetic light QC, see
[Checking your data](qc-user-guide.md). The in-app help topic
*Progressive Ratio experiments* (`pyflic help`) covers the same ground as a
concise reference. The developer's view is in
[progressive-ratio-implementation.md](progressive-ratio-implementation.md).

---

## 1. The assay in one page

Each DFM's six chambers form three **chamber groups**: chambers 1+2, 3+4 and
5+6. The two chambers of a group share one light circuit and one treatment.

- The **paired** fly controls the light. When it feeds at the **sucrose
  well** (always well A), the light comes on, typically driving
  optogenetic stimulation.
- The **yoked** fly, its partner, is lit at exactly the same moments,
  whatever it does itself. It receives the same light but cannot earn it.

The recording has two phases:

1. **Training.** Closed loop: every sucrose feed by the paired fly turns
   the light on. The firmware marks training in the data, and each group
   finishes training at its own time, when its paired fly has done so.
2. **Test.** The firmware demands progressively more feeding for each light
   event. A fly that finds the light rewarding keeps working as the price
   rises, up to a point. From DFM firmware 4.0.0 the price is counted in
   feeding bouts, and a fixed ratio, the same price every time, is possible
   too.

The analysis asks three questions:

| Question | Main measure |
|---|---|
| Does the paired fly feed differently from a fly that got the same light for free? | the **paired − yoked difference**, within each group |
| How far did the paired fly keep working as the requirement rose? | the **breaking point** |
| How long did each fly keep feeding at the sucrose well? | **sucrose persistence**, for both flies |

Two rules run through everything:

- **Differences are always taken within a chamber group, never between
  group means.** The yoked fly is the paired fly's own control: same
  device, same light, same moments.
- **Time runs from each group's training end**, not from the start of the
  recording.

---

## 2. Before you start

### Data you need

What the DFM files must hold depends on the firmware that recorded them.
pyflic reads the shape of each DFM's file and calls it its **generation**:

| Generation | Recorded by | Training is read from | Light events are read from |
|---|---|---|---|
| 1 | PyMCU 3.x, DFM firmware before 4.0.0 | a flag inside the sucrose well's signal | onsets of the light in `OptoCol1` |
| 2 | PyMCU 4.0.0, DFM firmware before 4.0.0 | nowhere: no training information | onsets of the light in `OptoCol1` |
| 3 | PyMCU 4.0.0, DFM firmware 4.0.0 | the paired sucrose well's Phase column | the paired sucrose well's Activations |

- **Generation 1 needs version-3 DFM files with light data (`OptoCol1`).**
  The training flag and the light state both live there. Without them no
  group ever finishes training, and every group is removed.
- **Generation 2 has no training information at all.** Its groups are
  kept, each as one `Recording` phase with no Test, no breaking point and no
  sucrose persistence (section 5.1).
- **Generation 3 records Training, every light event and the requirement it
  met** in its own columns, and the light exactly.
- **Both wells named:** well A is the sucrose well, well B the yeast well.
- **The MCU's `Program.txt`.** The MCU writes the program it ran back out as
  `Program.txt`; copy it into the member's `data/` folder, beside the DFM
  files. pyflic reads both the PyMCU 4.0.0 export and the older one. It
  tells pyflic each well's threshold, the linkage and the light's rule — its
  **Paradigm**: ProgressiveRatio or FixedRatio, with its settings — which
  the light QC needs to judge the light properly, and it can name the paired
  chambers for you. Without it the analysis still runs, with a more limited
  light QC. **On generation 3 it is all but required:** the data name each
  Paradigm but not its type, so without the file a fixed ratio cannot be
  told from a progressive one, and pyflic warns loudly (*firmware 4.0.0
  recording without Program.txt*).

A firmware 4.0.0 program usually runs a ClosedLoop Paradigm first, then the
ratio Paradigm, or a ratio Paradigm whose `Acclimation` setting gives each
fly a set number of closed-loop light events first. Either way that opening
is Training.

### Setting up the experiment

For each DFM, the config states which chamber of each group is paired, and
which side of the chamber well A (sucrose) is on:

```yaml
dfms:
  1:
    params: {pi_direction: left}      # which side well A (sucrose) is on
    paired_chambers: [1, 4, 5]        # exactly one chamber from each group
    chambers: {1: Ctrl, 2: Ctrl, 3: Exp, 4: Exp, 5: Exp, 6: Exp}
```

- **`paired_chambers`** must name exactly one chamber from each of 1–2,
  3–4 and 5–6. The yoked chamber is the other one and is never written.
- **Both chambers of a group must carry the same treatment.** pyflic
  refuses to load a config where they differ.
- **Paired and yoked are roles, not treatments.** Don't create a "paired"
  treatment or design factor; pyflic adds a `Role` column itself.
- In the **Config Editor**, the paired chambers are three pickers on each
  DFM tab.
- **With `Program.txt` in `data/`, `paired_chambers` may be left out.** In
  each group the chamber holding the program's trigger well is the paired
  one. If you give both and they disagree, your config wins and
  `summary.txt` says so; a trigger well that is well B is flagged too.

### Setting up the Project

Put the recordings that answer one question into one **Project**. Its
`project.yaml` holds the shared **design**, which every member inherits:

```yaml
# project.yaml
name: my_pr_study
design:
  global:
    experiment_type: ProgressiveRatio
    well_names: {A: Sucrose, B: Yeast}
    constants:
      pr_break_gap_min: 120
      # pr_test_window_min: 720        # optional; see section 4
    experimental_design_factors:
      Genotype: [Ctrl, Exp]
```

Edit it in the Hub with **Project panel → Project design…**. Its sections
hold every setting in section 4. **Set the analysis constants here, once.**
Every member is then analysed under the same rules, which pooling
requires.

---

## 3. Running the analysis

For each member (experiment):

1. **Hub → Analyze → Basic analysis.** This runs everything below and
   writes the tables and figures into the member's `analysis/` folder.
2. **Hub → Analyze → PDF report**, or `pyflic report <member folder>`. This writes
   the experiment report.

For the Project:

3. **Project panel → Build combined analysis.** This stacks every member's
   tables and runs the pooled statistics (`<project>_Stats.txt`).
4. **Project panel → Create report**, or `pyflic report <project folder>`.
   This writes the Project Report.

Every step is also a Script Editor action, so a Project Script or
`pyflic batch` can run it unattended. **Re-run basic analysis after changing
any setting.** Members analysed before a setting changed keep their old
numbers until you do.

**Check each member's data before its results.** Basic analysis does not
write the per-DFM QC bundle (integrity, data breaks, crosstalk and the
signal plots). **Hub → QC → QC reports** writes it, and **Open QC Viewer**
shows it. [Checking your data](qc-user-guide.md) explains every check.

### What basic analysis does, in order

1. **Training.** It finds each group's training end (section 5.1).
2. **Quality control and exclusions.** It checks training and light for
   every group, and removes chambers that fail (sections 5.2 and 5.3).
   It also runs the optogenetic light QC and writes it into `qc/opto/`
   (section 5.2).
3. **Feeding summaries.** It computes the standard two-well metrics (licks,
   events, durations, preference index) per chamber, for the whole
   recording and separately for the Training and Test phases.
4. **Paired − yoked difference.** One row per chamber group per phase
   (section 5.4).
5. **Cumulative difference curve** (section 5.5).
6. **Breaking point** and **sucrose persistence** (sections 5.6 and 5.7).
7. **Figures** and the text summary (`summary.txt`).

---

## 4. Settings you control

All of these are in the Project's design (**Project design…**), except
the figure bin size, which is set per plot action. The defaults are chosen
to be sensible for a typical overnight recording. Change one only for a
reason you can state.

### Study design

| Setting | What it does | Choosing it |
|---|---|---|
| `paired_chambers` (per DFM) | which chamber of each group controls the light | from your rig setup; must match what the firmware did |
| `pi_direction` (per DFM) | which side well A, the sucrose well, is on | from your rig setup; may differ between DFMs |
| treatments (`chambers:`) | what each group received | the same for both chambers of a group |
| `experimental_design_factors` | factors such as genotype and drug, crossed | the first factor is the x axis of the dot plots |
| `well_names` | labels for wells A and B in plots and reports | well A must be the sucrose well |
| `transform_licks` | transforms lick counts in the summary tables | the cumulative curves always use raw counts regardless |

### Detection parameters

`feeding_threshold`, `feeding_minimum`, `tasting_minimum` and the other
detection parameters decide which signal deflections count as licks and
feeding events. They matter more in this assay than in most, because the
**light QC** and the **breaking point** both depend on whether a light event
was backed by at least one lick. See the *Parameter reference* help topic. Change
them for the whole Project, never for one member.

### Exclusion

| Setting | Default | Effect |
|---|---|---|
| `min_untransformed_licks_cutoff` | 20 | removes a chamber whose sucrose or yeast well has fewer licks than this over the whole recording, counted before any transform |
| `max_med_duration_cutoff` | 13.0 | removes a chamber whose median feeding-event duration at either well is above this (a sign of a stuck or bleeding signal) |
| `max_events_cutoff` | 150000 | removes a chamber with an implausible number of events at either well |
| `require_training_complete` | true | removes **both** chambers of a group whose paired fly never finished training; a generation-2 group, which has no training information, is kept |
| `exclude_failed_pr_groups` | true | removes **both** chambers of a group that fails the light QC |

The optogenetic light QC has its own switch, `exclude_failed_opto_chambers`,
in the optogenetic table below. It is off by default.

### Light QC thresholds

| Setting | Default | Meaning |
|---|---|---|
| `pr_lick_free_run` | 5 | this many lick-free Test light events **in a row** fails the group as self-triggered |
| `pr_trend_min_events` | 5 | the fewest Test light events needed to judge the lick trend |
| `pr_trend_min_rho` | 0.3 | the licks-per-event trend must reach this rank correlation, or the group gets a warning |
| `pr_resting_level_rise` | 15 | a rise in the sucrose well's resting signal of this many counts is a warning |
| `pr_resting_level_ratio` | 3 | a sucrose well resting this many times higher than the DFM's other sucrose wells is a warning |

### Optogenetic light QC thresholds

Every optogenetic experiment, PR or not, also gets the general light QC of
section 5.2. Its settings, with their defaults:

| Setting | Default | Meaning |
|---|---|---|
| `optogenetics` | `auto` | run it when `Program.txt` or light data exist; `true` always, `false` never (a design key, and a per-DFM one) |
| `exclude_failed_opto_chambers` | false | remove the chambers of a failed linkage group; off, they are flagged and kept |
| `opto_unexplained_warn_fraction` | 0.10 | a group whose lit time is this fraction unexplained by licks gets a warning |
| `opto_unexplained_fail_fraction` | 0.30 | this fraction fails the group |
| `opto_unexplained_min_sec` | 30 | seconds of unexplained light needed before either is judged |
| `opto_default_decay_ms` | 1000 | the light's Hold assumed without `Program.txt` |
| `opto_decay_tolerance_samples` | 2 | slack, in samples, around the Hold |
| `opto_unlit_feeding_fraction` | 0.50 | in a closed-loop interval, this share of feeding bouts that never lit the group is a warning |
| `opto_open_loop_min_lit_fraction` | 0.95 | an open-loop interval lit for less than this share of its time is a warning |
| `opto_event_disagreement_warn_fraction` | 0.25 | firmware 4.0.0: a paired sucrose well whose firmware-counted feeding bouts and pyflic's differ by more than this share is a warning |
| `opto_yoking_fail_fraction` | 0.01 | firmware 4.0.0: a group whose yoked light differs from the paired light by more than 1 ms in more than this share of its lit records fails |
| `opto_lost_records_warn` | 25 | firmware 4.0.0: more records lost than this is a warning for the DFM |
| `opto_unknown_rows_warn_fraction` | 0.01 | firmware 4.0.0: more than this share of rows under an instruction outside the program is a warning for the DFM |
| `opto_late_records_warn` | 10 | firmware 4.0.0: more late records than this is a warning for the DFM |

The last five apply only to firmware 4.0.0 recordings, and their defaults
have no real recording behind them yet. [Checking your data](qc-user-guide.md),
section 6, describes the checks these settings drive.

This type owns its phases, so its design never states `facet_cutoffs` or
`facet_source`.

### Breaking point

| Setting | Default | Meaning |
|---|---|---|
| `pr_break_gap_min` | 120 minutes | the pause that counts as "the fly stopped". It is used for both the breaking point and sucrose persistence |
| `pr_test_window_min` | off | caps every group's Test window at the same length |

**Choosing `pr_break_gap_min`.** The breaking point moves with this value,
so pyflic always shows every group's breaking point at 60, 120 and 240
minutes beside your setting (in `summary.txt` and the *Breaking point CSV*
log). Look at that table **before** you settle on a gap:

- If the ranking of treatments is the same at every gap, the result is
  robust.
- If it changes, report that.

Pick the gap on biological grounds, such as how long a fly normally goes
between feeding bouts, and not by choosing whichever value gives the
smallest p-value. pyflic does not know the time of day, so a long night
pause ends a count like any other.

**Choosing `pr_test_window_min`.** Each group is watched from its own
training end to the end of the recording — on firmware 4.0.0, to the end of
the ratio Paradigm's run — so a group that trained late gets less Test time
and is more likely to be censored (section 5.6). The
`TestMinutes` column of `pr_breaking_point.csv` shows each group's window.
If those windows differ a lot, set `pr_test_window_min` to a value no longer
than the shortest one: every group is then judged over the same span. It
must be comfortably longer than `pr_break_gap_min`, or almost every group
will be censored.

### Figures

The cumulative-curve actions (*Cumulative difference curve*,
*Training-aligned traces*) take a **bin size**, default 1 minute. It changes
only the smoothness of the curve, not any statistic.

---

## 5. The analyses

### 5.1 Training

Where a group's **training end** comes from depends on the recording's
generation (section 2).

**Generation 1.** The training end is the last minute its paired fly's
sucrose well carries the firmware's training flag. The other three wells of
the group normally clear at the same moment. If they don't, the difference
appears as a *training-flag note* in `summary.txt` and the report. These
notes are QC information, not errors: the analysis always follows the
paired sucrose well.

**Generation 3.** The firmware records each well's **Phase**: `A` while the
well is in **Acclimation**, its opening run of closed-loop light events, and
`M` (Main) after. The training end is the paired sucrose well's first row in
`M` under the ratio Paradigm. Everything before it is Training, including a
ClosedLoop interval that ran before the ratio Paradigm. The other three
wells are `Off`, read `M` throughout and say nothing, so there are no
per-well notes. The notes say instead:

- *Training was empty*, when the ratio Paradigm had no Acclimation and no
  interval before it. Training then ended at the program's first row, and
  the group counts as having completed it.
- why Training never completed: the paired sucrose well never ran a ratio
  Paradigm, was still in Acclimation when the recording ended, or never
  reached `M` under one;
- *Paradigm restarted at Program Interval k*, when the well went back into
  Acclimation later. The firmware starts a well afresh whenever the Paradigm
  changes name.

**Generation 2** records no Training at all. Nothing is removed for it:
each group becomes one phase, `Recording`, with no Test, so no breaking
point and no sucrose persistence, and it is never pooled with other
members' Test. `TrainingComplete` is `NA`. `summary.txt`, the report's cover,
the Hub's **Loaded** line, the Project Report's member table and the Stats
text all say *no training information: recorded with DFM firmware older than
4.0.0*.

A group whose paired fly **never finished training** has no Test phase. It
appears as `TrainingComplete = false`, and by default both its chambers are
removed.

**Where to look:** the report's *Progressive ratio: training* table (one row
per group, with its training end) and the training notes beneath it. On a
firmware 4.0.0 recording the Program timeline (section 6) shows each well's
Acclimation directly.

### 5.2 Light QC: did the paired fly earn its light?

The firmware switches the light on from its own live reading of the paired
sucrose well. pyflic counts licks afterwards, from a cleaned-up signal.
Usually the two agree. When a sucrose well's resting signal slowly creeps
up, however, the firmware sees a well that is constantly touched and fires
the light on its own. pyflic sees a flat signal and no licks. The light
then describes the sensor, not the fly, and every number built on it is
meaningless. The light QC catches this, per group, over the whole
recording.

A **light event** is one onset of the group's light. On an older recording
it is read from `OptoCol1`, which samples the light five times a second. On
a firmware 4.0.0 recording it is an **Activation** of the paired sucrose
well: the firmware's own record of each light it switched on for that well,
exact to the record.

| Check | What it means | Verdict |
|---|---|---|
| **Self-triggered light** | 5 (`pr_lick_free_run`) or more Test light events in a row with no sucrose lick since the previous one | **fails** the group |
| **Implausible training** | training "completed", with light events, but without a single sucrose lick | **fails** the group |
| **No increasing trend** | licks per light event don't rise across the Test phase, as a working progressive ratio should | warning |
| **Resting level rise** | the sucrose well's resting signal rose during the recording | warning |
| **Resting level elevated** | the sucrose well rests well above the DFM's other sucrose wells | warning |

Some behaviour here is normal and is not flagged:

- **An occasional lick-free light event.** The firmware responds to brief
  touches below pyflic's feeding threshold. That is why only a *run* fails
  a group.
- **Fewer training licks than training light events**, for the same
  reason. Only *zero* licks is implausible.
- **A group with no Test light events at all** simply stopped before its
  first Test requirement. That is a breaking point of 0, not a failure.

A failed group is removed by default. `pr_light_qc.csv` still lists it, and
the QC figures keep it on screen with **EXCLUDED** and the reason in its
panel title, so you can check the decision. Warnings never remove a group;
read them as reasons to look at the QC figures.

If you would rather judge a failed group yourself, `LickFreeRunStartMin` in
`pr_light_qc.csv` is the minute after training end at which its failing run
began. Two ways to use it:

- set `exclude_failed_pr_groups: false` and cap the analysis with
  `pr_test_window_min`;
- exclude the chambers by hand.

Whichever you choose, apply the same rule to every group, whatever its
treatment.

**Lick-free allows for the Hold.** The firmware keeps the light on for its
*Hold* after the contact that earned it (the old programs' *decay*), and a
brief touch it counts may read below pyflic's feeding threshold. A light
event is therefore lick-free only when it has no sucrose lick since the
previous one *and* no sucrose lick or touch within its Hold — the one
`Program.txt` states, or `opto_default_decay_ms` without it. A light the fly
touched for is never counted against it, and the breaking point counts it.

**The firmware's own count, on firmware 4.0.0.** The firmware counts the
feeding bouts it saw at the paired sucrose well, its **Firmware Events**, and
records how many each light event needed. pyflic measures their trend across
the Test, `TrendRhoFirmware` in `pr_light_qc.csv`, beside the trend of
pyflic's licks. The *no increasing trend* warning stays on pyflic's licks.
When the firmware's count rises and pyflic's licks do not, the group gets a
note instead: *the firmware counted rising Events per light event; pyflic's
licks did not follow: check detection*. The fly worked to the schedule, and
pyflic's detection missed some of it. Under a fixed ratio the requirement
never rises, so no trend is judged at all.

**The general optogenetic light QC runs beside this one.** It asks a
simpler question of every linkage group — here, every chamber group — from
lit *time* rather than light events: how much of the light had no lick or
touch behind it? With `Program.txt` it also re-runs the firmware's own
trigger on the raw signal, so a well the firmware read as touched while
pyflic saw nothing is named as a drifting baseline. The two checks can
disagree. On the first real dataset, a group lit for four hours during
training passes this check, because one long light event is not a run of
lick-free events, and fails the general one, because 93% of those four
hours had no lick. On a firmware 4.0.0 recording the general check also
confirms the yoking: the yoked chamber's wells must count no light events of
their own and get exactly the paired well's light, or the group fails for
*broken yoking*. A group the general check fails is flagged, not removed,
unless you switch on `exclude_failed_opto_chambers`. Its results are in
`qc/opto/`, an *Optogenetic light QC* section of `summary.txt` and of the
report, and the **Light explained by licks (QC)** figure. The QC Viewer's
**Opto Light QC** tab shows the same verdicts group by group, says why each
group got its own, recomputes them when you change a detection parameter,
and can tick a failed group's chambers for exclusion. Every check it makes,
and how to read its figure, is in [Checking your data](qc-user-guide.md),
section 6.

### 5.3 Exclusions

Chambers leave the analysis for three kinds of reason:

- **By hand**, in `remove_chambers.csv`.
- **A chamber-level cutoff:** too few licks, an implausible duration or an
  implausible event count. Only that chamber is removed.
- **A group-level failure:** training never completed, or the light QC
  failed. Both chambers are removed.

A linkage group that fails the optogenetic light QC is flagged, not
removed, unless you switch on `exclude_failed_opto_chambers`. Here a
linkage group is a chamber group, so its failure would remove both
chambers too.

Every automatic removal and its reason is written to `removed_chambers.csv`
and listed in `summary.txt`. The Project gathers them all into
`<project>_Excluded.csv`.

A group needs **both** of its chambers for anything that compares paired
with yoked. If one chamber is removed, its partner still appears in the
per-chamber tables, but the whole group drops out of the difference table,
the difference curve and the breaking point.

### 5.4 The paired − yoked difference

For each group and each phase (Training, Test), pyflic subtracts the yoked
fly's value from the paired fly's, for each metric:

| Column | Paired − yoked … |
|---|---|
| `dLicksA`, `dLicksB` | sucrose licks, yeast licks |
| `dEventsA`, `dEventsB` | sucrose feeding events, yeast feeding events |
| `dPI`, `dEventPI` | preference index (by licks, by events) |
| `dMedDurationA`, `dMedDurationB` | median feeding-event duration |
| `dPersistA` | sucrose persistence (section 5.7), Test rows only |

Positive means the paired fly did more. **Zero is the null hypothesis:** the
contingency made no difference beyond the light itself. The file is
`paired_yoked_diff.csv`, one row per group per phase. The reports use the
**Test** phase, where the requirement is rising.

### 5.5 The cumulative difference curve

This is the difference as it builds up over time: for each group, paired
minus yoked cumulative sucrose licks, minute by minute from training end.
Per treatment, pyflic draws the mean ± SEM across groups, over the span of
time that **every** group covers, so the curve never jumps when one group's
recording ends. The individual groups are drawn faintly behind it.

### 5.6 The breaking point

*How far did the paired fly keep working?*

pyflic reads the paired fly's Test light events in order from training end.
The fly is taken to have **stopped at its first pause longer than
`pr_break_gap_min`** (120 minutes by default). Pauses are counted from
training end to the first event, between events, and from the last event
to the end of the Test window.

The **breaking point** is the number of light events the fly completed
before that pause: the last ratio it met. Some details:

- **Only lick-backed events count.** A lick-free light event neither counts
  nor ends a pause, because a light with no lick is no evidence that the
  fly was still working.
- **A pause of exactly the gap does not end the count.**
- **`BreakMin`** is the minute, after training end, of the last event
  counted.
- **Censored (`n+`).** If no long pause came before the Test window ended,
  the fly was still working when the recording stopped. Its count is a
  **lower bound**, not a measurement. Tables write it as `12+`, the dot
  plot draws it as an open symbol, and the still-responding curve marks it
  with a tick.
- **The yoked fly has no breaking point.** Its light is its partner's, so
  there is nothing for it to have worked for.
- **The unit is light events, not licks.** Before firmware 4.0.0 the
  firmware's schedule isn't recorded in the data, and `LargestRequirement`,
  the most licks credited to one counted event, is given as a description
  only.

**The recorded Requirement (firmware 4.0.0).** A firmware 4.0.0 recording
states, for every light event, the **Requirement** it met: the number of
feeding bouts the firmware demanded for it. The breaking point is still the
count of lick-backed light events, because a light with no lick is still the
drifting-sensor signature. The Requirement is reported beside it:

| Column | What it is |
|---|---|
| `BreakRequirement` | the Requirement the last counted light event met: the ratio the fly reached, in the firmware's own units |
| `FirmwareEvents` | the feeding bouts the firmware counted for the counted light events |
| `ParadigmType` | the Test Paradigm: `ProgressiveRatio` or `FixedRatio` |
| `LargestRequirement` | the same as `BreakRequirement` here |

Both reports show the break requirement beside the breaking point, and the
Project Report adds its median per treatment.

**Fixed ratio.** Under a FixedRatio Test Paradigm every light event needs the
same number of feeding bouts. The same rule runs, and what it counts is the
activations the fly earned before its first long pause. `BreakRequirement` is
the constant ratio, no trend is judged, and the reports title the section
**Fixed ratio: activations earned** (the Project Report when every pooled
group ran a fixed ratio).

**The end of the Test window.** On a firmware 4.0.0 recording the Test ends
where the ratio Paradigm's run ends, not at the end of the recording. A
ClosedLoop interval after it is not Test. Only the first ratio run is the
Test: a later one is noted in `summary.txt`. `pr_test_window_min` caps the
window after that, and `TestMinutes` is each group's.

The file is `pr_breaking_point.csv`, one row per group, with `BreakingPoint`,
`BreakMin`, `Censored`, `TestMinutes`, `LargestRequirement`,
`BreakRequirement`, `FirmwareEvents`, `ParadigmType` and the group's light QC
result. A generation-2 group has no row: it has no Test. `pr_light_events.csv`
lists every Test light event, with a `Counted` column showing which ones make
up the breaking point; on firmware 4.0.0 each event also carries the
`Requirement` it met, the `FirmwareEvents` since the previous one and its
`Phase`. Use it to check any group by hand.

### 5.7 Sucrose persistence

The same rule applied to feeding, for **both** flies: the minutes from
training end to the fly's last sucrose feeding event before a pause longer
than `pr_break_gap_min`. It is censored the same way when the fly was still
feeding at the end of the window.

Because the yoked fly has it too, it has a paired − yoked difference,
`dPersistA`. `dPersistCensored` marks differences where either fly was
censored. Those differences are kept and flagged, not dropped, because in a
recording that ends during a feeding peak, dropping them would remove most
groups.

Persistence is in `PersistA` / `PersistACensored` on every per-chamber
summary row, and in `dPersistA` / `dPersistCensored` in the difference
table.

---

## 6. Reading the figures

### Results figures

**Cumulative difference curve** (`pr_cumulative_diff.png`). The line is each
treatment's mean paired − yoked cumulative sucrose licks since training
end, with the shaded band its SEM, over the time every group covers. The
faint lines are individual groups, and the dashed line is zero.

- A line climbing above zero means the paired flies worked for the light
  more than their yoked partners fed.
- A line that flattens shows when the difference stopped growing.
- A flat line near zero means no operant effect.
- Check the faint lines: one extreme group can carry a mean.

**Paired − yoked dot plots** (reports). One point per chamber group, for
Test-phase `dLicksA`, `dPI` and, when present, `dPersistA`, with the
treatment mean ± SEM and a line at zero. Points mostly above zero support a
paired > yoked effect. Compare how far the treatments sit from zero, not
only from each other.

**Breaking point by treatment** (reports). One point per group, with mean ±
SEM. **Open symbols are censored**: the true value is at least that high.
If one treatment has many open symbols, its mean understates it. Under a
fixed ratio the section is titled *Fixed ratio: activations earned*, and
the points are the activations each fly earned before its first long pause.

**Light behaviour** (reports). One point per paired chamber for each of the
light table's headline measures — light events (Activations), lit time,
the firmware's feeding bouts and the end of Acclimation — by treatment,
with the treatment comparisons. On an older recording only lit time is
there.

**Still-responding curve** (`pr_still_responding.png`). For each treatment,
the fraction of paired flies that reached each ratio: 1.0 at ratio 0,
stepping down as flies stop. Ticks mark censored flies, which were still
responding when their window ended. The legend gives each treatment's *n*.

- A curve lying to the right of another means that treatment's flies kept
  working to higher ratios.
- This is the figure that treats censoring correctly. When many flies are
  censored, trust it over the dot plot.

**Breaking-point plots** (`breaking_point_dfm<id>.png`, from the Hub's
**Breaking-point plots** button and in the experiment report). One panel per
chamber, both roles, showing the licks between successive light onsets over
time since training end.

- Blue points are the events the breaking point counts.
- Grey points came after the break, or after the Test window.
- Hollow red rings are lick-free events, never counted.
- The dashed line marks the break. A censored group has no dashed line, and
  its strip reads `BP n+`.
- Groups removed by the light QC are drawn for reference, with
  "— excluded" in the strip and no break marked.

### Quality-control figures

**Licks per light event** (`pr_light_events_dfm<id>.png`). For each group,
the sucrose licks credited to each Test light event, in order.

- **A working progressive ratio climbs.**
- Hollow red rings are lick-free events; a run of them along the bottom is
  self-triggered light.
- The dashed line is the group's own trend. The grey line is the
  requirement pyflic estimates across the experiment, for reference.

**Sucrose Well resting level** (`pr_resting_level_dfm<id>.png`). For each
group, the paired sucrose well's resting signal over the whole recording,
against the median of the DFM's other sucrose wells. The rug along the
bottom shows light onsets, and the dashed line is training end.

- A well that creeps up while the rug gets denser is a sensor problem, not
  a motivated fly.
- This figure is usually the clearest explanation of a self-triggered
  failure.

**Training-aligned traces** (`pr_cumulative_licks_dfm<id>.png`). Paired and
yoked cumulative sucrose licks since each group's training end. Points mark
minutes with the light on; black rings mark lick-free light events on the
paired trace. Use it to see whether the light kept firing while the paired
trace went flat. That pattern is self-triggering.

Every QC figure's panel title gives the group's treatment and its light QC
result: *light QC ok*, *warning: …*, or *EXCLUDED: …*.

**Light explained by licks** (`qc/opto/opto_light_dfm<id>.png`). The
optogenetic light QC's figure: one row per group, with its wells and its
optogenetic verdict in the strip. The left panel is the group's lit time
per bin, 10 minutes when basic analysis draws it: grey-blue where a lick or
touch at the paired sucrose well explains it, and red where nothing does.
The right panel is orange where the firmware saw contact and pyflic saw
nothing: on an older recording, drawn when `Program.txt` is in `data/`, the
time pyflic's re-run of the firmware's test read the well as touched; on a
firmware 4.0.0 recording, the light of the light events the firmware
switched on with no lick or touch at their onset.

- Red beside orange in the same bins is a drifting well: the light
  followed the sensor.
- Red with no orange is light the firmware had no reason to switch on.
- [Checking your data](qc-user-guide.md), section 6.7, covers the other
  colours.

**Program timeline** (`qc/program/program_timeline_dfm<id>.png`; firmware
4.0.0 recordings, or older ones with `Program.txt`). For one DFM, the
program it ran — a band of intervals coloured by Paradigm, such as the
ClosedLoop opening and then `PR10` — above one lane per well. Each paired
sucrose well's lane shows its Acclimation shaded, its light events as ticks
and its light as a blue strip; its yoked partner's lane should show the same
strip and no ticks.

- The shading should end in the first interval: that is the training end.
  A well shaded to the end never finished training.
- Ticks thin out as the requirement rises. A dense comb of ticks while the
  paired fly's licks are flat is self-triggered light.
- A yoked lane with ticks, or a different strip, is broken yoking.
- [Checking your data](qc-user-guide.md), section 6.8, covers the rest.

---

## 7. Statistics and inference

### The unit of analysis

**One observation per chamber group.** Paired and yoked flies are never
entered as separate observations in the main tests. The yoked fly is the
paired fly's control, and pooling them would average an effect with its own
control.

### The tests

| Question | Test | Where |
|---|---|---|
| **Is the paired fly different from its yoked partner?** | Each treatment's Test-phase differences against zero: the paired t-test (a one-sample t-test on the differences), with the Wilcoxon signed-rank test beside it; in a Project, also a mixed model's intercept | both reports; `<project>_Stats.txt` |
| **Do treatments differ in the paired − yoked difference?** | Welch's t-test for two treatments, Tukey HSD for three or more; in a Project, also a mixed model | both reports; `<project>_Stats.txt` |
| **Do treatments differ in breaking point?** | The same tests on `BreakingPoint`, plus a pairwise **log-rank test** on the ratio reached | both reports; `<project>_Stats.txt` |
| **What fraction of flies reached each ratio?** | Kaplan-Meier estimate (the still-responding curve) | both reports; `pr_still_responding.png` |

The per-chamber pooled tests from the standard two-well analysis are still
reported, as a secondary section.

In a Project with two or more members, the **mixed model** treats each
experiment, and each DFM within it, as a source of variation of its own
(DFM nested within Experiment). It is reported beside the pooled p-value.
**When they disagree, prefer the mixed model**: it doesn't treat groups on
the same device, or in the same recording, as independent.

### What a result lets you say

- **A difference above zero in the paired flies** (for example `dLicksA`
  in the Test phase) supports the light acting as a reinforcer. The paired
  fly fed more when feeding produced the light than a fly given the same
  light regardless. The yoked design controls for the light's direct
  effects on feeding, but only when both flies of a group were treated
  identically in every other way.
- **A higher breaking point** means the paired flies kept working to
  higher requirements, a measure of how much effort the light was worth.
  There is no yoked comparison for it. Compare treatments with each other,
  and keep the dot plot and the still-responding curve side by side.
- **A difference between treatments in the paired − yoked difference**
  means the treatment changed how reinforcing the light was, not merely
  how much the flies fed.

### Cautions before you conclude

1. **Censored breaking points.** The t-test, Tukey and the mixed model
   enter a censored count as if it were the true value, which **biases
   that treatment's mean downward**. The log-rank test and the
   still-responding curve treat censoring correctly. Count the censored
   groups per treatment (open symbols, `n+`). When censoring is common or
   uneven between treatments, base the conclusion on the log-rank test and
   the curve, and consider a longer recording.
2. **The gap setting.** Check the sensitivity table (60 / 120 / 240
   minutes). A conclusion that holds at only one gap is weak and should be
   reported as such.
3. **Unequal Test windows.** Groups that trained late had less Test time.
   If `TestMinutes` varies widely, set `pr_test_window_min` so every group
   is judged over the same span.
4. **Independence in a single experiment.** In one experiment's report, the
   three groups on a DFM are treated as independent although they share a
   device. The mixed model that accounts for this runs only across two or
   more members, so replicate across recordings and pool them in a
   Project.
5. **Multiple comparisons.** The reports test several metrics
   (`dLicksA`, `dLicksB`, `dEventsA`, `dPI`, `dMedDurationA`, `dPersistA`,
   and `dEventsB` in a Project) without correction. Tukey HSD corrects
   within one metric; the log-rank tests are **not** corrected between
   treatment pairs. Decide your primary measure before you look, and treat
   the others as supporting.
6. **Exclusions can bias a comparison.** If the light QC or training
   removes more groups from one treatment than another, the remaining
   groups may not be comparable. `<project>_Excluded.csv` and the report's
   exclusion table give the counts. Report them per treatment.
7. **Lick detection matters.** Whether a light event counts depends on
   pyflic detecting at least one lick. Detection parameters that miss
   brief licks turn real responses into lick-free events. That lowers
   breaking points and can trigger the self-triggered check. Keep detection
   parameters identical across the Project, and look at the QC figures
   when many lick-free events appear.
8. **Sucrose persistence differences can be differences of lower bounds.**
   Rows with `dPersistCensored = true` are kept. If many are censored,
   interpret `dPersistA` cautiously.

### What to report

- The number of chamber groups per treatment, before and after exclusion,
  with the reasons.
- `pr_break_gap_min`, `pr_test_window_min` (if used), and the detection
  parameters.
- The number of censored groups per treatment.
- For the breaking point: the still-responding curve and the log-rank test,
  with the mean comparison as secondary.
- For the paired − yoked difference: the test against zero within each
  treatment, and the between-treatment comparison.
- Whether the conclusion survives the breaking-point sensitivity table.
- For pooled data: the mixed-model p-values.

---

## 8. Quick troubleshooting

| You see | Likely cause | What to do |
|---|---|---|
| Every group removed, with "training never completed" | a v2 file or no light data: no training flags | check the DFM files are version 3 with `OptoCol1` |
| "no training flag on any well of group *g*" | same as above, or the run never entered training | as above |
| "no training information: recorded with DFM firmware older than 4.0.0" | PyMCU 4.0.0 recorded a DFM whose firmware was not updated: there is no record of Training | nothing is removed; each group is one `Recording` phase with no breaking point. Update the DFM's firmware for the next recording |
| "firmware 4.0.0 recording without Program.txt" | the program was not copied into `data/` | copy the `Program.txt` PyMCU exported for this recording and run again; without it a fixed ratio is taken as progressive |
| "paired Sucrose Well W*n* never reached Phase M under a ratio Paradigm" | the fly never finished Acclimation, or the ratio Paradigm never ran | check the Program timeline; the group is removed like any group that never finished training |
| "Training was empty" | the ratio Paradigm had no Acclimation and nothing ran before it | nothing: Training ended at the start, and every light event is Test |
| "Paradigm restarted at Program Interval *k*" | a later interval named a different Paradigm, so the firmware started the well afresh | check the program was the one you meant; only the first ratio run is the Test |
| A group failed for **broken yoking** | the yoked chamber's light differed from the paired chamber's, or a yoked well counted light events of its own | check the lid's wiring and the program's linkage; the yoked fly did not get its partner's light |
| "the firmware counted rising Events per light event; pyflic's licks did not follow" | the fly worked to the schedule, and pyflic's detection missed some of its feeding | look at the paired sucrose well's baselined trace and the detection parameters |
| A group failed for **self-triggered light** | the sucrose well's resting level drifted, so the light fired on its own | look at *Sucrose Well resting level*; the group is correctly excluded |
| A group failed for **implausible training** | training was completed by the sensor, not the fly | check the well and the fly; the group is correctly excluded |
| Almost every breaking point is censored (`n+`) | the Test window is short compared with `pr_break_gap_min` | record longer, or reconsider the gap; don't shorten the gap to get a result |
| A group is missing from the difference table | one of its two chambers was removed | see `removed_chambers.csv` |
| The Project Report says a member has no breaking point table | that member was analysed with an older pyflic | re-run its basic analysis |
| Loading fails on `paired_chambers` | missing, two chambers from one group, or a group left out | name exactly one chamber from each of 1–2, 3–4, 5–6 |
| Loading fails on treatments | the two chambers of a group have different treatments | give both chambers the same treatment |
| A linkage group failed for **unexplained light** | most of its lit time had no lick or touch behind it | open *Light explained by licks*: orange beside the red is a drifting well, no orange is a light the firmware had no reason to switch on |
| "holds more than one Program.txt" | two program files in `data/` | keep only the one the MCU exported for this recording |
| `summary.txt` says `paired_chambers` disagrees with `Program.txt` | the config names a different paired chamber than the program's trigger well | check which chamber the program lit for; fix the config or the program |
