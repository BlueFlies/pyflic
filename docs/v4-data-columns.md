# The firmware 4.0.0 data columns, and what pyflic does with them

DFM firmware 4.0.0, recorded with PyMCU 4.0.0, adds 63 columns to every DFM
data file. They record what each well's light program was doing, every 200 ms:
which step of the program was running, whether each fly was still in
Acclimation, how many light periods it had earned, and exactly how long its LED
was on. This page explains the new columns and where they show up in pyflic.

For the full column-by-column reference, see
[Firmware 4.0.0 data in pyflic](firmware-4-data-in-pyflic.md). For how to read
the QC results, see [Checking your data](qc-user-guide.md).

---

## Which kind of file do you have?

pyflic decides this from each DFM file when it loads, and names it in
`summary.txt` and on the report's cover as the file's **Generation**.

| Generation | What it is | What pyflic can do |
|---|---|---|
| **1** | 27 columns, from PyMCU 3.x | Everything it did before. Progressive Ratio training is read from a flag inside the signal. |
| **2** | 90 columns, the new ones all `NA`: the new PyMCU with a DFM that still runs older firmware | Feeding analysis as usual. There is **no training information** at all, so a Progressive Ratio experiment is analysed as one "Recording" phase and says so. |
| **3** | 90 columns, filled: firmware 4.0.0 | Everything below. |

Feeding itself is still measured from the well signals, `W1`–`W12`, exactly as
before. The new columns describe the light.

---

## The new columns

Each per-well column has one copy per well, numbered 1–12 like `W1`–`W12`.

| Column | What it records | What pyflic uses it for |
|---|---|---|
| `Interval` | Which step of the program was running: 1 for the first, and so on. `0` marks the few seconds of baseline before the program reached the DFM. | Splitting the recording by program step: the light QC judges each step by its own rule, and **Program Facets** can split every result by step. pyflic's own tables call it `ProgramInterval`. |
| `Cycle` | Which pass through a Repeating or Circadian program. | Telling the passes apart, when you ask for one Facet per pass. |
| `Paradigm` | The name of the light rule in force, as written in the program. | Looking up the rule's type and settings in `Program.txt`. Labels the Program Facets and the Program timeline. |
| `Phase` | `A` while a well is in Acclimation, `M` (Main) after. | **Progressive Ratio training end**: the paired sucrose well's first Main row under the ratio rule. Also the light table's Acclimation columns and a QC check that each fly got the number of Acclimation light periods it should. |
| `Activations` | A running count of the light periods each well's own rule started. A well lit only through its partner never counts one. | **Light Events** in Progressive Ratio; the light table's `Activations`; the light QC, which asks whether each light period had a lick behind it; roles (a yoked well has light but no Activations). |
| `Requirement` | Under a ratio rule, how many feeding bouts the well needs for its next light period. | The ratio each light period met, which a Progressive Ratio breaking point now reports as `BreakRequirement`. |
| `Progress` | Under a ratio rule, how many bouts the well has made toward that Requirement. | **Firmware Events**: the feeding bouts the firmware counted, compared with pyflic's own count of feeding events as a QC check. |
| `OnMs` | How many of the record's 200 ms the well's LED was on, from any cause. | **Exact light time**: `LitSec` in the light table, the `OptoOn_sec` columns of the feeding summary, and the lit time the light QC judges. Older files can only sample the light once every 200 ms. |

A value that does not apply is written `NA`: for example `Requirement` and
`Progress` on a well that is not under a ratio rule. `NA` means "not
applicable", not lost data.

---

## Original columns that now mean slightly more

| Column | What changed |
|---|---|
| `W1`–`W12` | Always the plain signal. Older files added 65536 to a well in training; the new firmware reports training in `Phase` instead. |
| `Dark`, `OptoFreq`, `OptoPW` | Taken from the program step that was running. The light QC checks them against `Program.txt`. |
| `OptoCol1` | Still the LEDs lit at the instant of each record. On firmware 4.0.0 pyflic measures light from `OnMs` instead; `OptoCol1` remains the source for older files. |
| `Error` | Labelled by generation in the integrity report: on firmware 4.0.0, 0x01 is *No Ack* and 0x02 is *Overflow*. |
| `Index` | The DFM's record counter. A gap is records lost on the way to the MCU; the integrity report counts them as **lost records**. |

---

## `Program.txt` still matters

The data file names each row's light rule, but not its type, its settings, the
threshold of each well or which wells are linked. Those are only in the
`Program.txt` the MCU writes into the recording folder. **Copy it into the
experiment's `data/` folder.**

Without it, pyflic still reads Phase, Activations and light time, and works
out which wells trigger and which are linked from the data. It cannot tell
which rule each step followed, so results that depend on the rule are `NA`, and
pyflic warns in `pyflic lint`, in `summary.txt`, on the report and in the Hub.

A recording started without a program (`***ALL DFM***` at the top of
`Program.txt`, every well Off) is analysed as an ordinary feeding experiment.

---

## Where you see it

- **The feeding summary** (`analysis/feeding_summary.csv`) of an optogenetic
  experiment gains `Role`, `LitSec` and `Activations` for each chamber.
- **The light table** (`analysis/light_summary.csv` per chamber,
  `light_wells.csv` per well) holds what the light did: lit time, Activations,
  Acclimation, Firmware Events, the last ratio met, and each rule's own
  measures. It carries the same Treatment and factor columns as the feeding
  summary, so it pools, plots and is compared between treatments the same way.
  A Project stacks it into `<project>_LightSummary.csv`.
- **Reports** gain a *Light behaviour* section: Activations, lit time,
  Firmware Events and the end of Acclimation, by treatment, with the
  comparisons. The Plot Editor offers the same metrics as publication figures.
- **Progressive Ratio** reads training, light events and the ratio met
  straight from the recording. `pr_light_events.csv` gains `Requirement`,
  `FirmwareEvents` and `Phase`; `pr_breaking_point.csv` gains
  `BreakRequirement`, `FirmwareEvents` and `ParadigmType`. The breaking point
  rule itself is unchanged. Fixed ratio programs are supported too.
- **Program Facets.** Set `facet_source: program` in the Project design, and
  every summary is split by program step, each labelled with its rule's name.
- **The optogenetic light QC** judges each rule by its own logic, one light
  period at a time, from the firmware's own record. It adds checks for yoked
  wells whose light differs, a rule name missing from `Program.txt`, an
  Acclimation count that is off, Firmware Events that disagree with pyflic's
  events, and lost, late or unknown records.
- **The Program timeline** (`qc/program/`, the report's Quality control, the
  Hub's QC panel and the QC Viewer's *Program* tab) draws each DFM's program
  steps, and for each well its Acclimation, its Activations and its light.
- **The integrity report** counts lost, repeated, late and unknown-instruction
  records and lists `Messages.csv`'s errors.

---

## Worth knowing

- **The baseline rows** at the start (`Interval` 0, a few seconds) count
  toward whole-recording feeding totals, but toward no program step and no
  light judgement.
- **Activations are a well's own; `OnMs` is the light it received.** In a
  paired and yoked design, the yoked fly's wells show light with zero
  Activations. pyflic uses that to tell the roles apart, and to check the
  yoking.
- **The Requirement a light period met is on the row before it.** The firmware
  moves to the next Requirement in the same millisecond it starts the light,
  so the row where `Activations` rises already shows the next one. pyflic reads
  the row before.
- **`OnMs` above 200** means a record arrived late. A few are harmless; many
  are flagged as *late records*.
- **Nothing here changes how feeding is detected.** Licks and feeding events
  come from the well signals and your detection parameters, on every
  generation.
