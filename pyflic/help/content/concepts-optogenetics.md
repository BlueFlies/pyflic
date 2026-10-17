# Optogenetic experiments and the light QC

When a DFM drives an Optolid, the firmware decides every millisecond whether each well's LED
is on. It reads the well's own signal, compares it with a threshold from the program the MCU
loaded, and applies the rule of the interval's **Paradigm**. pyflic counts licks afterwards,
from the baselined signal.

The two should agree. When they do not, the light is evidence about the sensor rather than
the fly. A well whose signal drifts upward looks continuously touched to the firmware and
flat to pyflic, so the light runs with no lick behind it, and every light-on number
describes the hardware. The **optogenetic light QC** measures that disagreement for any
experiment type, over the whole recording, whatever window a table uses.

A short tail of light after the last lick is normal: that is the **Hold**. Long stretches of
light with no lick are not.

## Turning it on

One setting, `optogenetics`, under `global:` (or the Project's design):

```yaml
global:
  optogenetics: auto      # the default; also true (yes) or false (no)
```

- **auto** runs the light QC on every DFM that has a section in `data/Program.txt` or any
  LED lit in its data. A recording with neither is not treated as optogenetic.
- **yes** (`true`) runs it on every DFM, and a DFM with no LED lit for the whole recording
  **fails** — an unplugged lid, or a program that did not load.
- **no** (`false`) turns it off.

YAML reads a bare `yes` or `no` as true or false, which is why the editors write those.

A DFM's own entry may override the setting for that DFM, because whether its lid was lit is
a fact about the recording, not about the analysis. The override is allowed inside a
Project, like the rest of `dfms:`:

```yaml
dfms:
- id: 3
  optogenetics: false     # this DFM ran without a lid
  chambers: {1: Ctrl, 2: Ctrl}
```

In the [Config Editor](app-config-editor.md) the setting is on the Experiment tab and each
DFM tab has its own *Optogenetics* picker, which inherits by default.

## Generations

No data file states its firmware version. pyflic reads the shape of each DFM's file once, at
load, and calls it the recording's **Generation**:

| Generation | Written by | Columns | Training | Light |
|---|---|---|---|---|
| 1 | PyMCU 3.x, any older firmware | 27 | a flag inside the signal | `OptoCol1`, sampled five times a second |
| 2 | PyMCU 4.0.0, DFM firmware older than 4.0.0 | 90, the new ones all `NA` | **none** | `OptoCol1` |
| 3 | PyMCU 4.0.0, DFM firmware 4.0.0 | 90, filled | each well's `Phase` | `OnMs`, exact to the millisecond |

A generation-3 file records, on every row, the **Program Interval**, **Cycle** and
**Paradigm** in force, and for each well its **Phase** (`A` in Acclimation, `M` after), its
running **Activations**, its **Requirement** and **Progress** under a ratio Paradigm, and
the milliseconds its LED was on (`OnMs`). The light QC reads those decisions instead of
reconstructing them.

A generation-2 file comes from a lab with an updated MCU and an un-updated DFM. It has light
but no training information at all, and pyflic says so wherever training would show.

`summary.txt` names each DFM's generation and where its light seconds came from. The
report's cover has a **Generation** line and, for an optogenetic member, a **Lit time from**
line. Every light table and QC table carries a `Generation` column.

## Program.txt

The MCU writes the program it ran back out as `Program.txt`. Copy that file into the
member's `data/` folder, beside the DFM CSVs. pyflic reads the exported file only, the one
with `***DFM 1***` sections, not the program you authored for the MCU with `[General]`,
`[Paradigm …]` and `[DFM]` sections.

PyMCU writes two kinds of export. pyflic tells them apart by their content and reads both.

### The PyMCU 4.0.0 export

```
Paradigms:
Closed (ClosedLoop): Frequency 40 Hz, PulseWidth 8 ms, HoldMs 500 ms, MaxOnMs 0 ms, EventGapMs 100 ms
PR10 (ProgressiveRatio): Frequency 40 Hz, PulseWidth 8 ms, ActivationMs 500 ms, Series Arithmetic, FirstRequirement 1, Step 10, Cap 200, EventGapMs 100 ms, Acclimation 10

***DFM 1***
Linkage: 1,1,2,2,3,3,4,4,5,5,6,6
Program Type: Linear
(10/12/2026 20:00:00) Dark, Closed, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 30 min
(10/12/2026 20:30:00) Dark, PR10, 20,Off,20,Off,20,Off,20,Off,20,Off,20,Off, 330 min
```

- **The `Paradigms:` block** names every Paradigm, its type in brackets and every setting.
  It is the only place the type and settings appear: a data row carries only the name.
- **An interval line** gives its start, `Dark` or `Lit`, the Paradigm's name, twelve
  thresholds and its length. The k-th line of a DFM's section is its Program Interval k.
- **A threshold** is a signal level, `On` or `Off`. A level makes the well a **trigger
  well**. `On` keeps it lit regardless (open loop). `Off` never lights it by its own
  behaviour, and such a well runs no Paradigm of its own.
- **`***Env Mon***`** is the Environmental Monitor's section. pyflic ignores it.
- **`***ALL DFM***`** is what PyMCU writes for a recording started without a Program. pyflic
  reads it as every well `Off` for the whole recording, so any light is a fault.
- **An old program loaded into PyMCU 4.0.0** is exported with generated Paradigm names that
  describe its settings, such as `ClosedLoop-40Hz-8ms-Hold500-MaxOn0`.

### The older export

Before PyMCU 4.0.0 an interval line looked like this:

```
(07/28/2025 12:01:00) Dark Off,20,-1,-1,-1,20,-1,-1,-1,20,-1,-1,-1,F:5160,P:8,D:500,L:1000,M:1000000000000,1440.0min.
```

- **Thresholds** are numbers: a positive one makes a trigger well, `0` is open loop and `-1`
  never triggers.
- **F, P, D, L, M** are frequency, pulse width, decay, delay and max-time-on. A frequency
  above 512 carries the progressive ratio's acclimation-event count in its high bits (`5160`
  is 10 events at 40 Hz). A pulse width at or above 32768 selects non-feeding activation.
  Both are decoded.
