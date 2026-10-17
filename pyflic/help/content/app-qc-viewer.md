# QC Viewer

```bash
pyflic qc my_experiment/
```

The QC viewer is where you decide whether to believe your results. It shows the signal
pyflic worked from and the events it found, so you can check that detection agrees with
what you would have called by eye.

Do this before running statistics, not after. Detection parameters that are wrong for your
data produce output that looks entirely plausible.

Opened from the Hub's QC panel, the viewer starts directly on the member the Hub already
loaded — no second load. The **Run QC** button in the top bar computes the QC bundle for
that experiment (integrity, data breaks, bleeding, and the raw / baselined /
cumulative-licks plots) and refreshes the DFM tabs in place, so the plots appear without a
round-trip back to the Hub; progress streams to the Load tab's log, and unsaved exclusion
checkboxes survive the refresh. Loading from the Load tab runs the same QC as part of the
load.

## Tabs

| Tab | Shows |
|---|---|
| **Load** | Load the experiment and choose the time range |
| **Feeding Summary** | The per-chamber summary table |
| **DFM *n*** | One tab per device, with per-well traces |
| **Opto Light QC** | Optogenetic experiments only: was the light where the licks were? |
| **Params** | Detection parameters, with live recompute |

Each **DFM** tab has its own sub-tabs:

- **Integrity** — data continuity: gaps, breaks, lost and repeated records, error flags,
  and anything odd about the recording. Below the report, the recording's `Messages.csv`
  for this DFM and the MCU, when `data/` holds one.
