# Checking your data: quality control in pyflic

A guide for researchers analysing FLIC recordings with pyflic. It explains
every quality-control (QC) check pyflic runs, the files and figures each one
writes, how to read them, and how to decide which chambers to leave out.

Sections 1 to 5 apply to every experiment. Section 6 adds the light QC of
optogenetic experiments, section 7 the checks of a Progressive Ratio
experiment, and section 8 what a Project does with its members' QC.
Section 9 is a checklist to work through for each recording.

You do not need to read code to use it. For installing and starting pyflic,
see [Getting Started](GETTING_STARTED.md). For the Progressive Ratio assay
itself, see [Analysing a Progressive Ratio assay](progressive-ratio-user-guide.md).
The in-app help (`pyflic help`, or **F1** in any window) covers the same
ground as a concise reference. Its reading path *Checking your data* starts
from the QC Viewer.

---

## 1. What QC is for

Every number pyflic reports rests on two things: the signal each well
recorded, and the licks pyflic detected in it. Both can go wrong in ways
that still produce plausible results. A well whose background drifts,
thresholds that miss brief licks, two wells that pick up each other's
signal: none of these stops an analysis, and each one changes its numbers.

QC asks five questions:

| Question | Where to look | Section |
|---|---|---|
| Did the recording run cleanly? | the integrity report and the data breaks | 3.1, 3.2 |
| Does detection agree with what you would call by eye? | the signal plots and the QC Viewer | 3.3, 4 |
| Are the two wells of a chamber independent? | simultaneous feeding and bleeding (two-well) | 3.4, 3.5 |
| Is each chamber a usable fly? | the exclusion cutoffs and your own inspection | 5 |
| Was the light where the licks were? | the optogenetic light QC | 6 |

Three rules run through everything:

- **Do QC before statistics.** Once you have seen a result, every exclusion
  looks like a choice made for it.
- **Most checks flag; you decide.** Only the design's exclusion cutoffs
  remove chambers on their own. Everything else is information for your
  judgement.
- **Apply one rule to every chamber, whatever its treatment.** A rule
  applied to one treatment only biases the comparison.

---

## 2. Running QC

### Where QC runs

| How | What it writes |
|---|---|
| **Hub → QC → QC reports** | the **QC bundle**, into the member's `qc/` folder: the integrity report, the data breaks, the three signal plots, the two-well crosstalk tables, and when the member is optogenetic the light QC and the Program timeline of each DFM that has one |
| **Hub → Analyze → Basic analysis** | auto-removal, `summary.txt` and the feeding summaries. It skips the QC bundle, which is the slow part, but it writes the optogenetic light QC, the light table, the Program timeline of each firmware 4.0.0 DFM of an optogenetic member, and a Progressive Ratio experiment's own light QC |
| **QC Viewer** | loading a member on its **Load** tab writes the QC bundle. Opened from the Hub, the viewer starts on the member the Hub already loaded, and **Run QC** in its top bar writes the bundle |
| **PDF report** | nothing into `qc/`. The report computes its integrity and crosstalk tables from the loaded recording, never from an old `qc/` folder |
| **Scripts** | `run_qc` writes the QC bundle. `basic_analysis` skips it, as on the Hub |

From Python, `execute_basic_analysis()` writes the QC bundle too, unless you
pass `skip_qc=True`.

The QC bundle describes the detection parameters in force when it was
written. **Write it again after you change a parameter**, or the baselined
plot will show thresholds you no longer use.

### What goes where

```
my_experiment/
  remove_chambers.csv        exclusions you declare (section 5)
  qc/
    integrity/               DFM1_integrity_report.csv and .txt
    data_breaks/             DFM1_data_breaks.csv, only when there are breaks
    raw_signal/              DFM1_raw.png
    baselined/               DFM1_baselined.png
    cumulative_licks/        DFM1_cumulative_licks.png
    simultaneous_feeding/    DFM1_simultaneous_feeding_matrix.csv   (two-well)
    bleeding/                DFM1_bleeding_matrix.csv
                             DFM1_bleeding_alldata.csv               (two-well)
    opto/                    four tables and opto_light_dfm1.png     (optogenetic)
    program/                 program_timeline_dfm1.png               (optogenetic)
  analysis/
    removed_chambers.csv     what auto-removal took out, and why
    summary.txt              the run in text, with its QC sections
    experiment_report.pdf    the report, which opens with Quality control
    light_summary.csv, ...   the light table                         (optogenetic)
    pr_light_qc.csv, ...     Progressive Ratio (section 7)
```

Every file outside `qc/opto/` and `qc/program/` has one copy per DFM, named `DFM<n>_...`.

`summary.txt` always lists the chambers excluded and the chambers
auto-removal took out, and it has a light QC section for an optogenetic or
Progressive Ratio experiment. Its *QC summary* of integrity, data
breaks and crosstalk appears only when the QC bundle ran as part of basic
analysis, as it does from Python by default. The Hub's Basic analysis
leaves that section out; the report and `qc/` hold the same information.

---

## 3. The checks every experiment gets

### 3.1 Data integrity

For each DFM, the integrity report states:

| Item | What it is |
|---|---|
| Generation | which shape of data file the DFM wrote: 1, 2 or 3 (section 6.2) |
| Rows | the number of samples recorded |
| Start, end and elapsed time | the first and last sample's clock time, and the minutes between them |
| Elapsed from the `Minutes` column | the same span, from the file's own minute count |
| Error column | how many samples carry a non-zero firmware error code, and how many of each kind (below) |
| Index check | whether the device's record index rises by exactly 1 from each row to the next |
| Lost records | records missing from the index: how many, and for each gap the index before it, its minute and its length in seconds |
| Repeated records | records written twice, and dropped at load |
| Paradigm state | generation 3 only: the baseline rows before the program's first instruction, the rows under an instruction outside the program, the late records, and the Paradigm sequence — each Paradigm with its first and last minute and its rows |
| `Messages.csv` errors | the error messages the MCU logged for this DFM and for itself, when `data/` holds its `Messages.csv` |

**The error kinds depend on the generation.** The firmware's error byte has
eight bits, and the meaning of the two lowest changed:

| Bit | Generation 1 | Generations 2 and 3 |
|---|---|---|
| 0x01 and 0x02 | counted together as *No ACK / overflow*: the two firmware 2.0.0 builds used them differently, and the file does not say which wrote it | 0x01 *No Ack*: a request came before the last reply was acknowledged, and records were sent again; 0x02 *Overflow*: the DFM's record buffer overflowed and records were lost |
| 0x04 to 0x80 | PacketType, DMA_TX, DMA_RX, PacketSize, AIInterrupt and OInterrupt Error | the same |