- pyflic turns each interval's numbers into the Paradigm PyMCU would make of them, with the
  same generated name. The decay becomes that Paradigm's Hold.

### What pyflic takes from it

- **Linkage**: wells sharing a number form one **linkage group**, lit together whenever any
  member triggers.
- **Each interval's Paradigm and thresholds**: which wells trigger, which are open loop,
  which are off, and the rule the light followed.
- **Program type** and the interval timestamps. On generations 1 and 2 these lay the
  intervals out over the run: Linear holds its last interval to the end, Repeating and
  Circadian start over, and Constant runs its first interval throughout. A generation-3
  file records its own schedule row by row, so the timestamps are used only as a check.
- **Baseline**, the start time and the duration.

### Without it

**The file is optional.** Without it the light QC still runs, but it is limited:

- **Generations 1 and 2.** Linkage is inferred from wells lit together, every lit well
  counts as a trigger well, and the Hold is taken as `opto_default_decay_ms`.
- **Generation 3.** The rows name each Paradigm but not its type, settings or thresholds.
  Linkage comes from wells whose `OnMs` match exactly, and the trigger wells are the ones
  that counted Activations. Every Activation is judged against its group's licks within
  `opto_default_decay_ms`. The checks that need the Paradigm's type are not made, and every
  type-dependent column is `NA`.

Either way, unexplained light can warn but not fail, because without the program an
open-loop schedule is indistinguishable from a stuck light.

A firmware 4.0.0 recording without its program is warned about loudly, because the file it
needs was simply not copied. `pyflic lint`, the report's *At a glance* and the Hub's
**Loaded** line all say:

```
DFM 1: firmware 4.0.0 recording without Program.txt: Paradigm types and settings unknown
```

### When it is wrong

A line pyflic does not understand is skipped and listed in `summary.txt`. A DFM section
that cannot be read is dropped, and that DFM is judged as if there were no program. A file
with no readable DFM section is set aside with the reason. More than one `Program.txt` in
`data/` stops the load, because which one describes this recording is not a guess to make.