- **Sim. Feeding** — samples where both wells of a chamber registered feeding at once,
  before and after the dual-feeding correction. This is your window onto electrical
  crosstalk; see [dual-feeding correction](concepts-two-well-pi.md#dual-feeding-correction).
- **Bleeding** — signal bleeding between wells.
- **Raw Signal**, **Baselined** and **Cumulative Licks** — the saved QC plots from `qc/`,
  once QC has run.
- **Program** — the Program timeline and each well's Paradigm state, for a DFM with
  firmware 4.0.0 data or a `Program.txt` section. See [below](#the-program-sub-tab).

### The messages table

PyMCU writes `Messages.csv` beside the data: what the MCU logged while it recorded. The
Integrity sub-tab lists the messages of this DFM and of the MCU itself (DFM 0), with their
time, the record `Index` they refer to, the text and the type, and counts the errors in its
title. *Skipped index* is a lost record; a DFM error code points at the `Error` column. The
integrity report lists the same errors.

### The Program sub-tab

The [Program timeline](plots-catalog.md#program-timeline) fills the top: the Program
Intervals coloured by Paradigm type, and per well its Acclimation, its Activations and its
light. Below it, a table with one row per well at the end of the loaded range:

| Column | What it holds |
|---|---|
| `Well`, `Chamber`, `Role` | the well, its chamber and the chamber's [Role](concepts-optogenetics.md#roles) |
| `Paradigm` | the Paradigm in force on the last row |
| `Phase` | `A` while in Acclimation, `M` after |
| `AcclimationEndMin` | the minute the well left Acclimation |
| `Activations` | Activations so far |
| `Requirement`, `Progress` | under a ratio Paradigm: the Firmware Events the next Activation needs, and how many it has |
| `LitSec` | seconds its LED was on over the loaded range |

On a recording older than firmware 4.0.0 the timeline is laid out from the program's clock
times, and only `Paradigm`, `Role` and `LitSec` can be filled. The sub-tab is computed from the
loaded experiment, not read from `qc/`, so a **Params** recompute redraws it.

A Progressive Ratio experiment's own QC — the light QC table and its figures — is on the
Hub's QC panel rather than here; see
[Light QC](concepts-progressive-ratio.md#light-qc). The Feeding Summary tab shows its
`Group`, `Role` and light QC columns like any other.

## The Opto Light QC tab

Shown for an optogenetic experiment of any type: one row per linkage group, with its
chambers and their `Roles` (`1 Paired, 2 Yoked`), its lit time, the share of it no
trigger-well lick or touch explains, the minute that began, the contact with no lick — the
emulated firmware trigger's, or on firmware 4.0.0 data the light of Activations with no lick
or touch at their onset — and the verdict, coloured by tone. The tab opens on the worst
group. Selecting a group fills the panes below it:

- **Why** — the verdict, a line per flag with its numbers and likely cause, and the notes
  about its DFM and its program.
- **Intervals**, **Light events** and **Program** — the group's rows of the tables in
  `qc/opto/`, and its DFM's program as read. A column empty on every row — a setting none
  of the DFM's Paradigms has, a firmware column on an older recording — is hidden.
- The **Light explained by licks** figure — the selected group's panels, or the whole DFM
  with **Selected group only** unticked, at the bin size you choose.

The tab is computed from the loaded experiment, not read from `qc/opto/`, so a **Params**
recompute updates its verdicts at once: a threshold that loses real licks makes healthy
light look unexplained, which is worth seeing before you commit to it.

**Mark Selected Group Excluded** and **Mark Failed Groups Excluded** tick the chambers of
those groups on the Feeding Summary and DFM tabs. They save nothing: a failed light does not
invalidate the feeding record, so whether to exclude is yours to decide, and **Save
Exclusions…** records the decision. See
[Optogenetic experiments](concepts-optogenetics.md).

## What to look for

**Does the baseline sit where it should?** It should track the background and ignore
feeding. A baseline that visibly rises during long bouts means the running median is being
pulled up by the feeding itself — see [the baseline](concepts-signal.md).

**Does detection match the visible bouts?** The plots do not mark individual events, so set
a well's **Baselined** trace, with its threshold lines, beside its **Cumulative Licks**
curve, which climbs only where licks were detected. Climbs where the trace is flat mean the
thresholds are too low. Clear deflections with no climb mean they are too high.

**Are bouts being split or merged?** The plots cannot show this, but the Feeding Summary
can: many short events per chamber suggest the link gap is too small, and a few very long
ones that it is too large. This is the single most common cause of surprising duration and
event-count results — see [event linking](concepts-licks-events.md#event-linking-the-link-gap).

**Are some wells dead?** A well with no signal at all is an empty position or a hardware
fault. Exclude it rather than letting a zero into your averages.

## The Params tab

Change a detection parameter and recompute without editing your configuration or
restarting. This is the right way to choose parameter values: try one, look at the traces,
try another.

The workflow that works:

1. Open a DFM tab and find a chamber whose behaviour you can interpret by eye.
2. Change one parameter in **Params** and recompute.
3. Look at whether detection now matches your reading of the trace.
4. When it does, write that value into your configuration file — **the Params tab does not
   save it for you.**

Each parameter has a `?` button that opens
[Parameter reference](reference-parameters.md) at that parameter.

Changing parameters here affects only this session. It is a place to experiment, not a
place to configure.

## Saving exclusions

On the **Feeding Summary** tab, tick the chambers to exclude — **Mark All Excluded** and
**Clear All** set every box at once. **Save Exclusions…** writes your current selection to a
named group in
`remove_chambers.csv`. That is the intended path from "this chamber looks wrong" to a
recorded, reusable exclusion set — see
[exclusions](config-dfms-chambers.md#excluding-chambers).

Name the group after the analysis it belongs to. A script's bare `remove_chambers` step
looks for a group named after the script.

## Auto Filter

**Auto Filter** applies the cutoffs from `global.constants` to select chambers
automatically — for a Progressive Ratio experiment, that includes the chamber groups whose
training never completed or whose light QC failed. **View Criteria** shows what the last run
used and why each chamber was selected. Review the selection before saving — automatic
criteria are a starting point, not a verdict.

---

Related: [How feeding is detected](concepts-licks-events.md) ·
[Parameter reference](reference-parameters.md) · [Analysis Hub](app-hub.md)