**Lost and repeated records.** The DFM numbers its records from 1, one per
200 ms. A gap in that index is records the DFM could not keep while the MCU
was not reading it; they are gone, and PyMCU logs *Skipped index* in
`Messages.csv`. A repeated index with the same time is a block PyMCU wrote
twice after a failed file write: pyflic keeps the first copy, drops the
second at load, and `summary.txt` and the integrity report say how many. A
DFM that restarted and counts from 1 again, with new times, loses nothing.

**Where to look.** `qc/integrity/DFM<n>_integrity_report.txt` holds the full
text and the `.csv` beside it one row of numbers, the generation and the
lost, repeated, unknown-instruction and late records among them. The QC
Viewer's **Integrity** tab shows both, with the recording's `Messages.csv`
below. The report's *Data integrity* table gives each DFM a verdict: **ok**
when it has no data breaks, no error flags, no lost records and a continuous
index, and **warning** otherwise. The report's cover repeats the verdict
under *At a glance*.

**Reading it.**

- The two elapsed times should agree with each other and with how long you
  recorded. A DFM much shorter than the others stopped early.
- An index that does not rise by 1 means records are missing or repeated.
  Lost records leave a data break at the same minute (section 3.2).
- The error names are the firmware's. pyflic counts them but does not
  interpret them. *Overflow* beside lost records is the same event seen
  twice.
- **Nothing here removes a chamber.** A warning is a reason to look at the
  signal plots around the affected time, and to note it if that DFM's
  results stand out. On an optogenetic recording the light QC also warns
  about lost, late and unknown-instruction records (section 6.3).

### 3.2 Data breaks

A **data break** is a gap between two consecutive samples longer than four
sampling intervals: more than 0.8 seconds at the default 5 samples per
second. `qc/data_breaks/DFM<n>_data_breaks.csv` has one row per break: the
row that ended it, led by `BreakIndex`, its row number in the recording, and
`GapSeconds`, the length of the gap. The file exists only for a DFM that has
breaks. The report's integrity table counts them. (Older pyflic named these
two columns `Index` and `Interval`, which clashed with the data file's own
columns and stopped the check on recordings that had a break.)

- **A few short breaks change little.** Totals lose a second or two.
- **A long break removes that stretch from every chamber on the DFM.**
  Compare the DFM's recording length with the others', and treat
  time-binned results across the gap with care.
- **Breaks on one DFM only** point at that device or its connection, not at
  the flies.

### 3.3 The signal plots

Three figures per DFM, one panel per well. They are diagnostics, not
figures for a paper.

**Raw signal** (`qc/raw_signal/DFM<n>_raw.png`). Every well's signal as
recorded.

- A well that stays flat, with no deflections at all, is an empty position
  or a dead well.
- A background that creeps upward is drift. The baseline removes slow
  drift, as the next figure shows, but a well that drifts a lot is worth a
  second look.
- A sudden step in the background is a disturbance: a moved plate, a
  refilled well, a bubble.

**Baselined signal** (`qc/baselined/DFM<n>_baselined.png`). Every well after
pyflic subtracts a running median of the signal, its **baseline**, with two
red dashed lines: `feeding_threshold` (the upper line) and `feeding_minimum`
(the lower one). A feeding bout must reach the upper line, and its licks are
the samples above the lower one.

- **This is the most useful figure in the set.** It shows whether the
  thresholds sit in a sensible place for your data.
- The trace should sit near zero between bouts. A trace that dips below
  zero around long bouts, or long bouts that look flattened, means the
  baseline is being pulled up by the feeding itself; see *The raw signal and
  the baseline* in the help.
- Bouts that barely cross the upper line, or noise that often crosses it,
  both say the threshold needs a look. Try values in the QC Viewer
  (section 4) before changing the configuration.

**Cumulative licks** (`qc/cumulative_licks/DFM<n>_cumulative_licks.png`).
Each well's running lick total over time, drawn as the fourth root of the
total whatever `transform_licks` says. A two-well experiment has one row per
chamber, with well A on the left and well B on the right.

- A steady slope is steady feeding, a plateau is a fly that stopped, and a
  step is a burst.
- A curve that never leaves zero is a well with no licks. With a fly in the
  chamber, that fly did not feed there, or the well did not work.
- One chamber far steeper than its neighbours is either a heavy feeder or a
  signal problem. The baselined plot tells you which.

### 3.4 Simultaneous feeding (two-well)

A fly cannot drink from both wells of its chamber at once. Samples that
register a lick on both wells are therefore **crosstalk** between the wells,
or a fly bridging them. `qc/simultaneous_feeding/DFM<n>_simultaneous_feeding_matrix.csv`
has one row per chamber:

| Column | Meaning |
|---|---|
| `Licks1`, `Licks2` | lick samples at the chamber's lower- and higher-numbered well, after the correction |
| `Both` | lick samples on both wells at once, after the correction |
| `MaxMinSignalAtBoth` | across those samples, the largest value of the weaker well's signal |
| `HigherInCol1AtBoth` | how many of them had the lower-numbered well's signal higher |
| `Both_pre`, `MaxMinSignalAtBoth_pre`, `HigherInCol1AtBoth_pre` | the same three, before the correction |

The QC Viewer's **Sim. Feeding** tab shows the table, and the report's
*Simultaneous feeding* table gives each chamber's treatment, the lick samples
at each well, the samples on both wells **before** and **after** the
correction, and the count after it as a percentage of the chamber's lick
samples.

**The dual-feeding correction.** `correct_for_dual_feeding`, on by default in
two-well experiments, gives each such sample to the stronger well and
detects the licks again. The `_pre` columns are the crosstalk the detection
found; the columns without them are what the correction left, normally
zero. The lick counts are the ones each well kept. With the correction off
the two agree. State in your methods whether the correction was on.

Crosstalk left uncorrected pushes a chamber's preference index toward zero,
because the weaker well is credited with licks that belong to the stronger
one. The correction repairs most of that, but a chamber where crosstalk is
common deserves a look at its baselined trace.

### 3.5 Bleeding between wells (two-well)