On a generation-3 recording the rows are checked against the file. A row naming a Paradigm
the file does not define means the file belongs to another recording, which fails every
group of that DFM (see [the checks](#the-checks)).

## Paradigm types

Each Paradigm is one of six types. Every type has a frequency and a pulse width. The
**Hold** is how long the light stays on after the contact that earned it; the light QC
explains light with it.

| Type | When the LED is on | The Hold | Other settings |
|---|---|---|---|
| **OpenLoop** | the whole interval, except `Off` wells | none | — |
| **ClosedLoop** | during contact, and for the Hold after it ends; one on-period is cut off at `MaxOnMs` | `HoldMs` | `MaxOnMs`, `EventGapMs` |
| **FixedInterval** | contact starts an Activation of exactly `ActivationMs`; the next cannot start until `LockoutMs` after the last one started | `ActivationMs` | `LockoutMs`, `EventGapMs`, `Acclimation` |
| **NonFeeding** | on at the start, off during contact, on again `OnDelayMs` after contact ends, for at most `MaxOnMs` | none | `OnDelayMs`, `MaxOnMs` |
| **ProgressiveRatio** | the feeding bout that meets the **Requirement** starts an Activation of exactly `ActivationMs`; the Requirement then rises along its series | `ActivationMs` | `Series`, `FirstRequirement` and `Step`, or `Scale` and `Rate`; `Cap`, `EventGapMs`, `Acclimation` |
| **FixedRatio** | every `Ratio`-th feeding bout starts an Activation of exactly `ActivationMs` | `ActivationMs` | `Ratio`, `EventGapMs`, `Acclimation` |

The firmware counts a feeding bout of its own, a **Firmware Event**: contact that ends once
the signal has stayed below the threshold for `EventGapMs`. It is a different detector from
pyflic's feeding events, on the same signal. The two agree in the main and differ at the
edges.

**Acclimation.** A FixedInterval or ratio Paradigm with `Acclimation: N` starts each well
with N closed-loop Activations: each of its first N Firmware Events lights the LED during
contact and for `ActivationMs` after. The well's `Phase` reads `A` until its Nth Activation
ends, then `M` (Main). Each well moves on separately.

**Same name, same state.** When the next interval names the same Paradigm, every well keeps
its Phase, Requirement and Progress. A different name starts every well afresh.

The firmware's own definitions are in PyMCU's `ProgramFormat.md`.

## Roles

Every chamber of an optogenetic DFM gets a **Role**: what it was to the light, in any
design.

| Role | The chamber |
|---|---|
| **Paired** | holds the trigger well of a linkage group that also lights other chambers, and is the only chamber of that group that can |
| **Yoked** | shares a linkage group with a Paired (or Mutual) chamber and holds none of its trigger wells: lit when its partner earns light |
| **Mutual** | is one of several chambers of one linkage group that each hold a trigger well |
| **Self** | holds a trigger well whose group lights no other chamber |
| **Open** | is lit regardless of its fly: every well `On`, or in a group lit open loop |
| **Unlit** | none of the above |

Roles come from the program's linkage and thresholds. On a generation-3 recording without a
program they come from the data: trigger wells are the wells that counted Activations, and
wells whose `OnMs` match exactly are linked. A generation-1 or 2 recording without a program
cannot tell a trigger well from a yoked one, so its Role is left blank.

The Role is a column beside the Treatment, never a Treatment level. It appears on
`feeding_summary.csv` rows, in the [light table](#the-light-table), in the lane labels of
the [Program timeline](#the-program-timeline), and per group in `opto_light_qc.csv`'s
`Roles` column (`1 Paired, 2 Yoked`). A [Progressive Ratio](concepts-progressive-ratio.md)
experiment keeps its own `paired` and `yoked` everywhere, from `paired_chambers`.

## What the light QC checks

The unit of judgement is the **linkage group**: its light is one circuit. Every verdict is
passed on to each chamber the group touches.

### Windows

Each group is judged interval by interval, under that interval's Paradigm.

- **Generations 1 and 2.** The intervals are laid out by clock time from the program.
- **Generation 3.** The rows are the schedule: each run of rows under one Program Interval
  and Cycle is a window. The baseline rows before the first instruction (Program Interval 0)
  and rows under an instruction outside the program are not judged. A Program Interval
  beyond the lines `Program.txt` prints (it omits intervals past the duration and lists a
  Repeating program's first pass only) is judged by its Paradigm's name, with the trigger
  wells read from the Activations.

A group's mode in a window comes from its members' thresholds: any member `On` is open loop,
every member `Off` is off, and otherwise the Paradigm's type rules.

### Explained light

The light is judged by the rule of its Paradigm type:

| Light under | Is explained when |
|---|---|
| **ClosedLoop** | a trigger well has a feeding lick or a tasting sample from the Hold (`HoldMs`) plus `opto_decay_tolerance_samples` (2) before the lit sample to the tolerance after it |
| **FixedInterval**, **ProgressiveRatio**, **FixedRatio** | an Activation's whole `ActivationMs` of light is explained when its trigger well had a lick or touch within the tolerance of its onset. Feeding during a FixedInterval lockout that earned nothing is expected |
| **Acclimation** (Phase `A`) | the ClosedLoop rule, with `ActivationMs` as the Hold |
| **NonFeeding** | not judged by explained light; checked instead for light that stayed on through feeding |
| **OpenLoop** and `On` wells | not judged by explained light; checked for their lit fraction |
| every member `Off` | never: any light fails |

Tasting samples count because the firmware decides on contact at millisecond resolution, and
a brief touch it counts often reads below pyflic's feeding threshold. The tolerance absorbs
the difference between those decisions and the recorded samples.

**On generation 3 the light is attributed to Activations.** Lit time is `OnMs`, exact to the
millisecond. Each Activation of a trigger well owns the group's light from its onset to the
next onset, the light going out, or the end of its window plus the Hold, whichever comes
first. Unexplained light is the lit time of Activations whose onset had no pyflic lick or
touch. Light no Activation owns is judged sample by sample with the window rule.

**On generations 1 and 2** every lit sample of `OptoCol1` is judged with the window rule and
the interval's Hold (the old export's decay).

The thresholds are the same for every type: at least `opto_unexplained_warn_fraction` (10%)
of the group's judged lit time unexplained warns, at least `opto_unexplained_fail_fraction`
(30%) fails, and neither is judged until a group has `opto_unexplained_min_sec` (30 s) of
unexplained light, so a few stray samples are not called a fault. Where a group is flagged,
`UnexplainedOnsetMin` is the start of the first 30-minute window in which its unexplained
share reached the warning fraction: the latest a hand-set cutoff could fall.

Light at the start of an interval is left to the interval before it for the length of its
Hold.

### The checks

Each check writes a flag into the group's `Flags`, in the words below.

| Check | Verdict | Generation |
|---|---|---|
| **unexplained light**: at least 30% of the group's judged lit time unexplained | **fails** the group | all |
| **partly unexplained light**: at least 10% unexplained | warning | all |
| **unexplained light (no Program.txt)**: 30% or more without a program, which cannot fail | warning | all |
| **light while off**: lit while every member's threshold was `Off` (-1), or under PyMCU's `Idle` | **fails** the group | all |
| **no light recorded**: `optogenetics: yes`, and no LED lit on the DFM at all | **fails** the DFM | all |
| **broken yoking**: linked wells' `OnMs` differ by more than 1 ms in more than `opto_yoking_fail_fraction` (1%) of the group's lit records, or an `Off` well linked to a trigger well counted Activations of its own | **fails** the group | 3 |
| **paradigm not in program**: a row names a Paradigm `Program.txt` does not define, so the file belongs to another recording; those rows are not judged | **fails** every group of the DFM | 3 |
| **unlit feeding**: at least `opto_unlit_feeding_fraction` (50%) of the feeding bouts at its trigger wells under closed loop or in Acclimation never lit the group (5 bouts needed) | warning | all |
| **no light events**: feeding at its trigger wells, and never lit | warning | all |
| **open loop not lit**: lit for less than `opto_open_loop_min_lit_fraction` (95%) of an open-loop interval | warning | all |
| **non-feeding light during feeding**: under NonFeeding, lit through more than 10% of the feeding at its trigger wells, and for at least 30 s | warning | 3 |
| **acclimation count mismatch**: a trigger well's completed Acclimation counted a different number of Activations than its Paradigm's `Acclimation` | warning | 3 |
| **firmware events disagree**: under a ratio Paradigm's Main phase, a trigger well's Firmware Events and pyflic's feeding events differ by more than `opto_event_disagreement_warn_fraction` (25%) of the Firmware Events (judged from 5 events) | warning | 3 |
| **lost records**: more than `opto_lost_records_warn` (25) records missing from the DFM's `Index` | warning, DFM | 3 |
| **unknown-instruction rows**: more than `opto_unknown_rows_warn_fraction` (1%) of the rows after the `Idle` lead-in recorded under an instruction outside the program | warning, DFM | 3 |
| **late records**: more than `opto_late_records_warn` (10) records with an `OnMs` above 200 ms | warning, DFM | 3 |
| **program mismatch**: the data's `OptoFreq`, `OptoPW` or `Dark` differ from the program, the data start more than a minute from its Start Time, or (generation 3) the rows name another Paradigm than the printed line | warning | all |
| **no program section**: `Program.txt` has no usable section for the DFM | warning | 1, 2 |
| **no Program.txt for firmware 4.0.0**: a generation-3 DFM without its program | warning | 3 |

The five firmware 4.0.0 checks with constants read the file's own bookkeeping, and none of
their defaults has a real recording behind it yet. Treat a flag from one as a reason to look,
and see [Thresholds](#thresholds).

### Drift or hardware?

Each flagged group gets a `LikelyCause`: **a drifting baseline or sustained contact** when
most of its unexplained light fell where the firmware saw contact and pyflic saw no lick or
touch, otherwise **hardware, linkage or program mismatch**: light the firmware had no reason
to switch on.

**Generation 3 reads the firmware's own decisions.** An Activation, or a Firmware Event (a
rise in `Progress`), with no pyflic lick or touch at its trigger well is the drifting-baseline
signature itself. On these recordings:

- `ContactSec` is the lit time of the trigger wells' Activations: the firmware's contact
  decisions.
- `ContactWithoutActivitySec` is the lit time of the Activations whose onset had no pyflic
  lick or touch at their well.
- `FirmwareEventsWithoutActivity` counts the Firmware Events with none either.

**Generations 1 and 2 emulate the firmware.** With a program, pyflic re-runs the firmware's
own test on the recorded signal: raw minus the mean of the run's first ten seconds, against
the interval's threshold. `ContactWithoutActivitySec` is how long that **emulated trigger**
read a trigger well above threshold while pyflic saw no lick or touch.
`EmulationApproximate` marks it approximate when the data begin more than two seconds after
the program, so the baseline window was not recorded. On generation 3 nothing is emulated and
the column is `NA`.

## Thresholds

The thresholds are design `constants:`, shared by every experiment type, with fields in the
Project Design dialog and the Config Editor. The Config Editor shows them once the
experiment is known to be optogenetic.

| Constant | Default | What it does |
|---|---|---|
| `exclude_failed_opto_chambers` | false | every chamber of a failed group leaves the analysis through auto-removal |
| `opto_unexplained_warn_fraction` | 0.10 | unexplained share that warns |
| `opto_unexplained_fail_fraction` | 0.30 | unexplained share that fails |
| `opto_unexplained_min_sec` | 30 | unexplained seconds needed before either is judged |
| `opto_default_decay_ms` | 1000 | the Hold assumed without a `Program.txt` |
| `opto_decay_tolerance_samples` | 2 | samples of slack around the Hold |
| `opto_unlit_feeding_fraction` | 0.50 | unlit share of closed-loop feeding bouts that warns |
| `opto_open_loop_min_lit_fraction` | 0.95 | lit share an open-loop interval needs |
| `opto_event_disagreement_warn_fraction` | 0.25 | firmware 4.0.0: a trigger well whose Firmware Events and pyflic feeding events differ by more than this share of the Firmware Events warns |
| `opto_yoking_fail_fraction` | 0.01 | firmware 4.0.0: share of a group's lit records in which its linked wells' `OnMs` differ by more than 1 ms, above which the group fails |
| `opto_lost_records_warn` | 25 | firmware 4.0.0: records missing from `Index` (5 s at 5 Hz) above which the DFM warns |
| `opto_unknown_rows_warn_fraction` | 0.01 | firmware 4.0.0: share of the rows after the `Idle` lead-in under an unknown instruction above which the DFM warns |
| `opto_late_records_warn` | 10 | firmware 4.0.0: records with an `OnMs` above 200 ms above which the DFM warns |

The last five apply only to firmware 4.0.0 recordings. Their defaults are first guesses, to
be revisited once real recordings exist.

**Failures are flagged, not excluded, by default.** A faulty light does not invalidate the
feeding record, so a failed group stays in every result with its flags on its chambers'
rows (`OptoLightQC`, `OptoUnexplainedFraction`) until you exclude it by hand or switch
`exclude_failed_opto_chambers` on.

## Outputs

Basic analysis and **QC reports** write, into the member's `qc/opto/`:

| File | One row per | Holds |
|---|---|---|
| `opto_light_qc.csv` | linkage group | `Generation`, wells, trigger wells, chambers, their `Roles`, treatment, lit and unexplained time, onset, the contact evidence, `FirmwareEvents` and `PyflicEvents` under a ratio Paradigm, `AcclimationActivations` and `AcclimationExpected`, `LikelyCause`, `Flags`, `Verdict`, `Excluded` |
| `opto_light_intervals.csv` | group × window | the window's printed `Interval`, and on generation 3, as the rows recorded it, `ProgramInterval`, `Cycle`, `Paradigm` and `ParadigmType`; its mode, the `HoldMs` it was judged with, its trigger wells, `LitSource`; lit, unexplained and contact time; feeding bouts and unlit ones |
| `opto_light_events.csv` | light event | its `Well`, onset, end and duration, interval, `Phase`, the `RequirementMet` and `FirmwareEvents` behind it, `UnexplainedSec`, `Explained`, `OverrunSec` (the light's time past the last lick plus the Hold), and its `Source` |
| `opto_program.csv` | program interval | the program as read: the Paradigm's name and type (`ParadigmType`, as PyMCU spells it) with its settings (`HoldMs`, `ActivationMs`, `LockoutMs`, `Acclimation`, the Requirement series …, `NA` where the type has none), linkage, trigger wells, and for an export older than PyMCU 4.0.0 the raw `F` and `P` it echoed (`LegacyF`, `LegacyP`) |
| `opto_light_dfm<id>.png` | DFM | the QC figure, below |

A light event is a lit run of `OptoCol1` on generations 1 and 2 (`Source` = `optocol1`), and
one Activation of a trigger well on generation 3 (`activations`). The firmware columns are
`NA` before generation 3.

`summary.txt` gains an *Optogenetic light QC* section, and the experiment report a
subsection of Quality control with the program table, the verdicts and the figure. The
figure, **Light explained by licks (QC)**, gives each group a row: its lit time per bin,
explained and unexplained, and beside it the contact with no lick — the emulated trigger's
on generations 1 and 2, the light of Activations with no lick or touch on generation 3
(titled *firmware events, no lick*). A Project's Combined Analysis stacks every member's
verdicts into `<project>_LightQC.csv` with `Source` = `Opto`.

The Hub's QC panel has an **Optogenetics** group whenever the loaded member is
optogenetic: **Opto light QC table**, **Light explained by licks (QC)**, **Program
timeline** and **Light summary CSV**, with the Progressive Ratio light checks beside them for
that type. The Script Editor's actions are `opto_light_qc`, `plot_opto_light`,
`plot_program_timeline` and `light_summary`. The
[QC Viewer](app-qc-viewer.md#the-opto-light-qc-tab) has an **Opto Light QC** tab: the
verdicts, why each group got its own, the figure per group, a Params recompute that updates
them live, and buttons that tick a failed group's chambers for exclusion.

## The light table

The light QC asks whether the light was right. The **light table** asks what it did, and
puts the answer in the feeding summary's shape so it can be pooled and tested like feeding.
Every optogenetic experiment of any type gets one. Basic analysis and **Light summary CSV**
write it into `analysis/`:

| File | One row per |
|---|---|
| `light_summary.csv` | chamber |
| `light_wells.csv` | well |
| `light_summary_facet.csv`, `light_wells_facet.csv` | the same, per Facet, when the experiment has Facets |

Each row carries the Treatment, the design factors, the `Role` and the `Generation`, then:

| Columns | What they hold |
|---|---|
| `Paradigm`, `ParadigmType`, `ProgramInterval`, `Cycle` | what ran over the window, or `mixed` |
| `WindowMinutes`, `LitSec`, `LitFraction`, `LitSource` | the light received: from `OnMs` on generation 3, from `OptoCol1` samples before |
| `LightOnsets` | times the light came on; on generation 1 the nearest thing to an Activation count |
| `Activations`, `ActivationsPerHour` | on-periods the well's own Paradigm started |
| `AcclimationActivations`, `AcclimationEndMin`, `AcclimationComplete` | FixedInterval and ratio Paradigms with Acclimation |
| `FirmwareEvents`, `LastRequirementMet`, `ProgressAtEnd`, `EventsPerActivation` | ratio Paradigms |
| `LockedOutContactSec` | FixedInterval: feeding while the lockout kept the light off |
| `UnlitSec`, `Suppressions` | NonFeeding: time dark, and times the light went out |
| `PyflicEvents`, `PyflicLicks` (per well); `EventsA`, `EventsB` (per chamber) | pyflic's own count, for comparison |

A chamber row sums its wells' counts. Its `LitSec` is the chamber's own light, counted once
however many of its wells were lit, its `AcclimationEndMin` the latest of its wells', and
`AcclimationComplete` true only when all of them finished.

A column is `NA` wherever the well ran no Paradigm of a type that defines it, and every
type-dependent column is `NA` without the DFM's `Program.txt` section. On generations 1 and
2 every firmware column is `NA`. The baseline before the first instruction and rows under an
unknown instruction count toward the light but never toward `Paradigm`.

**The four headline metrics** — `Activations`, `LitSec`, `FirmwareEvents` and
`AcclimationEndMin` — are tested between treatments by default. They appear in the
experiment report's **Light behaviour** section and the Project Report's, and as faceted
Publication Figures in the [Plot Editor](app-plot-editor.md). A Progressive Ratio yoked
chamber's light is its partner's, so those comparisons use the paired chambers only.

Every optogenetic `feeding_summary.csv` row also carries its chamber's `Role`, `LitSec` and
`Activations`. A Project's Combined Analysis stacks the members' tables into
`<project>_LightSummary.csv` and `<project>_LightWells.csv` (and their `_Facet` variants),
with `Experiment` first.

## Program Facets

With `facet_source: program` in the design, every **Program Interval** of a DFM's program is
a [Facet](concepts-facets.md#program-facets), labelled by its Paradigm's name: every metric
is split by what the program ran. `program_cycles` separates the passes of a Repeating
program. On a generation-3 recording the Facets come from the rows themselves; on an older
one from the program's clock schedule, noted as approximate.

## The Program timeline

One figure per DFM: what its program ran, and what each well did.

- **The top band** is the Program Intervals, coloured by Paradigm type and labelled by
  Paradigm name, with the Cycle of a repeating program. Light grey is the baseline before
  the first instruction, hatched white an unknown instruction, and dark grey a Paradigm
  whose type is unknown, because `Program.txt` does not define it or is missing.
- **Below it, one lane per well**, its chamber and Role in the label: its Acclimation
  (Phase `A`) shaded, each Activation as a tick, and the share of each bin its LED was on as
  a blue strip.

A generation-3 recording draws all of this from its own rows. A generation-1 or 2 recording
with a `Program.txt` section gets the band from the program's clock schedule, approximate,
and the lanes show `OptoCol1` only. With neither there is nothing to draw.

**QC reports** write it to `qc/program/program_timeline_dfm<id>.png` for every DFM that has
one, and basic analysis for every generation-3 DFM, in an optogenetic experiment only: a
recording whose light never came on has nothing for it to show. It appears in the report's Quality
control section, behind the Hub's **Program timeline** button (`plot_program_timeline`),
and with each well's state at the end of the loaded range in the
[QC Viewer](app-qc-viewer.md#the-program-sub-tab)'s **Program** sub-tab. See
[Reading the Program timeline](plots-catalog.md#program-timeline).

## Progressive Ratio

A [Progressive Ratio](concepts-progressive-ratio.md) experiment gets this light QC as well
as its own, which asks whether the paired fly earned each light event. The program serves
both:

- **Paired chambers from the program.** With a `Program.txt`, a DFM entry may leave
  `paired_chambers` out: in each chamber group the chamber holding the trigger well is the
  paired one. When both are given and disagree, the config wins and `summary.txt` says so.
  A trigger well that is well B is flagged, because the Sucrose Well is always well A.
- **Hold-aware lick-free events.** A light event is lick-free only when it is credited
  with no Sucrose Well licks *and* has no lick or touch within its Hold, the program's or
  `opto_default_decay_ms`. A light the fly touched for is never counted against it.
- **Both ratio Paradigms.** The type covers ProgressiveRatio and FixedRatio.
- **A type mismatch is reported.** A program running a ratio Paradigm under another
  experiment type, or a Progressive Ratio experiment whose program runs none, is noted in
  `summary.txt` and the report.

---

Related: [Light state and phase analysis](concepts-light-phase.md) ·
[Progressive Ratio experiments](concepts-progressive-ratio.md) ·
[Facets](concepts-facets.md) · [Exclusions](concepts-exclusions.md) · [Reports](reports.md)