**Bleeding** is one well's signal appearing in another well. For every well
in turn, pyflic takes the samples where that well's baselined signal is
above 50 and averages every well's baselined signal over them. The result is a 12 × 12
table in `qc/bleeding/DFM<n>_bleeding_matrix.csv`: a row per signalling well
(`W1Sig` …) and a column per responding well (`W1Resp` …).
`DFM<n>_bleeding_alldata.csv` is each well's mean baselined signal over the
whole recording, for comparison.

- The diagonal is each well responding to itself, which is large by
  construction. Ignore it.
- **Off the diagonal, every value should be near zero.** A well that rises
  while another is being fed from is picking up its signal.
- **The report's check.** For each DFM, the report's *Bleeding between wells*
  table names the largest response off the diagonal. It is a **warning** when
  that response is above `feeding_threshold`, because such a response would
  register as licks that never happened.

A bleeding warning is a reason to open the baselined plot of the responding
well and look at the moments the signalling well was fed from. Nothing is
removed automatically.

---

## 4. The QC Viewer

The QC Viewer is where you check detection against the trace. Open it from
the Hub's **QC** panel with **Open QC Viewer**, or from a terminal:

```
pyflic qc "path/to/my_experiment"
```

| Tab | Shows |
|---|---|
| **Load** | load an experiment and choose the time range; the log of every step |
| **Feeding Summary** | the per-chamber summary table, with a checkbox per chamber for exclusion |
| **DFM *n*** | one tab per device: **Integrity** (with the recording's `Messages.csv` below), **Sim. Feeding** and **Bleeding** (two-well), **Raw Signal**, **Baselined** and **Cumulative Licks**, and **Program** for a DFM with a program or firmware 4.0.0 data (section 6.8), with an **Exclude Wells** panel beside them |
| **Opto Light QC** | optogenetic experiments only (section 6.6) |
| **Params** | the detection parameters, with a live recompute |

### What to look for

The DFM tabs show the saved QC plots of section 3.3. They do not mark
individual events. Judge detection by setting a well's **Baselined** trace,
with its threshold lines, beside its **Cumulative Licks** curve, which
climbs only where pyflic detected licks.

- **Does the baseline sit where it should?** Between bouts the baselined
  trace should sit near zero.
- **Does detection match the trace?** Deflections that clear the upper line
  should appear as climbs in the cumulative curve. Climbs where the trace is
  flat mean the thresholds are too low. Clear deflections with no climb mean
  they are too high.
- **Are bouts split or merged?** The plots cannot show this, but the
  Feeding Summary can. Many short events per chamber suggest the link gap
  (`feeding_event_link_gap`) is too small, and a few very long ones that it
  is too large. This is the most common cause of surprising duration and
  event-count results.
- **Are some wells dead?** A well with no signal is an empty position or a
  hardware fault. Exclude it rather than let a zero into the averages.

### Trying parameters

The **Params** tab changes a detection parameter and recomputes the feeding
summary, without editing your configuration. Change one value, recompute,
look at a chamber you can read by eye, and repeat. When detection matches
your reading of the trace, write the value into the configuration. The
Params tab never saves it for you.

A recompute updates the Feeding Summary and the Opto Light QC tabs, and each
DFM tab's Program sub-tab. The DFM tabs' other plots are the images saved in
`qc/`, which do not change. **Run QC** after a
recompute writes the QC bundle under the parameters you are trying, not the
ones in your configuration. Write it again from the Hub once you have
settled on a value.

**Before you publish, sweep the parameter.** The Script Editor's *Parameter
sensitivity sweep* (`param_sensitivity`) re-runs the analysis over a list of
values and writes `analysis/param_sensitivity_<parameter>.csv`, with the
licks, events and median duration of each treatment at each value. An effect
that appears at only one link gap or one threshold is not a robust effect.

### Marking exclusions

On the **Feeding Summary** tab, tick the chambers to exclude, or use a DFM
tab's **Exclude Wells** panel, which ticks the chamber a well belongs to.
**Mark All Excluded** and **Clear All** set every box at once. **Auto Filter**
ticks the chambers the design's cutoffs would remove, and **View Criteria**
shows the rules it used and why each chamber was chosen. **Save Exclusions…**
writes your selection to a named group in the member's `remove_chambers.csv`.

The ticks are only a selection until you save them. Review Auto Filter's
selection before saving: automatic criteria are a starting point, not a
verdict.

---

## 5. Exclusions

An **excluded chamber** leaves every result: every summary, plot and
statistic. Chambers leave in two ways.

### By hand

Each member declares its own exclusions in a `remove_chambers.csv` at its
root:

```csv
group,dfm_id,chamber,note
general,1,3,low lick count
general,2,5,fly escaped
```

The `group` column lets one member keep several exclusion sets. The active
one is `general`, unless a Project's design names another with
`exclusion_group:`. The QC Viewer's **Save Exclusions…** writes this file
for you.

To declare many at once, put one exclusion sheet at the project or batch
folder and apply it; pyflic writes its rows into each member's file. See
*Excluding chambers in bulk* in the help.

### Automatically, by the design's cutoffs

Basic analysis applies the design's `constants:` cutoffs once, before it
writes any summary. The defaults depend on the experiment type:

| Setting | Removes a chamber when | Custom | Hedonic, Progressive Ratio |
|---|---|---|---|
| (always) | a well produced no usable lick count | yes | yes |
| `min_untransformed_licks_cutoff` | a well has fewer licks than this over the recording, counted before any transform | off | 20 |
| `max_med_duration_cutoff` | the median feeding-event duration at either well is above this, a sign of a stuck or bleeding signal | not applied | 13.0 |
| `max_events_cutoff` | either well has more feeding events than this | not applied | 150000 |
| `exclude_failed_opto_chambers` | its linkage group failed the optogenetic light QC (section 6) | off | off |

A Progressive Ratio experiment adds its own group-level rules (section 7).
Set the cutoffs in the Project's design so that every member is judged by
the same rule.

### Where exclusions are recorded

| File | Holds |
|---|---|
| `remove_chambers.csv` | the exclusions you declared |
| `analysis/removed_chambers.csv` | every automatic removal and its reason |
| `analysis/summary.txt` | both lists |
| the report's *Excluded chambers* table | both, marked *by hand* or *automatic*; the cover counts them |
| `<project>_Excluded.csv` | every member's, in a Project (section 8) |

**Declaring does not change results already on disk.** When a member's
`remove_chambers.csv` is newer than its saved results, the Hub's Analyzed
column reads **re-run needed**. Run the member's basic analysis again.

---

## 6. Optogenetic experiments: the light QC

When a DFM drives an Optolid, the firmware decides every millisecond whether
each well's light is on. It reads the well's own signal, compares it with a
threshold from the program the MCU loaded, and follows the rule of the
interval's **Paradigm**: in closed loop, for example, it keeps the light on
for a set **Hold** after contact ends. pyflic counts licks afterwards, from
the baselined signal.

Usually the two agree. When a well's signal drifts upward, however, the
firmware sees a well that is constantly touched and keeps the light on,
while pyflic sees a flat trace and no licks. The light then describes the
sensor, not the fly. The **optogenetic light QC** measures that disagreement
over the whole recording, for any experiment type.

A short tail of light after the last lick is normal: that is the Hold. Long
stretches of light with no lick are not.

What pyflic can see depends on the recording. Older firmware records only
`OptoCol1`, which LEDs were lit at each sample. DFM firmware 4.0.0 also
records, on every row, the Paradigm in force and each well's own decisions:
its Activations, its Acclimation, and the milliseconds its light was on.
Section 6.2 explains the difference.

### 6.1 Turning it on

One setting, `optogenetics`, in the design's `global:` block or the
experiment's own:

| Value | Effect |
|---|---|
| `auto` (the default) | runs on every DFM that has a section in `Program.txt` or any light on in its data |
| `true` (*yes* in the editors) | runs on every DFM. A DFM with no light on for the whole recording **fails**: an unplugged lid, or a program that did not load |
| `false` (*no*) | off |

A DFM's own entry may override it, because whether its lid was lit is a fact
about the recording:

```yaml
dfms:
- id: 3
  optogenetics: false     # this DFM ran without a lid
```

In the Config Editor the setting is on the Experiment tab, and each DFM tab
has its own *Optogenetics* picker. In the Project Design dialog it is a
design setting.

### 6.2 Program.txt and the generations

The MCU writes the program it ran back out as `Program.txt`. **Copy that file
into the member's `data/` folder**, beside the DFM files. Use the exported
file, the one with `***DFM 1***` sections, not the program you wrote for the
MCU.

**Two exports.** PyMCU 4.0.0 writes a new kind; older PyMCU wrote another.
pyflic tells them apart by their content and reads both.

- **The PyMCU 4.0.0 export** opens with a `Paradigms:` block that names every
  **Paradigm**, its type and every setting:

  ```
  PR10 (ProgressiveRatio): Frequency 40 Hz, PulseWidth 8 ms, ActivationMs 500 ms, Series Arithmetic, FirstRequirement 1, Step 10, Cap 200, EventGapMs 100 ms, Acclimation 10
  ```

  Each interval line then names its Paradigm, with a threshold per well that
  is a level, `On` or `Off`:

  ```
  (10/12/2026 20:30:00) Dark, PR10, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330 min
  ```

  An old program loaded into PyMCU 4.0.0 appears with generated names such
  as `ClosedLoop-40Hz-8ms-Hold500-MaxOn0`. The `***Env Mon***` section, the
  Environmental Monitor's, is ignored.
- **The older export** echoes five numbers on each interval line: `F:`,
  `P:`, `D:`, `L:` and `M:`, frequency, pulse width, decay, delay and maximum
  time on. Thresholds are numbers: `0` is open loop and `-1` never triggers.
  pyflic turns each line's numbers into the Paradigm PyMCU would make of
  them; the decay becomes its Hold.
- **A recording started without a Program** exports one `***ALL DFM***`
  block. pyflic reads it as every well `Off` for the whole recording, so any
  light is a fault.

From either, pyflic learns for each DFM and each interval of the program:

- **each well's threshold.** A level makes the well a **trigger well**. `On`
  keeps its light on regardless (open loop), and `Off` means it never lights
  by its own behaviour;
- **the linkage**: wells that share a linkage number form one **linkage
  group**, lit together whenever any of them triggers;
- **the Paradigm**: its type (OpenLoop, ClosedLoop, FixedInterval,
  NonFeeding, ProgressiveRatio or FixedRatio) and settings, and from them the
  **Hold** — `HoldMs` for ClosedLoop, `ActivationMs` for FixedInterval and the
  two ratio types;
- **the schedule**: the program type and the interval timestamps.

**The generations.** No data file states its firmware version, so pyflic
reads the shape of each DFM's file once, at load:

| Generation | Recorded by | What pyflic can read |
|---|---|---|
| 1 | PyMCU 3.x, older firmware: 27 columns | the light at each sample (`OptoCol1`); Training as a flag in the signal |
| 2 | PyMCU 4.0.0 with an un-updated DFM: 90 columns, the new ones empty | the light at each sample; no Training at all |
| 3 | PyMCU 4.0.0 with DFM firmware 4.0.0: 90 columns, filled | on every row the Program Interval, its Cycle and its Paradigm; for every well its Phase (`A` in Acclimation, `M` after), its Activations, its Requirement and Progress under a ratio Paradigm, and `OnMs`, the milliseconds its light was on |

On generation 3 the rows are the schedule, so the program's timestamps are
only a check, and the light QC reads the firmware's decisions instead of
re-creating them. The integrity report, `summary.txt` and the report's cover
all name each DFM's generation.

**The file is optional, but the check is weaker without it.**

- On generations 1 and 2 pyflic infers the linkage from wells lit together,
  treats every lit well as a trigger well, and assumes a Hold of
  `opto_default_decay_ms`.
- On generation 3 the rows name each Paradigm but not its type, settings or
  thresholds. pyflic takes the linkage from wells whose light matches to the
  millisecond and the trigger wells from the Activations, judges every
  Activation against its group's licks within `opto_default_decay_ms`, and
  leaves every type-dependent result `NA`. Because the file was simply not
  copied, this is a loud warning: `pyflic lint`, the report's *At a glance*
  and the Hub's **Loaded** line say *DFM n: firmware 4.0.0 recording without
  Program.txt: Paradigm types and settings unknown*, and the light QC flags
  *no Program.txt for firmware 4.0.0*.

Either way unexplained light can then warn but never fail, because without
the program an open-loop schedule looks exactly like a stuck light.
`summary.txt` and the report say so.

If the file cannot be read in part, the lines pyflic skipped are listed in
`summary.txt`, and a DFM whose section cannot be read is judged as if it had
no program. Two `Program.txt` files in `data/` stop the load: keep only the
one the MCU exported for this recording.

### 6.3 What it checks

The unit of judgement is the **linkage group**, because its light is one
circuit. Every verdict passes to each chamber the group touches. Each group
is judged interval by interval, under that interval's Paradigm: on
generations 1 and 2 the intervals are laid out by clock time from the
program, and on generation 3 each run of rows under one Program Interval and
Cycle is an interval.

**Explained light.** Light is **explained** when one of its group's trigger
wells had a feeding lick, or a tasting-level touch, behind it. Touches count
because the firmware decides on contact at millisecond resolution, and a
brief touch it acts on often reads below pyflic's feeding threshold. What
"behind it" means depends on the Paradigm type:

| Light under | Is explained when |
|---|---|
| **ClosedLoop** | a lick or touch at a trigger well from the Hold before it until just after it |
| **FixedInterval**, **ProgressiveRatio**, **FixedRatio** | the trigger well had a lick or touch at the Activation's onset: then its whole `ActivationMs` of light is explained. Feeding during a FixedInterval lockout, which earns no light, is expected |
| **Acclimation** | the ClosedLoop rule, with `ActivationMs` as the Hold |
| **NonFeeding** | not judged this way: the light is meant to be on while the fly does *not* feed. Firmware 4.0.0 recordings are checked for light that stayed on through feeding instead |
| **OpenLoop** | not judged this way: open-loop intervals get their lit-fraction check |

Two samples of slack each side (`opto_decay_tolerance_samples`) absorb the
difference in timing between the firmware's decisions and the samples.

**On a firmware 4.0.0 recording the light belongs to Activations.** Lit time
is `OnMs`, exact to the millisecond. Each Activation of a trigger well owns
its group's light from its onset to the next Activation, the light going out
or the end of its interval plus the Hold. Unexplained light is the lit time
of the Activations whose onset had no lick or touch at their well. On older
recordings every lit sample of `OptoCol1` is judged with the Hold rule.

| Check | What it means | Verdict |
|---|---|---|
| **Unexplained light** | at least 30% of the group's judged lit time had no lick or touch behind it | **fails** the group |
| **Partly unexplained light** | at least 10% unexplained | warning |
| **Light while off** | lit while every well of the group was `Off` (-1), or while the DFM ran PyMCU's idle Paradigm | **fails** the group |
| **No light recorded** | `optogenetics: true`, and no light on the DFM at all | **fails** the DFM |
| **Broken yoking** | firmware 4.0.0: the group's linked wells' light differs by more than 1 ms in more than 1% of its lit records, or an `Off` well linked to a trigger well counted Activations of its own | **fails** the group |
| **Paradigm not in program** | firmware 4.0.0: a row names a Paradigm `Program.txt` does not define, so the file is another recording's; those rows are not judged | **fails** every group of the DFM |
| **Unlit feeding** | at least half of the feeding bouts at its trigger wells under closed loop, or in Acclimation, never lit the group (at least 5 bouts) | warning |
| **No light events** | feeding at its trigger wells, and never lit | warning |
| **Open loop not lit** | lit for less than 95% of an open-loop interval | warning |
| **Non-feeding light during feeding** | firmware 4.0.0: under NonFeeding, lit through more than 10% of the feeding at its trigger wells, and for at least 30 seconds | warning |
| **Acclimation count mismatch** | firmware 4.0.0: a trigger well's completed Acclimation counted a different number of Activations than its Paradigm's `Acclimation` | warning |
| **Firmware events disagree** | firmware 4.0.0: under a ratio Paradigm's Main phase, the feeding bouts the firmware counted at a trigger well and the ones pyflic counted differ by more than 25% of the firmware's (judged from 5 bouts) | warning |
| **Lost records** | firmware 4.0.0: more than 25 records missing from the DFM's index | warning for the DFM |
| **Unknown-instruction rows** | firmware 4.0.0: more than 1% of the rows after the opening idle rows recorded under an instruction outside the program | warning for the DFM |
| **Late records** | firmware 4.0.0: more than 10 records whose light count exceeds the record's 200 ms, so the record came late | warning for the DFM |
| **Program mismatch** | the data's frequency, pulse width or dark setting differ from the program, the data start more than a minute from its start time, or (firmware 4.0.0) a row names another Paradigm than the program's line for its interval | warning |
| **No program section** | `Program.txt` has no usable section for this DFM | warning |
| **No Program.txt for firmware 4.0.0** | a firmware 4.0.0 DFM without its program | warning |

Neither unexplained-light check is judged until a group has at least 30
seconds of unexplained light (`opto_unexplained_min_sec`), so a few stray
samples in a group lit for seconds are not called a fault. The fractions are
the same for every Paradigm type.

Some light is not judged at all:

- light at the start of an interval, for one Hold, which belongs to the
  interval before it;
- light outside the program's schedule; on firmware 4.0.0, the baseline rows
  before the program's first instruction, rows under an instruction outside
  the program, and an interval whose Paradigm `Program.txt` does not define;
- **open-loop** light and **NonFeeding** light, where the light is not meant
  to follow feeding. They get their own checks instead.

The firmware 4.0.0 checks read the file's own bookkeeping. Their thresholds
(section 6.5) are first guesses with no real recording behind them yet:
treat their flags as reasons to look.

### 6.4 Drift or hardware?

Each flagged group gets a **likely cause**:

- **a drifting baseline or sustained contact**, when most of its unexplained
  light fell where the firmware saw contact and pyflic saw no lick or touch.
  The light followed the sensor.
- **hardware, linkage or program mismatch**, otherwise: light the firmware
  had no reason to switch on. Check the lid, the linkage and the program.

How pyflic knows where the firmware saw contact depends on the generation.

**On a firmware 4.0.0 recording the firmware's decisions are recorded.** An
Activation, or a feeding bout the firmware counted toward a Requirement, with
no pyflic lick or touch at its trigger well is the drifting-baseline
signature itself. In `opto_light_qc.csv`, `ContactSec` is the lit time of the
trigger wells' Activations, `ContactWithoutActivitySec` the lit time of the
ones whose onset had no lick or touch, and `FirmwareEventsWithoutActivity`
the firmware's feeding bouts with none either. Nothing is emulated.

**On older recordings pyflic emulates the firmware.** With a program, it
re-runs the firmware's own test on the recorded signal: the firmware
subtracts the mean of the run's first ten seconds and compares each sample
with the interval's threshold. Wherever this **emulated trigger** reads a
trigger well above threshold while pyflic sees no lick or touch, the firmware
was seeing contact that pyflic's running baseline removed.
`ContactWithoutActivitySec` is how long that lasted. The emulation is marked
approximate (`EmulationApproximate`) when the data begin more than two
seconds after the program started, because the firmware's first ten seconds
were not recorded.

### 6.5 Settings

The thresholds are design `constants:`, shared by every experiment type,
with fields in the Project Design dialog and the Config Editor. Change one
only for a reason you can state.

| Setting | Default | Meaning |
|---|---|---|
| `exclude_failed_opto_chambers` | false | remove every chamber of a failed linkage group; off, they are flagged and kept |
| `opto_unexplained_warn_fraction` | 0.10 | unexplained share of lit time that warns |
| `opto_unexplained_fail_fraction` | 0.30 | unexplained share that fails |
| `opto_unexplained_min_sec` | 30 | seconds of unexplained light needed before either is judged |
| `opto_default_decay_ms` | 1000 | the Hold assumed without `Program.txt` |
| `opto_decay_tolerance_samples` | 2 | samples of slack around the Hold |
| `opto_unlit_feeding_fraction` | 0.50 | unlit share of closed-loop feeding bouts that warns |
| `opto_open_loop_min_lit_fraction` | 0.95 | lit share an open-loop interval needs |
| `opto_event_disagreement_warn_fraction` | 0.25 | firmware 4.0.0: a trigger well whose firmware and pyflic feeding-bout counts differ by more than this share of the firmware's warns |
| `opto_yoking_fail_fraction` | 0.01 | firmware 4.0.0: share of a group's lit records in which its linked wells' light differs by more than 1 ms, above which the group fails |
| `opto_lost_records_warn` | 25 | firmware 4.0.0: records missing from the index (5 seconds) above which the DFM warns |
| `opto_unknown_rows_warn_fraction` | 0.01 | firmware 4.0.0: share of rows under an instruction outside the program above which the DFM warns |
| `opto_late_records_warn` | 10 | firmware 4.0.0: late records above which the DFM warns |

The last five apply only to firmware 4.0.0 recordings. None of their defaults
has a real recording behind it yet; they will be revisited once there is one.

### 6.6 Where to look

Basic analysis and **QC reports** both write the light QC into `qc/opto/`:

| File | One row per | Holds |
|---|---|---|
| `opto_light_qc.csv` | linkage group | its `Generation`; its wells, trigger wells, chambers, their `Roles` and treatment; lit and unexplained time; the onset; the contact evidence (section 6.4); on firmware 4.0.0, the firmware's and pyflic's feeding-bout counts and the Acclimation counted and expected; `LikelyCause`, `Flags`, `Verdict`, `Excluded` |
| `opto_light_intervals.csv` | group and interval | the interval's mode, the Hold it was judged with (`HoldMs`) and trigger wells; on firmware 4.0.0 the `ProgramInterval`, `Cycle`, `Paradigm` and `ParadigmType` the rows recorded; lit, unexplained and contact time; feeding bouts, and those never lit |
| `opto_light_events.csv` | light event | its well, onset, end and duration; unexplained seconds; `OverrunSec`, the light's time past the last lick plus the Hold; on firmware 4.0.0, where each event is one Activation, its `Phase`, the Requirement it met and the firmware's feeding bouts behind it |
| `opto_program.csv` | program interval | the program as pyflic read it: each Paradigm's name, type and settings, the linkage and trigger wells, and for an older export the raw `F` and `P` it echoed |
| `opto_light_dfm<n>.png` | DFM | the *Light explained by licks* figure |

**Roles.** `Roles` names what each chamber of the group was to the light, as
in `1 Paired, 2 Yoked`. The six Roles are Paired (it holds the group's only
trigger well), Yoked (lit by a partner's trigger well), Mutual (one of
several chambers with trigger wells in one group), Self (a trigger well whose
group lights no other chamber), Open (lit regardless) and Unlit. They come
from the program, or on a firmware 4.0.0 recording from the data; an older
recording without a program has none.

Every chamber's rows in the feeding summaries carry `OptoLightQC`, its
group's flags (empty when the group is ok), and `OptoUnexplainedFraction`,
and on an optogenetic member its `Role`, `LitSec` and `Activations`.
`summary.txt` has an *Optogenetic light QC* section, and the report has one
in Quality control, with the program, the verdicts and the figure.

Beside the QC, basic analysis writes the **light table**,
`analysis/light_summary.csv` (per chamber) and `light_wells.csv` (per well):
what the light did, with the feeding summary's treatment and factor columns.
It is a result, not a check; the report's *Light behaviour* section compares
treatments on it. See *Optogenetic experiments* in the help.

**On the Hub**, the QC panel shows an **Optogenetics** group whenever the
loaded member is optogenetic: **Opto light QC table** writes the tables and
logs every flagged group, **Light explained by licks (QC)** draws the
figure, **Program timeline** draws section 6.8's figure, and **Light summary
CSV** writes the light table.

**In the QC Viewer**, the **Opto Light QC** tab lists every linkage group with
its chambers' Roles, lit time, unexplained share, onset, contact with no lick
and verdict, and opens on the worst group. Selecting a group shows why it got
its verdict, its intervals, light events and program, and its panels of the
figure; a column empty on every row is hidden. The tab is computed from the
loaded experiment, so a **Params** recompute updates its verdicts at once.
That is worth seeing before you settle on a threshold: one that loses real
licks makes healthy light look unexplained.

### 6.7 Reading *Light explained by licks*

One row per linkage group that was ever lit or touched, or was flagged, with
the group's wells and verdict in each panel's strip. Basic analysis and the
QC Viewer draw it in 10-minute bins; the Hub's button uses the bin size on
its Analyze panel.

- **The left panel** is the group's lit time per bin, stacked: **grey-blue**
  where a trigger-well lick or touch explains it, **red** where nothing
  does, **purple** where the group was lit while every threshold was `Off`
  (-1), and **light grey** where the light is not judged by licks (open
  loop, NonFeeding). On a firmware 4.0.0 recording the lit time is `OnMs`.
- **The right panel** is **orange**. On an older recording, when
  `Program.txt` allows the emulated trigger, it is the time the firmware
  would have read a trigger well above threshold while pyflic saw no lick or
  touch. On a firmware 4.0.0 recording, titled *firmware events, no lick*,
  it is the light of the Activations the firmware counted with no lick or
  touch at their onset.

How to read a row:

- **Mostly grey-blue**: the light followed the fly. A little red beside it
  is light that outlasted the last lick or touch pyflic saw by more than the
  Hold. Small amounts are normal, which is why nothing is judged below 30
  seconds or the warning fraction.
- **Red beside orange** in the same bins: a drifting well. The firmware saw
  contact, pyflic did not, and the light is not evidence of feeding.
- **Red with no orange**: light the firmware had no reason to switch on.
  Check the lid, the linkage and the program.
- **Purple** anywhere: the program said the light was off. That is a
  hardware or program problem, whatever the licks did.

### 6.8 Reading the Program timeline

The **Program timeline** (`qc/program/program_timeline_dfm<n>.png`) shows,
for one DFM, what its program ran and what each well did. QC reports draw it
for every DFM with a `Program.txt` section or firmware 4.0.0 data, and basic
analysis for every firmware 4.0.0 DFM. It is in the report's Quality control
section, behind the Hub's **Program timeline** button (which uses the
Analyze panel's bin size), and in the QC Viewer's **Program** sub-tab of each
DFM.

- **The band at the top** is the program: one block per Program Interval,
  coloured by Paradigm type and labelled with the Paradigm's name, and with
  `C<n>`, the pass, when the program repeats. **Light grey** is the baseline
  before the first instruction reached the DFM, **hatched white** an
  instruction outside the program, and **dark grey** a Paradigm whose type
  `Program.txt` does not give.
- **One lane per well** follows, labelled with its chamber and the chamber's
  Role. **Pale orange shading** is Acclimation (Phase `A`), each **black
  tick** an Activation, and the **blue strip** the share of each bin the
  light was on.

How to read it:

- **The band should be the program you meant to run.** A hatched block
  after the start is the DFM running something outside the program. A
  dark-grey block is a Paradigm the `Program.txt` in `data/` does not know:
  it is most likely another recording's file.
- **Each trigger well should leave Acclimation** within the interval that
  started it. A well still shaded at the end never completed it.
- **Ticks should come where the fly fed.** Under a ratio Paradigm they thin
  out as the Requirement rises. A dense comb of ticks while the fly's
  cumulative licks are flat is the light following the sensor.
- **A yoked well has no ticks** and the same blue strip as its partner.
  Ticks on a yoked well, or a strip that differs, is broken yoking.

In the QC Viewer the timeline sits above a table of each well at the end of
the loaded range: its Paradigm, its Phase, the minute its Acclimation ended,
its Activations, its Requirement and Progress, and its lit seconds.

On an older recording the band is laid out from the program's clock times
and is approximate, and the lanes show the sampled light only: no
Acclimation and no ticks.

### 6.9 Deciding what to exclude

**A failed group is flagged, not excluded, by default.** A faulty light does
not make the feeding record wrong. It makes the light-on numbers wrong, and
whether that matters depends on your question. Three ways to act on it:

- **Keep the group.** Its flags stay on its chambers' rows, and the Project
  reports it as *retained*. Say so when you report the result.
- **Exclude it by hand.** In the QC Viewer's Opto Light QC tab, **Mark
  Selected Group Excluded** or **Mark Failed Groups Excluded** tick its
  chambers, and **Save Exclusions…** records them. The buttons save nothing
  on their own.
- **Exclude every failed group automatically**, by setting
  `exclude_failed_opto_chambers: true` in the design.

`UnexplainedOnsetMin` is the start of the first 30-minute window in which a
flagged group's unexplained share reached the warning fraction, in minutes
from the start of the recording. It is the latest point at which a cutoff
you set by hand could fall, if you analyse only the time before the fault.

Whichever you choose, apply it to every group, whatever its treatment, and
decide before you look at the results.

---

## 7. Progressive Ratio experiments

A Progressive Ratio experiment gets everything above, including the
optogenetic light QC, and a QC of its own, which asks whether the paired fly
earned each light event. It is described in full in the
[Progressive Ratio guide](progressive-ratio-user-guide.md), sections 5.1 to
5.3 and 6. In brief:

| Check | Verdict |
|---|---|
| **Training never completed** | removes both chambers of the group (`require_training_complete`) |
| **No training information**: recorded by PyMCU 4.0.0 from a DFM whose firmware is older than 4.0.0 | nothing removed: each group is one `Recording` facet, with no Test phase and no breaking point |
| **Self-triggered light**: five or more Test light events in a row with no sucrose lick since the previous one | **fails** the group |
| **Implausible training**: training completed, with light events, but without one sucrose lick | **fails** the group |
| **No increasing trend** in licks per light event | warning |
| **Resting level rise** or **resting level elevated** at the sucrose well | warning |

A group that fails leaves the analysis by default
(`exclude_failed_pr_groups: true`). A light event is lick-free only when it
has no sucrose lick since the previous one and no lick or touch within its
Hold, so a light the fly touched for is never counted against it. On a
firmware 4.0.0 recording a light event is the paired sucrose well's own
Activation, and Training is read from its Phase rather than from a flag in
the signal.

| Output | What it is |
|---|---|
| `analysis/pr_light_qc.csv` | one row per chamber group: flags, verdict, `Excluded`, and `LickFreeRunStartMin` |
| `analysis/pr_light_events.csv` | every Test light event, with its licks and whether it counts; on firmware 4.0.0 also the Requirement it met and the firmware's feeding bouts behind it |
| `analysis/pr_light_events_dfm<n>.png` | **Licks per light event**: a working progressive ratio climbs |
| `analysis/pr_resting_level_dfm<n>.png` | **Sucrose Well resting level**: a well that creeps up is a sensor problem |
| `analysis/pr_cumulative_licks_dfm<n>.png` | **Training-aligned traces**: light that keeps firing while the paired trace is flat is self-triggering |

The Hub shows the checks' buttons in the same **Optogenetics** group of the
QC panel, beside the optogenetic ones.

**The two light QCs can disagree, and both are right.** The PR check counts
light *events*; the optogenetic check measures lit *time*. On the first real
dataset, one group lit for four hours during training passed the PR check,
because one long light event is not a run of lick-free events. It failed
the optogenetic check, because 93% of those four hours had no lick behind
them. Read both before deciding.

---

## 8. Projects

A Project pools its members, and so it pools their QC. **Project panel →
Build combined analysis** writes, into the Project's `analysis/` folder:

| File | Holds |
|---|---|
| `<project>_Excluded.csv` | every member's exclusions: `manual` (its `remove_chambers.csv`) and `auto` (its `removed_chambers.csv`), with the reason |
| `<project>_LightQC.csv` | every member's light QC tables stacked, with a `Source` column: `PR` for a Progressive Ratio chamber group, `Opto` for an optogenetic linkage group |
| `<project>_Stats.txt` | the pooled statistics, with every flagged group listed before the tables |

Every flagged group is listed in the Stats text and the Project Report's
Quality control section with a **status**:

- **excluded**: its member's auto-removal took its chambers out;
- **retained**: it failed, but its exclusion switch was off, so it **is** in
  the pooled numbers;
- **kept — warning only**: it was only warned.

Pooling needs **every member judged by the same rules**. A Project's design
owns the settings that decide QC: the detection parameters, the exclusion
cutoffs and the light QC thresholds. Every member inherits them. Set them
there, once, and keep a DFM's own settings to what its rig requires, such as
`pi_direction`.

Before pooling, compare the exclusion counts per treatment in
`<project>_Excluded.csv`. If one treatment lost far more chambers than
another, the chambers that remain may not be comparable. Report the counts.

The Project Report's member table names the **generation** of each member's
recordings, and adds a note for a member with no training information, so a
Project that mixes firmware versions says so. A firmware 4.0.0 member
contributes light measures an older one cannot (section 6.2).

---

## 9. A QC checklist

For each recording, before you look at any result:

1. **Load it and write the QC bundle**: Hub → QC → **QC reports**.
2. **Integrity**: every DFM *ok*, or every warning explained, lost records
   among them (section 3.1). Note each DFM's generation.
3. **Data breaks**: none long enough to matter (section 3.2).
4. **Raw signal**: no dead wells you did not expect, no wells drifting far
   (section 3.3).
5. **Baselined signal**: the thresholds sit sensibly for your data.
6. **QC Viewer**: detected bouts match the trace in a few chambers you can
   read by eye. Settle any parameter change now, and write it into the
   configuration (section 4).
7. **Two-well**: the bleeding check is *ok*, the crosstalk before the
   correction is small, and you know whether the dual-feeding correction was
   on (sections 3.4 and 3.5).
8. **Optogenetic**: `Program.txt` is in `data/` — for a firmware 4.0.0
   recording, no *without Program.txt* warning anywhere; every linkage group
   is ok, or every flagged group has a decision (section 6).
9. **Optogenetic, firmware 4.0.0**: the Program timeline shows the program
   you meant to run, every trigger well left Acclimation, and every yoked
   well's light matches its partner's (section 6.8).
10. **Progressive Ratio**: the training table and the PR light QC (section 7).
11. **Exclusions**: declare them, run **Basic analysis** again, and check
    `removed_chambers.csv` and the report's *Excluded chambers* table
    (section 5).
12. **Write the report** and read its Quality control section and cover
    before its results.

In a Project, finish with **Build combined analysis** and read the flagged
groups and the exclusion counts per treatment (section 8).

---

## 10. Quick troubleshooting

| You see | Likely cause | What to do |
|---|---|---|
| The QC Viewer's DFM tabs show no integrity files or plots | the QC bundle has not been written | **Run QC** in the viewer, or **QC reports** on the Hub |
| The baselined plot shows thresholds you changed | the QC bundle predates the change | write it again |
| An integrity **warning** | data breaks, error flags, lost records or a skipping index | read the integrity text for which; look at the signal plots around that time |
| **Lost records** in the integrity report | the DFM lost records while the MCU was not reading it; `Messages.csv` says *Skipped index* | a short gap changes little; treat results across a long one with care, as for a data break |
| **Repeated records dropped at load** | PyMCU wrote a block twice after a failed file write | nothing: the first copy is kept |
| A well with no deflections at all on the raw plot | an empty position or a dead well | exclude the chamber by hand if a fly was in it |
| The simultaneous-feeding table's `Both` is zero everywhere | the dual-feeding correction is on, and `Both` is counted after it | read `Both_pre`, the count before it (section 3.4) |
| A **bleeding** warning | one well's signal appears in another above `feeding_threshold` | look at the responding well's baselined trace while the signalling well is fed from |
| Many chambers removed for too few licks | the flies fed little, or `min_untransformed_licks_cutoff` is high for this assay | check the cumulative licks; set the cutoff in the design, for every member |
| The Hub says **re-run needed** | exclusions changed after the results were written | run the member's basic analysis again |
| A linkage group failed for **unexplained light** | most of its lit time had no lick or touch behind it | open *Light explained by licks*: orange beside the red is a drifting well; no orange is a light the firmware had no reason to switch on |
| Unexplained light only **warns**, never fails | no `Program.txt` in `data/` | copy the MCU's exported `Program.txt` into `data/` and run again |
| "holds more than one Program.txt" | two program files in `data/` | keep only the one exported for this recording |
| **No light recorded** fails a DFM | `optogenetics: true`, and the DFM's light was never on | check the lid and the program; set the DFM's own `optogenetics: false` if it ran without a lid |
| **Program mismatch** | the data's light settings or start time differ from the program, or a row names another Paradigm than the program's line | check that `Program.txt` is the one exported for this recording |
| *firmware 4.0.0 recording without Program.txt* | the program was not copied into `data/` | copy the `Program.txt` PyMCU exported for this recording and run again |
| **Paradigm not in program** fails every group of a DFM | the rows name a Paradigm `Program.txt` does not define: the file is another recording's | find the `Program.txt` exported with this recording |
| **Broken yoking** fails a group | linked wells' light differs, or an `Off` well counted Activations: the yoked fly did not get its partner's light | check the lid's wiring and the program's `Linkage:` line; the Program timeline shows which well |
| **Acclimation count mismatch** | a trigger well's Acclimation counted other than its Paradigm's number | check that `Program.txt` is this recording's; then look at the well's lane in the Program timeline |
| **Firmware events disagree** | the firmware and pyflic counted feeding bouts differently at a trigger well | look at the baselined trace; compare the Paradigm's `EventGapMs` with `feeding_event_link_gap` |
| **Unknown-instruction rows** or **late records** | the DFM ran something outside the program, or records came late | note the minutes; those rows are not judged |
| *no training information* on a Progressive Ratio member | recorded by PyMCU 4.0.0 from a DFM with older firmware | nothing to fix here: each group is one `Recording` facet; update the DFM for the next recording |
