# Paradigm analyses plan: a light QC and a summary for each Paradigm type

The plan for giving each Paradigm type of the firmware 4.0.0 program language
its own light QC, its own summary columns and its own report content, under
every Experiment Type. It follows [v4-data-plan.md](v4-data-plan.md), which
made pyflic read the new data, and begins with a check of pyflic against the
firmware and PyMCU as they stood on 10/17/2026.

**Status (2026-10-18): implemented** on `v4_Dev`, all 19 decisions: streams
P0 to S5 merged by ab0b9cd, and S6's help, guides and records on top of it.
Where the build departed from the plan is under [As built](#as-built). Still
open: the bench recordings of each type that recalibrate the constants (see
[Not in this plan](#not-in-this-plan), and the bench checkpoint in
[firmware-4-data-in-pyflic.md](firmware-4-data-in-pyflic.md#bench-checkpoint-for-the-paradigm-analyses)).
The fixes listed under [Where pyflic stands](#where-pyflic-stands) as *fixed*
were done first (55c4315). The decision and its reasons are in
[adr/0017](adr/0017-paradigm-families-not-experiment-types.md), with an
addendum to [adr/0015](adr/0015-the-opto-program-and-a-light-qc-for-every-type.md)
for the new checks' severities.

Terms are [../CONTEXT.md](../CONTEXT.md)'s: *Paradigm*, *Paradigm Family*,
*Program Interval*, *Activation*, *Hold*, *Requirement* / *Progress*,
*Firmware Event*, *Phase* / *Acclimation*, *Role*, *Linkage Group*, *Trigger
Well*. The firmware's rules are DFMV3_V2's `src/LEDControl.c`, which is the
authority; PyMCU's `docs/ProgramFormat.md` states them in words.

- [Where pyflic stands](#where-pyflic-stands)
- [What the user gets](#what-the-user-gets)
- [Paradigm Families](#paradigm-families)
- [Decisions](#decisions)
- [Stream P0: current with upstream, and the shared contract](#stream-p0-current-with-upstream-and-the-shared-contract)
- [Stream S1: rule checks](#stream-s1-rule-checks)
- [Stream S2: summary columns and headline metrics](#stream-s2-summary-columns-and-headline-metrics)
- [Stream S3: reports, figures and views](#stream-s3-reports-figures-and-views)
- [Stream S4: Progressive Ratio](#stream-s4-progressive-ratio)
- [Stream S5: the yoked comparison for every type](#stream-s5-the-yoked-comparison-for-every-type)
- [Stream S6: help, guides and records](#stream-s6-help-guides-and-records)
- [Delivery](#delivery)
- [As built](#as-built)
- [Not in this plan](#not-in-this-plan)

---

## Where pyflic stands

The v4 work was built against PyMCU 5d7d897 and DFMV3_V2 f353c1e. By
10/17/2026 PyMCU had ten more commits (to 6d1aa42) and the firmware one
(024b692).

| Upstream change | What it meant for pyflic | Status |
|---|---|---|
| **Acclimation counts every time the LED comes on** (firmware 024b692). A fly back within the Event gap after the light went off gets a new Activation, not a new Event. | The simulator followed the old rule. The light-events table credited each Acclimation Activation with one Firmware Event. | **Fixed.** The simulator follows the new rule: the firmware cross-check passes all eight comparisons, and fails five with the old rule. `opto_light_events.csv` leaves `FirmwareEvents` empty for Acclimation Activations. Help and glossary updated. |
| **The exponential series** gives the Cap on overflow, and Scale 0 gives 1 (firmware 024b692). | `Paradigm.requirement_for` raised `OverflowError` past a float's range. It computed in double precision, which rounds one checked case differently from the firmware's single precision. | **Fixed**, and matched against the simulator's firmware copy over 78,792 settings. |
| **`Messages.csv`** is written with the csv module: a message holding a comma is quoted, and repeats within 10 minutes are folded into one line (PyMCU d148926). New wording for lost records, restarts and error bits. | The reader kept the quotes and counted a folded line once. | **Fixed.** Both writers are read, with a `Repeats` column; the QC Viewer counts repeats. |
| **A bout that starts during an Activation is not an Event**, even if it outlasts it. This is a clarification in PyMCU's docs, with a new firmware test; the code already did this. | *Firmware events disagree* compares the firmware's count with pyflic feeding events, including those that start during an Activation. | Decision 16. |
| **A DFM that restarts on its own** (PyMCU 529b926): `Index` and the times carry on across the gap. Rows have `NA` Interval until PyMCU resends the instruction. The Paradigm state starts over, and the Activation totals carry on. | pyflic flags the gap and the `NA` rows, but treats the Paradigm state as continuous across them. | Decision 15. |
| **No Ack after every read**: firmware 4.0.0 treats a partial ACK naming every record as a missed ACK, fixed in PyMCU 19efddd. | Recordings from earlier PyMCU builds show large *No Ack* counts in the integrity report, with nothing lost. Nothing is flagged, because error bits are only counted. | Stream P0: the report explains it. |
| `Requirement` is reported during Acclimation. OpenLoop and `On` wells never count Activations. The baseline's first 10 readings are dark, even under OpenLoop. | Already assumed. | Confirmed. |
| **PyMCU's own simulator** (`scripts/simulate_recording.py`): simulated flies, run through PyMCU's real record parser and file writer, with a truth folder. | An independent end-to-end check. | **Run**, on two DFMs over two hours of Progressive Ratio. pyflic's light table matched the truth exactly for all twelve triggering wells on Activations, Acclimation Activations, last Requirement met, Progress at end and lit time. Acclimation end agrees to within one record once the time origins are aligned: the truth counts from the start of record 1, pyflic's `Minutes` from the first row's time stamp, 0.57 s apart here. The Progressive Ratio type could not load the design, which has no yoked controls (decision 13). |
| 27 records per reply, interrupt-safe error flags, bus fixes, a 512 Hz masking fix. | No effect on the files. | Nothing to do. |
| Fine mode (firmware 4.1.0). | Still a plan in PyMCU. | Not in this plan. |

To run PyMCU's simulator on Windows, its Pi-only hardware modules (smbus2,
busio, board, adafruit_*) and the "fork" process context need stand-ins. The
launcher used for the check above becomes a test helper in stream P0
(decision 17).

---

## What the user gets

- **Every Paradigm type is checked against its own rule**, with the
  program's settings, one light period at a time:
  - closed loop: the light lasts its Hold and never passes `MaxOnMs`;
  - FixedInterval: each light period is exactly `ActivationMs`, and the
    lockout is kept;
  - ratio types: each light period is exactly `ActivationMs`, and every
    Requirement follows the program's series;
  - NonFeeding: the light goes dark during feeding and comes back after
    `OnDelayMs`;
  - open loop: the light follows the schedule, Interval by Interval.

  A check that fails because the data disagree with `Program.txt` says that
  the file is probably not the program that ran.
- **The report's Quality control** gains one subsection per Paradigm in the
  program. Each states the rule in words with its settings, has a table per
  Linkage Group, and has one figure that puts the measured light against the
  rule's setting:
  - lit time per light period, against the Hold and `MaxOnMs`;
  - spacing between light periods, against the lockout;
  - Requirement met against light-period number, over the series;
  - the relight delay, against `OnDelayMs`.
- **The light table gains the measures each rule makes meaningful**:
  - closed loop: the median light period and the cut-offs;
  - FixedInterval: reward efficiency, return time after the lockout, and
    feeding while locked out;
  - NonFeeding: suppressions and their length;
  - open loop: feeding in light against feeding in dark.

  The report's *Light behaviour* results show the headline measures of the
  rules actually run, instead of the same four for every program.
- **Paired and yoked designs under any Experiment Type** get the comparison
  Progressive Ratio already has: the paired fly's feeding minus its yoked
  partner's, by treatment. Yoked chambers no longer sit in light statistics
  that their light only copies.
- **Progressive Ratio accepts designs without yoked controls**, which is
  PyMCU's reference design, and finishes its Fixed Ratio wording.
- **A DFM that restarts mid-recording** is named in the integrity report and
  the light QC, and the analysis treats its Paradigm state as starting over.

---

## Paradigm Families

A **Paradigm Family** is a group of Paradigm types that pyflic checks and
summarises with the same code, because the firmware lights them by the same
mechanism. A type gets its own check only where its rule adds a setting that
the family's rule lacks.

| Family | Types | The firmware's rule | Type-specific additions |
|---|---|---|---|
| **Open loop** | OpenLoop; any well set `On` | Lit for the whole Interval (`OnMs` 200 in every record) after the baseline. Never counts Activations. | none |
| **Closed loop** | ClosedLoop; the Acclimation of FixedInterval, ProgressiveRatio and FixedRatio | Contact lights the LED, and it stays lit for the Hold after contact ends (`HoldMs`, or `ActivationMs` in Acclimation). Each on-period is one Activation. | ClosedLoop with `MaxOnMs`: an Activation is cut off after `MaxOnMs`, then stays dark until the bout ends (`EventGapMs`). Acclimation: N Activations per well, then Main. |
| **Fixed length** | FixedInterval, ProgressiveRatio and FixedRatio, in Main | An earned Activation lasts exactly `ActivationMs`. | *Interval* branch (FixedInterval): contact earns it once `LockoutMs` from the previous start has passed. *Ratio* branch (PR, FR): the Event that meets the Requirement earns it, and the Requirement follows the series or the Ratio. |
| **Non-feeding** | NonFeeding | Dark during contact; lit `OnDelayMs` after contact ends, for at most `MaxOnMs` (0 = no limit); lit at the Interval's start without contact. Each on-period is one Activation. | none |

`Off` wells belong to no family. Their check, *light while off*, and the
yoking checks apply across families, as today.

### Today and after this plan

| Family | Light QC today | Light QC added (generation 3) | Light table today | Light table added |
|---|---|---|---|---|
| Open loop | lit fraction over the window (*open loop not lit*) | lit fraction **per Program Interval**, so one dark pass of a Repeating program shows; *interval started late* (every family) | LitSec, LitFraction | LicksPerMinLit, LicksPerMinDark, LightFeedingIndex |
| Closed loop | explained light; *unlit feeding*; *no light events*; Acclimation count | *short activations*; *max on exceeded*; cut-offs counted | LitSec, Activations, the Acclimation columns | MedianActivationSec, CutOffs, MainActivations |
| Fixed length, Interval | onset backed by contact | *wrong activation length*; *lockout broken*; *contact without activation* | LockedOutContactSec, defined from `OnMs == 0`, so linked light hides it | LockedOutContactSec from the well's own lockout; MaxActivations, RewardEfficiency, MedianReturnSec |
| Fixed length, Ratio | onset backed by contact; Acclimation count; *firmware events disagree* (like with unlike, decision 16) | *wrong activation length*; *requirement series wrong* | FirmwareEvents, LastRequirementMet, ProgressAtEnd, EventsPerActivation | MainActivations |
| Non-feeding | *non-feeding light during feeding*, on borrowed constants; a NonFeeding light that never comes on goes unflagged | its own constants; *non-feeding dark*; *max on exceeded*; the relight delay reported | UnlitSec; Suppressions, counted per record, which also counts `MaxOnMs` ends | Suppressions from the light periods themselves; MedianSuppressionSec |

The settings `MaxOnMs`, `LockoutMs`, `OnDelayMs`, `EventGapMs` and the series
are parsed today but used by no check. Of the light-table measures, only
Activations, LitSec, FirmwareEvents and AcclimationEndMin reach a report.

---

## Decisions

All accepted on 2026-10-17. The streams implement them; a stream that finds
one unworkable stops and reports rather than deciding otherwise.

**Scope**

1. **Families, not Experiment Types.** No Experiment Type per Paradigm. The
   Experiment Type describes the feeding design: layout, PI, Training and
   Test. The Paradigm describes the light, and one program can mix types
   across DFMs and Intervals. Content follows the Paradigm types in
   `Program.txt`, under every Experiment Type. ADR-0017 records this on
   acceptance.
2. **Four Paradigm Families**, as tabled above. The code is shared per
   family. A type gets its own check only for a setting the family lacks:
   `MaxOnMs`, `LockoutMs`, or the Requirement series.
3. **The new checks run on generation 3 only.** `OptoCol1` snapshots every
   200 ms cannot time a light period. Generations 1 and 2 keep today's
   checks, and the report names the checks that did not run and why.

**The shared record**

4. **One ledger, extended.** `qc/opto/opto_light_events.csv` already has one
   generation-3 row per Activation, and it gains:
   - `OnsetMs` and `EndMs`, to the millisecond: at the edges of a light
     period, `OnMs` says how much of the record was lit;
   - `LitMs`, the `OnMs` summed over the period;
   - `Overlap`, true when a linked partner's light merges with it, so its
     length cannot be read;
   - `EndedBy`: contact, Hold, `MaxOnMs`, Interval change, restart, or
     unknown;
   - `SinceLastOnsetMs`;
   - `K`, its number among the Main Activations of its Paradigm-state run;
   - `Family`.

   Every family check and summary aggregates the ledger. Nothing re-reads
   the rows. The pure columns come from the Paradigm state alone (P0, C3).
   `EndedBy` needs the program's settings and pyflic's contact, so S1 adds
   it (C4).
5. **Judged against `Program.txt`.** When the data disagree with the program
   on a length, the lockout or the series, the reason says the likely cause:
   the file is not the program that ran. *Program mismatch* already does this
   for frequency, pulse width and Dark.

**The light QC**

6. **Severities.** These fail a Linkage Group, because the firmware is
   deterministic, so a miss means a wrong program or broken hardware:
   *wrong activation length*, *lockout broken*, *requirement series wrong*,
   *max on exceeded* and *short activations*. These are warnings, because
   they rest on pyflic's lick detection against the firmware's threshold:
   *contact without activation*, *non-feeding dark* and *interval started
   late*.
7. **Each new check has its own constants**, never borrowed, editable in the
   Opto editors. The starting defaults are below. They are calibrated on the
   simulator and PyMCU-simulator recordings, and revisited after the first
   bench recordings of each type.

   | Constant | Default | Used by |
   |---|---|---|
   | `opto_activation_tolerance_ms` | 25 | length, lockout and MaxOn checks |
   | `opto_activation_length_fail_fraction` | 0.05 | *wrong activation length*, *short activations* |
   | `opto_lockout_fail_fraction` | 0.02 | *lockout broken* |
   | `opto_missed_contact_warn_fraction` | 0.25 | *contact without activation* |
   | `opto_non_feeding_lit_warn_fraction` | 0.10 | *non-feeding light during feeding*, replacing the borrowed unexplained fraction |
   | `opto_non_feeding_min_sec` | 30 | the same, replacing `opto_unexplained_min_sec` |
   | `opto_non_feeding_dark_warn_fraction` | 0.10 | *non-feeding dark* |
   | `opto_interval_lag_warn_sec` | 5 | *interval started late* |

   *Max on exceeded* and *requirement series wrong* fail on any one case.
   They cannot happen on a working system with the right program.

**Summaries**

8. **Summary columns by family**, as tabled above. They go into
   `light_wells.csv` and `light_summary.csv`, and are `NA` outside their
   family, as the type columns are today. Definitions:
   - **MedianActivationSec**: the median `LitMs` of the unoverlapped
     Activations, in seconds.
   - **CutOffs**: Activations ended by `MaxOnMs`; `NA` without it.
   - **MainActivations**: Activations minus AcclimationActivations.
   - **MaxActivations**: the window divided by max(`LockoutMs`,
     `ActivationMs`).
   - **RewardEfficiency**: Activations divided by MaxActivations.
   - **MedianReturnSec**: the median time from a lockout's end to the next
     Activation.
   - **LicksPerMinLit** and **LicksPerMinDark**: by the chamber's own
     light.
   - **LightFeedingIndex**: (lit − dark) / (lit + dark) of those rates; `NA`
     when either phase is absent.
   - **MedianSuppressionSec**: the median dark period that contact caused.
9. **Headline metrics by family** replace the fixed four of v4 decision 16.
   *Light behaviour* gets one subsection per family in the member, each
   with its own headline set:

   | Family | Headline set |
   |---|---|
   | Open loop | LitSec, LightFeedingIndex |
   | Closed loop | Activations, LitSec, MedianActivationSec, and CutOffs with `MaxOnMs` |
   | Fixed length, Interval | Activations, RewardEfficiency, MedianReturnSec |
   | Fixed length, Ratio | Activations, LastRequirementMet, FirmwareEvents |
   | Non-feeding | LitFraction, Suppressions |
   | Acclimation, when any | AcclimationEndMin |

   A Project pools them per family.
10. **LockedOutContactSec and Suppressions are redefined** from the ledger.
    The first becomes lick time while the well's own lockout runs with no
    Activation lit. The second becomes the light periods that contact
    ended. Today's definitions let linked light hide lockout feeding, and
    count per 200 ms record, including the end of a `MaxOnMs` period. The
    CHANGELOG names the change.
11. **Feeding in light and dark is shown for Open-loop chambers only.** Their
    light does not depend on behaviour. Under closed loop the light is
    caused by feeding, so the comparison would mislead, and it is not shown.

**Designs**

12. **The yoked comparison for every Experiment Type.** It applies wherever
    the Roles show a Paired and a Yoked chamber in one Linkage Group, for
    example a yoked ClosedLoop design under Custom. It reports the paired
    minus yoked difference of the feeding metrics by treatment, with the
    same one-sample test as Progressive Ratio. Activation-based light
    statistics use the chambers that earn light (Paired, Self, Mutual).
    Yoked chambers' light is reported beside them, not pooled with them.
    Today, under Custom, yoked chambers are pooled into the Light behaviour
    statistics.
13. **Progressive Ratio takes unyoked designs.** Chamber Groups come from
    `Program.txt`'s Linkage. A group that lights one chamber is a solo group:
    its chamber is Paired, and it has no Yoked chamber. Without `Program.txt`,
    the config says so, with `chamber_groups: single` beside
    `paired_chambers`. The paired-minus-yoked parts are skipped for solo
    groups, and the report says why.
14. **Fixed Ratio wording is finished.** The "estimated requirement
    increment" paragraph and the "a working progressive ratio climbs"
    caption appear for progressive programs only.

**Upstream and validation**

15. **A DFM restart** is found in the data: an `Index` jump followed by `NA`
    Interval rows mid-recording. `Messages.csv` confirms it when present.
    Then:
    - Paradigm-state runs split at the restart, so Acclimation counts, the
      Main-Activation number K, and the series check start over there.
    - The integrity report lists each restart with the time missing.
    - The light QC warns on that DFM's groups (*DFM restarted*), and the
      Program timeline marks it.
    - A Progressive Ratio group whose Test phase spans a restart has its
      breaking point censored at the restart, because the ratio starts
      again after it.
16. ***Firmware events disagree* compares like with like.** pyflic feeding
    events that start while the well's own Activation is lit are left out of
    pyflic's count, as the firmware leaves them out of its own.
17. **Two independent checks.**
    - PyMCU's simulator becomes an optional slow test, beside the firmware
      cross-check. It runs when the PyMCU checkout and a Python with numpy,
      pyserial and cobs are found, through the stand-in launcher. It
      compares the light table and the Progressive Ratio outputs with
      PyMCU's truth.
    - pyflic's simulator gains fault injection: a `Program.txt` that differs
      from what ran, a dead or stuck LED, and dropped Activations. Each new
      flag is shown to fire on a real-shaped cause and to stay quiet on
      clean data.
18. ***Interval started late*** (every family): the first row of each
    Program Interval is compared with its `Program.txt` timestamp, on every
    pass of a Repeating or Circadian program. PyMCU now resends an
    instruction the DFM did not take up, and this shows when that happened.
19. **Acclimation stays columns, not Facets, outside Progressive Ratio.**
    MainActivations joins the existing Acclimation columns. Splitting every
    result at each chamber's own Acclimation end, as Progressive Ratio's
    Training and Test do, is deferred.

---

## Stream P0: current with upstream, and the shared contract

P0 runs before the other streams, as two agents. **P0-sim** works on the
simulator and the Paradigm state (C1, C2) together with the integrity work
(C6). **P0-ext** works on the PyMCU-simulator test (C8) in parallel, because
it touches neither. A third agent, **P0-ledger**, then builds the ledger,
the registry and their wiring (C3, C4, C5, C7) on P0-sim's merge. The
contract below is what streams S1 to S5 build on. A stream that needs
something this contract lacks adds it in its own module and says so in its
report. It does not change the contract.

### C1. The simulator (`tests/v4_fixtures.py`)

**Restarts.** `DFMSpec.restarts: tuple[Restart, ...] = ()`, with
`@dataclass(frozen=True) class Restart: at_s: float; down_s: float = 5.0;
resend_s: float = 1.0`. A restart at `at_s` seconds from the recording start
runs as PyMCU 529b926 and the firmware do:

- **Down for `down_s`.** No records are written: `Index` and the times jump
  by `round(down_s * 1000 / 200)` records, as PyMCU's offset makes them. No
  light is lit and no contact is counted.
- **Then `resend_s` of idle rows.** `Interval`, `Cycle` and `Paradigm` are
  `NA`; Phase is `M`; `Requirement` and `Progress` are `NA`; `OnMs` is 0;
  `Dark`, `OptoFreq` and `OptoPW` are 0. `Activations` carries its totals,
  because PyMCU carries them.
- **Then the instruction in force is applied afresh.** Every well starts as
  under a new Paradigm: Phase `A` where the Paradigm has Acclimation, the
  Requirement series from k = 1, `Progress` 0, no lockout running.
- **The truth** gains `restarts_ms: list[tuple[int, int, int]]`: the ms the
  DFM went down, the ms the instruction applied again, and the records
  missing. The truth's Activation and Acclimation lists include what
  happened after the restart.
- **`Messages.csv`** gets PyMCU's two errors, worded exactly as
  `DFM._StartRestart` and `DFM._FinishRestart` word them. "DFM {id}
  restarted: its record count went back from {last} to 1. Its Paradigm state
  and Activation counts started again. Sending its Interval and linkage
  again." is dated at the first record after the outage. "DFM {id} recorded
  nothing for about {s:.0f} s while it restarted: Index {a} to {b} are
  missing." follows it.

**Faults**, as new keyword arguments of `write_v4_recording`:

- `program_paradigms: Mapping[str, ParadigmSpec] | None`: `Program.txt` is
  written with these definitions in place of the spec's. They have the same
  names and different settings: the wrong `Program.txt`.
- `on_ms_faults: Mapping[int, Sequence[OnMsFault]] | None`, with
  `OnMsFault(well, start_s, end_s, on_ms)`. In the records within
  `[start_s, end_s)`, that DFM's `OnMs{well}` is set to `on_ms`, and its
  `OptoCol1` bit is set exactly when `on_ms > 0`. Linkage is not applied.
  This models a corrupted or misreported LED.

**Specs.** `family_specs() -> dict[str, RecordingSpec]` returns one spec per
edge case, each about 20 minutes long, with bouts that exercise the rule:

| Key | What it runs |
|---|---|
| `closed_max` | ClosedLoop, Hold 500 and `MaxOnMs` 2000, with bouts longer than 2 s and short ones |
| `fixed_interval` | DFM 1: FixedInterval with `ActivationMs` 1000 and `LockoutMs` 10000. DFM 2: `LockoutMs` 500 and `ActivationMs` 1500, with Acclimation 3 |
| `non_feeding` | DFM 1: NonFeeding, `OnDelayMs` 1000, `MaxOnMs` 0. DFM 2: `MaxOnMs` 5000 |
| `exponential` | ProgressiveRatio, Exponential (Scale 5, Rate 0.2), Acclimation 2 |
| `restart` | DFM 1: FixedRatio 3 with Acclimation 2, restarting in Main. DFM 2: ClosedLoop, restarting mid-bout |

The existing `fixed_ratio_spec`, `yoked_controls_spec`,
`repeating_open_loop_spec` and `stress_spec` stay as they are.

**Acceptance.** The firmware cross-check passes on every new spec except
`restart`; a restart is PyMCU's and the power supply's doing, not
`LEDControl.c`'s. `restart`'s rows match its truth. The new keyword
arguments change nothing when absent.

### C2. `ParadigmState` (`pyflic/base/paradigm_state.py`)

- `@dataclass(frozen=True) class RestartSpan: row: int; resume_row: int;
  missing: int; minute: float`. `row` is the first unknown-instruction row
  after the gap, `resume_row` the first row after that run, `missing` the
  records the gap lost, and `minute` is `minutes[row]`.
- `restarts() -> list[RestartSpan]` finds each `Index` gap whose next row
  begins a run of unknown-instruction rows (`Interval` `NA`, after the
  lead-in). This is the data's rule. `Messages.csv` confirms it in C6.
- `state_runs() -> list[tuple[int, int]]` gives `[i0, i1)` of each
  Paradigm-state run: rows between consecutive Paradigm starts, which already
  include the start after a restart's `NA` rows. It is the public face of the
  existing `_paradigm_starts`.
- **Nothing else changes behaviour.** `training_end` stays the first Main
  row under a ratio Paradigm, so a restart does not move Training.
  `acclimation_end` stays the end of the first Acclimation run.

### C3. The ledger (`pyflic/base/activation_ledger.py`)

```python
LEDGER_COLUMNS = ("Well", "Row", "EndRow", "Index", "OnsetMin", "OnsetMs", "EndMs", "LitMs",
                  "Timing", "Overlap", "Boundary", "SinceLastOnsetMs", "Phase", "K",
                  "Paradigm", "ProgramInterval", "Cycle", "RequirementMet")
TIMING_EXACT, TIMING_RECORD = "exact", "record"
BOUNDARY_INTERVAL, BOUNDARY_GAP, BOUNDARY_END = "interval", "gap", "end"

def ledger(state: ParadigmState, *, wells=None,
           linked: Mapping[int, Sequence[int]] | None = None,
           record_ms: int = RECORD_MS) -> pd.DataFrame
```

It is pure, with no program, no pyflic events and no Qt. It returns one row
per Activation (`state.activation_onsets(well)`) of each well in `wells`
(default `state.wells_with_activations()`), sorted by `Well`, then `Row`.

**Time base.** The time base is milliseconds from the start of the record
with `Index` 1: row `r` spans `[(index[r] − 1) · record_ms, index[r] ·
record_ms)`. PyMCU's simulator truth uses the same base.

The columns:

- **The light period**: from `Row`, the run of consecutive rows with no
  `Index` gap where the well's `OnMs` > 0, cut before the well's next onset.
  `EndRow` is its last row, inclusive.
- **`LitMs`**: the well's `OnMs` summed over `[Row, EndRow]`.
- **`OnsetMs`**: the end of `Row` minus `OnMs[Row]`.
- **`EndMs`**: the start of `EndRow` plus `OnMs[EndRow]` when `EndRow >
  Row`, otherwise `OnsetMs + LitMs`.
- **`Timing`** is `exact` when the period spans more than one row, its
  interior rows are all `record_ms`, and no row in it exceeds `record_ms`.
  Otherwise it is `record`, and the times are good to one record.
- **`Overlap`** is true when the period's length cannot be the Activation's
  own:
  - a well in `linked[well]` has an onset in `[Row, EndRow]`;
  - the row before `Row` was lit with no gap between, so the LED was
    already on;
  - the light ran on into the well's next Activation: the next onset is the
    row after `EndRow`, and `OnMs[EndRow]` is the whole record. Under
    FixedInterval, with `LockoutMs` shorter than `ActivationMs`, held contact
    does this, so neither Activation's length can be read;
  - two of the well's onsets fall in `Row`.

  Overlapped rows keep their `LitMs`, and checks skip them.
- **`Boundary`** says why the period stopped other than by the rule: a
  Paradigm start or Program Interval change in `(Row, EndRow + 1]`
  (`interval`), an `Index` gap right after `EndRow` (`gap`), or the last
  row (`end`). It is empty otherwise.
- **`SinceLastOnsetMs`**: `OnsetMs` minus the same well's previous
  `OnsetMs` in the same state run, or `NaN`.
- **`Phase`**: `A` or `M` at `Row`.
- **`K`**: the 1-based number of the well's Phase-`M` Activations in its
  state run. It is `NA` in Phase `A`. Under a ratio Paradigm, the k-th Main
  Activation meets `requirement_for(k)`.
- **`Paradigm`, `ProgramInterval`, `Cycle`**: at `Row`.
- **`RequirementMet`**: `state.requirement_met(well, Row)`. Filling the
  first row of a new Paradigm from the program is the consumer's job.

**Acceptance.** On every simulator spec, for every unoverlapped Activation
with `Timing` `exact`, `OnsetMs`, `EndMs` and `LitMs` equal the truth's own
`lit_spans_ms` to the millisecond. `K` and `RequirementMet` equal the truth's
too. On PyMCU's simulator recording, they equal its `Activations.csv`
(`StartMs`, `LitMs`).

### C4. The light-events table

`qc/opto/opto_light_events.csv`'s generation-3 rows gain the ledger's
`OnsetMs`, `EndMs`, `LitMs`, `Timing`, `Overlap`, `Boundary`,
`SinceLastOnsetMs` and `K`, joined on (`Well`, onset row; two onsets in one
row are matched in order). They also gain `Family`, from C5's `family_of`
of the row's `Mode` and `Phase`. Rows from `OptoCol1`, on generations 1 and
2, have these columns `NA`. S1 adds `EndedBy` (contact, Hold, `MaxOnMs`,
length, Interval change, gap, or unknown), because it needs the program's
settings and pyflic's contact.

### C5. The registry (`pyflic/base/paradigm_families.py`)

```python
OPEN_LOOP, CLOSED_LOOP, FIXED_LENGTH, NON_FEEDING = "open loop", "closed loop", "fixed length", "non-feeding"
FAMILY_ORDER = (OPEN_LOOP, CLOSED_LOOP, FIXED_LENGTH, NON_FEEDING)
INTERVAL_BRANCH, RATIO_BRANCH = "interval", "ratio"

@dataclass(frozen=True)
class Family:
    key: str
    title: str                       # "Open loop", "Closed loop", ...
    modes: tuple[str, ...]           # opto_program mode strings
    qc_columns: tuple[str, ...]      # S1's columns in opto_light_qc.csv
    summary_columns: tuple[str, ...] # S2's columns in the light table
    headline: tuple[str, ...]        # decision 9
    figure: str | None               # S3's rule figure kind

FAMILIES: dict[str, Family]
def family_of(mode: str, *, acclimation: bool = False) -> str | None
def branch_of(mode: str) -> str | None
def families_in(program, dfm_ids=None) -> list[str]
def headline_metrics(families, *, max_on: bool = False, acclimation: bool = False) -> list[str]
def rule_sentence(paradigm) -> str
```

- **`family_of`** maps `op.OPEN_LOOP` to open loop; `op.CLOSED_LOOP` and
  `op.CLOSED_LOOP_MAX` to closed loop; `op.FIXED_INTERVAL`,
  `op.PROGRESSIVE_RATIO` and `op.FIXED_RATIO` to fixed length, or to closed
  loop when `acclimation` is true; and `op.NON_FEEDING` to non-feeding.
  `op.LIGHTS_OFF`, unknown and not-judged modes give `None`.
- **`families_in`** lists, in `FAMILY_ORDER`, the families of the
  program's Paradigms for those DFMs. It adds closed loop for any Paradigm
  with Acclimation > 0, and open loop for any interval with a well `On`.
- **`rule_sentence`** states the rule with its settings, for example "CL500
  (closed loop): lit during contact and for 500 ms after; at most 2000 ms
  per light period".
- **The column tuples** are declared in P0 from decisions 8 and 9 and from
  S1's column list. Streams fill in the values; they do not rename the
  columns.

### C6. Integrity (`pyflic/base/dfm.py`)

- **The integrity report gains `## DFM restarts`**: one line per
  `RestartSpan`, with the clock time, the minute, the records and seconds
  missing, and whether `Messages.csv` names it. A restart that only
  `Messages.csv` names is listed too, as "named in Messages.csv; the data
  show an `Index` gap only". The report dict gains `restarts`.
- **The No Ack note.** When the *No Ack* count is above 0 with no lost and
  no repeated records, the error section adds: "No Ack with nothing lost or
  repeated: PyMCU builds before 10/17/2026 sent a partial ACK the firmware
  took as missed. No data were lost."
- **The cross-check.** `Messages.csv`'s "Lost N records" counts are summed
  per DFM against the `Index` gaps, and a difference is noted.

### C7. *Firmware events disagree*, like with like (`opto_qc.py`)

pyflic's count leaves out feeding events whose first sample lies in a row of
the same well's own Activation period, `Row` to `EndRow` in the ledger.
Decision 16.

### C8. The PyMCU-simulator test

- **`tests/pymcu_sim_runner.py`**, the launcher: stand-in modules for
  `fcntl`, `busio`, `board`, `smbus*`, `adafruit_*`, `RPi`, `digitalio`,
  `serial`, `cobs`, `gpiozero`, `neopixel` and `microcontroller`, and
  `multiprocessing.get_context("fork")` mapped to `"spawn"`. It then runs
  PyMCU's `scripts/simulate_recording.py` with `runpy`, with the working
  directory at PyMCU. PyMCU's serial and I2C modules are imported but never
  used, so pyflic's own `.venv` runs it, in about 7 s.
- **`tests/test_pymcu_simulator.py`**, marked slow. It skips unless
  `PYMCU_DIR` (default: the sibling checkout) has the script. It runs
  `sys.executable -I tests/pymcu_sim_runner.py <PyMCU> --out <tmp> --seed 1`
  and builds a Custom optogenetic Project over the recording.
- **The comparison.** For the whole-recording rows of the triggering wells,
  `light_wells.csv`'s values are compared with the truth's `Summary.csv`:
  - Activations, AcclimationActivations, LastRequirementMet (the truth's
    `Breakpoint`) and ProgressAtEnd: equal;
  - AcclimationEndMin: within 0.2 s;
  - LitSec: within 0.01 s.

  After C3, the ledger is also compared with `Activations.csv`. After S4,
  the same recording loads as Progressive Ratio without `paired_chambers`.
- **Why the default seed.** The test pins the seed, so a PyMCU change that
  alters the truth shows as a failure to look at, not a flake.

### P0 acceptance

- Each contract item's acceptance above is met.
- The firmware cross-check passes.
- The generation-1 tests are unchanged.
- The full gate passes with only the eight pre-existing failures.

## Stream S1: rule checks

Files: `opto_qc.py`, `opto_light.py` (outside its report blocks), the Opto
editors for the constants, and `qc_viewer.py`'s `OptoTab._COLUMNS`.

**How every check judges.** A check judges the ledger rows of a Linkage
Group's Trigger Wells, per window, on generation 3. Two kinds of row are
**judgeable** for a length:
- the row is not `Overlap`;
- its `Boundary` is empty.

The others are counted as not judged. A check needs `Program.txt`, because
it reads the Paradigm's settings. Without one it does not run, and the
reason says so. `tol` is `opto_activation_tolerance_ms`. A timing with
`Timing` `record` widens `tol` by one record (200 ms).

| Check and column | Applies to | Counted when | Verdict |
|---|---|---|---|
| *short activations*, `ShortActivations` | Closed loop: ClosedLoop Main, and any Phase-`A` Activation | a judgeable Activation's `LitMs` < min(Hold, `MaxOnMs` if > 0) − `tol`. The Hold is `HoldMs`, or `ActivationMs` in Acclimation. Lit time is the contact plus the Hold, so never less | fails when the count is above `opto_activation_length_fail_fraction` of the judgeable ones |
| *max on exceeded*, `OverMaxOnActivations` | ClosedLoop with `MaxOnMs`; NonFeeding with `MaxOnMs` > 0 | a judgeable Activation's `LitMs` > `MaxOnMs` + `tol` | fails on any one |
| `CutOffs` | ClosedLoop with `MaxOnMs` | a judgeable Activation with abs(`LitMs` − `MaxOnMs`) ≤ `tol` | reported |
| *wrong activation length*, `WrongLengthActivations` | Fixed length, Phase `M` | a judgeable Activation with abs(`LitMs` − `ActivationMs`) > `tol` | fails above `opto_activation_length_fail_fraction` |
| *lockout broken*, `LockoutViolations` | FixedInterval, Phase `M` | `SinceLastOnsetMs` < max(`LockoutMs`, `ActivationMs`) − `tol`, between consecutive Main Activations of one state run. The firmware needs both the Activation ended and the lockout passed | fails above `opto_lockout_fail_fraction` |
| *contact without activation*, `MissedContacts` | FixedInterval, Phase `M` | a run of pyflic activity at the Trigger Well that begins while the well is free, with no Activation onset within the tolerance after the run starts. Free means its own Activation is over and max(`LockoutMs`, `ActivationMs`) has passed since its last onset | warns when the count is above `opto_missed_contact_warn_fraction` of the free runs, with at least 5 free runs |
| *requirement series wrong*, `SeriesMismatches` | Ratio, Phase `M` | `RequirementMet` ≠ `requirement_for(K)`, where both are known and the row is not a two-onset row | fails on any one |
| *non-feeding dark*, `NonFeedingDarkSec` | NonFeeding | time the well's `OnMs` is 0 although the firmware's rule says lit. The rule says lit with no pyflic activity at the Trigger Well for longer than `OnDelayMs` + `tol`, and, with `MaxOnMs` > 0, within the first `MaxOnMs` after that point | warns when the time is above `opto_non_feeding_dark_warn_fraction` of the expected-lit time |
| `RelightDelayMs` | NonFeeding | the median, over Activations that follow pyflic activity at the Trigger Well, of `OnsetMs` minus the end of the last activity sample before it | reported, against `OnDelayMs` |
| *open loop not lit*, `OpenLoopLitFraction` | Open loop | the column becomes the **lowest** lit fraction over the group's open-loop windows, so each Program Interval and each pass is judged | warns below `opto_open_loop_min_lit_fraction`, as now |
| *interval started late*, `IntervalLagSec` | every family | the worst lag of a Program Interval's first row (on every Cycle) behind its `Program.txt` time. Extend `_check_program_times`, which already compares times | warns above `opto_interval_lag_warn_sec`. The firmware's normal lag is one row |
| *DFM restarted*, `Restarts` | every family | the DFM's `ParadigmState.restarts()` | warns, on every group of that DFM, with the times |

- ***Non-feeding light during feeding*** keeps its rule and reads
  `opto_non_feeding_lit_warn_fraction` and `opto_non_feeding_min_sec`. Their
  defaults equal the values it borrowed, so its results do not change.
- **Non-feeding windows now expect light**, so *no light recorded* fires for
  a NonFeeding DFM that never lit.
- **`EndedBy`** in `opto_light_events.csv`, for each Activation:
  - `interval`, `gap` or `end` from `Boundary`;
  - `unknown` when `Overlap`;
  - closed loop: `MaxOnMs` when within `tol` of it, otherwise `Hold`;
  - fixed length: `length` when within `tol` of `ActivationMs`, otherwise
    `unknown`;
  - non-feeding: `MaxOnMs` when within `tol` of it, `contact` when pyflic
    activity at the Trigger Well begins within the tolerance of `EndMs`,
    otherwise `unknown`.
- **The constants** of decision 7 go into `OptoQCSettings`, the yaml keys,
  the Opto editors (rows like the existing ones) and `summary.txt`'s
  constants line.
- **Flag placement.** The new flags join `FAILING_FLAGS` or `WARNING_FLAGS`
  per decision 6.
- **Reasons.** Each reason names the setting, the measured value and, for a
  failing check, the likely cause from decision 5.
- **Not judged.** Activations that could not be judged are counted in the
  notes.

Acceptance:
- **Each flag fires on its injected fault** from C1:
  - `program_paradigms` with a different `ActivationMs`, `LockoutMs`, Step
    or `MaxOnMs`;
  - `on_ms_faults` shortening or blanking light;
  - a restart.

  The reason names the setting and the value.
- **No new flag fires on clean data**:
  - any clean spec (`family_specs`, `one_of_each`, `choice` apart from its
    designed faults, `yoked_controls`, `stress`, `fixed_ratio`,
    `repeating_open_loop`);
  - the PyMCU-simulator recording;
  - the quiet bench run.
- **Generations 1 and 2** have the new columns `NA`, and their outputs are
  unchanged.

## Stream S2: summary columns and headline metrics

Files: `light_summary.py`, `pubfigures.py` (`LIGHT_METRICS`), and
`analytics.light_phase_summary`, which becomes the source of the light and
dark rates.

**Columns.** Per well and window, from the ledger, `NA` outside the family.
"Judgeable" is as in S1, and `tol` is `opto_activation_tolerance_ms` from the
member's opto settings.

| Column | Family | Definition |
|---|---|---|
| `MedianActivationSec` | Closed loop | the median `LitMs` / 1000 of the judgeable closed-loop Activations (ClosedLoop Main, or Phase `A`) |
| `CutOffs` | ClosedLoop with `MaxOnMs` | judgeable Activations with abs(`LitMs` − `MaxOnMs`) ≤ `tol` |
| `MainActivations` | any Paradigm with Acclimation > 0 | the Phase-`M` Activations |
| `MaxActivations` | FixedInterval | the window's Main time, divided by max(`LockoutMs`, `ActivationMs`), floored |
| `RewardEfficiency` | FixedInterval | `MainActivations`, or `Activations` without Acclimation, divided by `MaxActivations` |
| `MedianReturnSec` | FixedInterval | the median of `SinceLastOnsetMs` − max(`LockoutMs`, `ActivationMs`), over consecutive Main Activations, in seconds: how soon the fly came back once it could earn light |
| `LockedOutContactSec` | FixedInterval (redefined, decision 10) | pyflic lick samples at the well in Main rows where its lockout is running and its own Activation is not lit, divided by samples per second |
| `Suppressions` | NonFeeding (redefined, decision 10) | judgeable NonFeeding Activations not ended by `MaxOnMs`. Contact is the only other way the light goes out |
| `MedianSuppressionSec` | NonFeeding | the median of the next Activation's `OnsetMs` minus a suppression's `EndMs`, within one state run, in seconds |
| `LicksPerMinLit`, `LicksPerMinDark` | Open loop (the chamber's Role is Open, or its window's mode is open loop) | the chamber's licks while its own `OnMs` > 0, and while it is 0, per minute of each |
| `LightFeedingIndex` | Open loop | (lit − dark) / (lit + dark) of those two rates; `NA` when either phase is absent or both rates are 0 |

- The chamber table sums counts and takes medians over its wells, as it does
  today.
- `HEADLINE_METRICS` stays as a name, for compatibility. Callers move to
  `paradigm_families.headline_metrics(...)` with the member's families
  (decision 9).
- `pubfigures.LIGHT_METRICS` offers every new column, with its label and
  unit.

Acceptance:
- **Truth.** Each column equals a computation from the simulator's truth on
  its `family_specs` entry. The licks columns are compared with
  `light_phase_summary`.
- **Off-family.** Every column is `NA` off its family, and on generations 1
  and 2.
- **PyMCU.** On the PyMCU-simulator recording, `MainActivations` equals the
  truth's `MainActivations`.
- **Stacks.** The Project stacks carry every column.

## Stream S3: reports, figures and views

Files: `opto_light.report_qc_blocks` and `report_glance_blocks`,
`pdf_report.py`, `project_report.py`, `report_content.py`,
`program_timeline.py`, a new `pyflic/base/rule_figures.py`, and the QC
Viewer's Program tab.

**Quality control, optogenetic light** (member report). On generation 3,
after today's group table, the section gains one subsection per Paradigm in
the member's program, in `FAMILY_ORDER`, then by Paradigm name. Each has:

- **The heading**: the Paradigm's name, family and DFMs.
- **`rule_sentence(paradigm)`**.
- **A table of the family's `qc_columns`** per Linkage Group running it,
  with DFM, Group, Treatment, the judgeable and not-judged counts, and the
  verdict.
- **The rule figure**, from `rule_figures.py`, one panel per DFM:

  | Family | Figure |
  |---|---|
  | Closed loop (`activation_length`) | a histogram of judgeable `LitMs`, with dashed lines at the Hold and at `MaxOnMs` |
  | Fixed length, Interval (`onset_spacing`) | a histogram of `SinceLastOnsetMs`, with a dashed line at max(`LockoutMs`, `ActivationMs`); a small histogram of `LitMs` beside it, with a line at `ActivationMs` |
  | Fixed length, Ratio (`requirement_series`) | `RequirementMet` against `K`, points per Trigger Well over the line of `requirement_for(k)`; points that differ are drawn in the failure colour |
  | Non-feeding (`relight_delay`) | a histogram of each Activation's relight delay (the per-Activation value S1 takes the median of), with a dashed line at `OnDelayMs` |
  | Open loop | none: the Program timeline shows the schedule |

The rules for this section:
- **Wording.** The paragraph that today speaks of "decay" says, on
  generation 3, that each rule is checked below. Generations 1 and 2 keep
  it.
- **Empty families.** A family with no judgeable Activation gets a
  `NothingToDraw` grey note, not a figure.
- **The glance callout** counts the new failing and warning flags, as it
  counts today's.

**Results, Light behaviour** (member and Project reports). There is one
subsection per family present, titled by family. Each has dot plots and
the statistics of `headline_metrics(...)` for that family, computed on the
rows S5 assigns (Activation-based metrics on chambers that earn light). Open
loop adds a figure, *Feeding in light and dark*. It draws each chamber's
`LicksPerMinLit` and `LicksPerMinDark` as two points joined by a line, by
treatment, then `LightFeedingIndex` as a dot plot with its comparison
between treatments. With one treatment, the one-treatment note applies, as
elsewhere.

**Paired and yoked** (Results). S5's table and figure go in their own
subsection when any group has the Paired and Yoked Roles.

**The Program timeline**:
- per-well `On` and `Off` shading in the well lanes, from `Program.txt`;
- a marked band for each `RestartSpan`, labelled "restart";
- the same in the QC Viewer's Program tab.

The QC Viewer's Program tab also gains an *Activations* table for the
selected DFM. It lists the ledger rows from `opto_light_events.csv`:
`Well`, `OnsetMin`, `Family`, `Phase`, `K`, `LitMs`, `EndedBy`,
`RequirementMet` and `Overlap`.

Acceptance:
- **No error box.** The member and Project reports build with no red box
  and no "could not be drawn":
  - every `family_specs` entry;
  - `one_of_each`, `stress`, `choice` and `yoked_controls`;
  - the PyMCU-simulator recording;
  - the quiet bench run.
- **Subsections.** Each family's subsections appear exactly when its family
  is in the program.
- **Figures.** Each rule figure draws on its spec, and on an injected fault
  shows the failing points.
- **Generations 1 and 2.** Their reports are unchanged, apart from the
  glance callout's count.

## Stream S4: Progressive Ratio

Files: `progressive_ratio_experiment.py`, `pr_light_qc.py`,
`experiment_types/progressive_ratio.py`, and `yaml_lint.py` for the config
rule.

**Solo Chamber Groups** (decision 13). Today the Chamber Groups are fixed
pairs (`CHAMBER_GROUPS`, chambers 1–2, 3–4, 5–6), each needing a paired and a
yoked chamber. They become per-DFM groups:

- **With `Program.txt`**:
  - a Linkage Group lighting two chambers is a pair: the chamber holding
    the trigger well is Paired, the other Yoked;
  - a Linkage Group lighting one chamber is a solo group, its chamber
    Paired.
- **Without `Program.txt`**, the config's `chamber_groups: paired` (the
  default, as today) or `single`.
- **Numbering.** Groups are numbered in chamber order, so solo groups 1–6
  are the six chambers.
- **Group outputs.** The group columns keep their names. `YokedChamber` is
  `NA` for a solo group.
- **Skipped for solo groups**: the paired-minus-yoked comparison, the
  cumulative difference figure, and the yoked checks of the PR light QC.
  The report says, once, that the design has no yoked controls.
- **Lint.** `pyflic lint` accepts a solo design without `paired_chambers`,
  and still asks for it where a pair cannot be resolved.
- **Exclusion.** A solo group whose chamber is excluded drops. A pair still
  needs both chambers.

**Also:**

- **Wording** (decision 14): the "estimated requirement increment"
  paragraph, its line on the licks-per-light-event figure, and the
  "a working progressive ratio climbs" caption appear only when the
  group's test Paradigm is ProgressiveRatio.
- ***Requirement series wrong*** in the PR light QC, using S1's check
  function, which S4 imports from `opto_qc`. S4 adds the call only.
- **Restart censoring** (decision 15). When a `RestartSpan` falls in a
  group's Test window, the breaking-point rule sees the Test window only up
  to the restart, `Censored` is true, and `Notes` names the restart.

Acceptance:
- **PyMCU.** The PyMCU-simulator recording loads as Progressive Ratio
  without `paired_chambers`, as twelve solo groups. For each, the Test light
  events equal the truth's Main Activations (`Activations.csv`) in count,
  time and Requirement met. `BreakRequirement` is the Requirement of the
  last counted Test light event. Where `Censored` is true, it equals the
  truth's `Breakpoint`.
- **Fixed ratio.** A fixed-ratio report has none of the progressive-only
  text.
- **Restart.** The `restart` spec's FixedRatio group is censored at its
  restart.
- **Unchanged.** Every existing Progressive Ratio test passes unchanged. The
  paired-and-yoked designs are untouched.

## Stream S5: the yoked comparison for every type

Files: `light_summary.behaviour_rows`, a new `yoked_comparison` in
`analytics.py`, `experiment.py`'s basic-analysis write step for its CSV, and
the report blocks it hands S3, as functions S3 places.

- **Which groups.** A **yoked group** is a Linkage Group whose chambers have
  Roles Paired (exactly one) and Yoked (one or more), under any Experiment
  Type other than Progressive Ratio, which keeps its own.
- **`yoked_comparison(experiment, metrics=None)`** returns one row per
  yoked group and window: DFM, Group, PairedChamber, YokedChambers,
  Treatment (the paired chamber's), and, for each metric, the paired value,
  the mean of the yoked values and their difference.
  - The metrics default to the report's (Licks, Events, MedDuration), from
    the feeding summary. On two-well layouts they are taken per well (A and
    B), as the feeding summary names them.
  - The tests are Progressive Ratio's: a one-sample t-test of the
    differences against 0 by treatment, with the Wilcoxon signed-rank test
    beside it. Reuse its function; do not copy it.
- **The CSV** is written to `analysis/yoked_comparison.csv` in basic
  analysis. A Project stacks it as `<project>_YokedComparison.csv`.
- **Light behaviour by Role** (decision 12). `behaviour_rows` gives
  Activation-based metrics only the chambers whose Role earns light (Paired,
  Self, Mutual): Activations, the Acclimation columns, FirmwareEvents, the
  ratio columns, `MedianActivationSec`, `CutOffs`, `RewardEfficiency`,
  `MedianReturnSec` and `Suppressions`. LitSec and LitFraction keep every
  chamber, with Role as a column, so a yoked chamber's light is seen beside
  its partner's. The function fixes today's filter, which recognises only
  Progressive Ratio's lower-case role words.
- **The report blocks**: a table of the differences by treatment, and one
  figure, the paired against the yoked value per group, with the identity
  line. S3 places them.

Acceptance:
- **Hand computation.** On `yoked_controls_spec` under Custom,
  `yoked_comparison` equals a hand computation from the feeding summary.
- **Role filter.** The yoked chambers are absent from the Activation
  statistics and present in LitSec's.
- **Progressive Ratio.** Its outputs are unchanged.
- **Without yoking.** A design with no yoked group writes no CSV, and has no
  subsection.

## Stream S6: help, guides and records

- `docs/qc-user-guide.md`: a section per family, with each check, what it
  means and what to do about it;
- `pyflic/help/content/concepts-optogenetics.md`: the families, the
  new columns and the constants;
- `docs/v4-data-columns.md`: "Where you see it";
- the CHANGELOG;
- the CONTEXT.md term *Paradigm Family*;
- ADR-0017 (decision 1), and an addendum to ADR-0015 for the new severities;
- a "Which Experiment Type?" table for users: Custom for OpenLoop,
  ClosedLoop, FixedInterval and NonFeeding programs (Hedonic for a two-well
  hedonic design under any of them); ProgressiveRatio for ratio programs.

---

## Delivery

```
P0-sim (C1 simulator, C2 restarts, C6 integrity)     P0-ext (C8 PyMCU test)
                 └──────────────────┬───────────────────────┘
                                    ▼
                 P0-ledger (C3 ledger, C4 events, C5 registry, C7)
          ┌─────────────────────────┼───────────────────────┐
          ▼                         ▼                       ▼
     S1 rule checks          S2 summary columns       S4 Progressive Ratio
          │                         │
          │                         ▼
          │                  S5 yoked comparison
          └────────────┬────────────┘
                       ▼
             S3 reports, figures, views
                       ▼
                   S6 docs
```

- **Branches**: `pa-p0-sim` and `pa-p0-ext` in parallel from the plan's
  commit, then `pa-p0-ledger` from their merge. Then `pa-s1-checks`,
  `pa-s2-summaries` and `pa-s4-pr` in parallel from P0's tip, each in its own
  worktree. Then `pa-s5-yoked` from S2's merge, and `pa-s3-reports` after
  S1, S2 and S5 are merged. S6 works on `v4_Dev` last.
- **Worktree base**: the agent tool's worktrees start from `main`. Each
  prompt names its base commit (`git switch -c <branch> <commit>`) and runs
  the main `.venv`'s Python from the worktree root.
- **Merges**: one branch at a time, with the gate after each.
- **Gate**: `python -m pytest tests -q -p no:cacheprovider`, with no failure
  beyond the eight pre-existing ones listed in
  [v4-data-plan.md](v4-data-plan.md#delivery). Also:
  - the firmware cross-check and the PyMCU-simulator test pass, or skip
    with a reason;
  - the generation-1 tests are unchanged;
  - `pyflic lint` is clean on the fixtures.
- **Shared surfaces**:
  - `opto_qc.py`: S1 owns it; S4 calls into it.
  - `light_summary.py`: S2 owns it; S5 adds `behaviour_rows` only.
  - `pdf_report.py`, `project_report.py`, `rule_figures.py`: S3 only.
  - `experiment.py`: S5 adds the yoked-comparison write step only.
  - `qc_viewer.py`: S1 owns the Opto tab, and S3 the Program tab.
  - `paradigm_families.py`: P0-ledger creates it with every family's
    columns declared; a stream changes only its own family fields.
  - `tests/v4_fixtures.py`: P0-sim owns it; later streams add specs only.
- **Each stream's report** names:
  - the files changed;
  - the acceptance criteria met, with test names;
  - any decision found unworkable;
  - the calibration evidence for each constant default.

## As built

Where the build departed from the plan, stream by stream.

**P0-ext** (79a5d0f):
- **AcclimationEndMin is aligned, not exact.** The PyMCU test converts the
  truth's origin (the start of record 1) onto pyflic's `Minutes` (the first
  row's stamp, 0.57 s later on seed 1) before comparing. The measure then
  agrees to within one record. The plan's "where pyflic stands" had called
  it exact, from a check with a quarter-minute tolerance.

**P0-sim** (4d44efd):
- **The lead-in's `Paradigm` is `NA`**, as PyMCU writes it. Four tests that
  pinned `Idle` changed.
- **The restart checks run on generation 3 only.** C6's restart section,
  the No Ack note and the lost-records cross-check do not run on
  generations 1 and 2.
- **No Ack note.** "Lost" includes a restart's gap, so a recording with a
  restart never gets the No Ack note.
- **Restarts sit on the record grid.** A restart must come more than 54
  records into the DFM's count, or PyMCU would read it as a resend.

**P0-ledger** (d28ae8f):
- **C7 keeps the onset row.** pyflic's count leaves out feeding events
  that start in `Row + 1` to `EndRow` of the well's own Activation, not
  `Row` to `EndRow`. The Event that meets the Requirement starts in the
  onset row, in the millisecond the light comes on, and the firmware counts
  it. Dropping it took one event per Activation, and made healthy
  FixedRatio chambers warn.
- **`Overlap` gains a case**: a break in `Index` right before `Row`, since
  the Activation may have started in the lost records.
- **Leaving Acclimation.** On the row where a well leaves Acclimation under
  a ratio Paradigm, its Activations are Acclimation ones unless the
  Requirement advanced there, as `requirement_met` reads that row.
- **The registry.** The every-family QC columns are in
  `COMMON_QC_COLUMNS`. Fixed length's figure is given per branch
  (`BRANCH_FIGURE`, `rule_figure`). `rule_sentence` leaves out frequency and
  pulse width.

**S2** (92db0de):
- **Tolerance.** `activation_tolerance_ms(exp)` read
  `opto_activation_tolerance_ms` from the design's constants until S1's
  setting was merged.
- **Record timing.** Where `Timing` is `record`, `tol` is one record wider,
  for CutOffs and for "ended by `MaxOnMs`" in Suppressions. This is S1's
  rule.
- **Locked-out contact.** "Own Activation not lit", in
  LockedOutContactSec, means `ActivationMs` from the onset, because the
  ledger's own periods run on through a partner's light.
- **Open loop** means the chamber's Role is Open, or its window runs open
  loop with no fly-driven rule. The rates use the whole window, as
  `light_phase_summary` does.
- **A program is required.** Every new column needs generation 3 and a
  program, as the older type columns do.
- **Light and dark** counting is shared by `light_phase_summary` and the
  light table, through `analytics.chamber_light_phases`.
- **Decision 10 on the `non_feeding` spec**: Suppressions fell from 419 to
  312, because `MaxOnMs` ends no longer count.

**S4** (9bb928f):
- **Group resolution.** What the config states wins: `paired_chambers`,
  then `chamber_groups: single`, then the Linkage. A Linkage of
  non-adjacent pairs is now read as those pairs, where the old fixed
  reading paired neighbours.
- **`chamber_groups` is a per-DFM key only.**
- **Restart censoring** applies the first-gap rule to the window that
  ends before the restart. The note goes in `pr_light_qc.csv`'s `Notes`,
  `summary.txt` and the report. `pr_breaking_point.csv` gains no column.
- **The type's report introduction** is worded for both pairs and solo
  groups.
- **The config editor's Progressive Ratio card** gains a Groups choice:
  Pairs, Single chambers, or From Program.txt.

**S1** (9c5025b):
- **Checks judge per Paradigm.** Windows that ran the same Paradigm are
  pooled within a group, and the fraction verdicts are judged on each
  Paradigm's total. *Open loop not lit* stays per window.
- ***Non-feeding dark*** starts the expected-lit time one record later,
  because pyflic often misses a bout's last partial record. It judges only
  once 10 s are expected lit (`MIN_EXPECTED_LIT_SEC`).
- ***Interval started late*** discounts the first Interval's lead-in
  (`LEAD_IN_SEC`, 5 s). PyMCU sends no instruction until its baseline is
  taken, which measured 4.8 to 5.2 s. The schedule follows PyMCU's
  `GetPosition`; Circadian programs follow the time of day.
- **Pairing rules.**
  - Lockout pairs need both onsets unoverlapped.
  - *Contact without activation* counts the well free from any earlier
    onset, and accepts an onset in the run's first row or the next.
  - Activity is a lick or a tasting sample.
- **The series off-by-one runs are resolved, not skipped.** A run that
  matches the series with K one less passes, with a note.
- **`EndedBy` `contact`** means pyflic activity within the tolerance and a
  record of `EndMs`.
- **`RelightDelayMs`** reads up to a record above `OnDelayMs`, because it
  is measured to the end of the last activity sample.
- **The editors needed no change.** They build their rows from
  `OPTO_CONSTANT_FIELDS`.
- **Calibration.** No default changed. The largest clean values were 0
  for the length, lockout, missed-contact and series checks, 2.1% for
  *non-feeding dark* against 10%, and 0.2 s for the interval lag against
  5 s.

**S5** (77909f8):
- **The test function was already public.** The test against zero is
  `analytics.zero_tests`, used as it is: nothing was moved or copied.
- **One treatment** gets the one-treatment note in place of the
  comparison between treatments. The table of differences, each tested
  against zero, still shows, as in the Project report.
- **The CSV is written inside the "Light tables" step** of basic analysis.
  The Project stacks it through `LIGHT_TABLES`.
- **AcclimationActivations and AcclimationEndMin** now follow the ledger's
  Phase. In one edge, an Acclimation of 1 starts and ends inside a state
  run's first row, and the program corrects the ledger there
  (`_unseen_acclimation`). On `stress_spec` this moved 8 wells. Activations
  now equal AcclimationActivations plus MainActivations everywhere.
- **A known gap on `stress_spec` DFM 3.** Its Circadian program starts
  partway through its day, and the export lists only the first Interval.
  The FixedInterval Interval that runs at minutes 2 to 4 is omitted, so its
  thresholds are unknown, and wells 9 and 10 get no Acclimation columns.
  The simulator reproduces PyMCU's export exactly, so a real recording of
  such a program would be the same.

**S3** (14a8050):
- **Acclimation gets its own subsection.** A Paradigm with Acclimation has
  two rule subsections: its Acclimation, under closed loop, and its Main,
  under its own family. Wells set `On` get an open-loop subsection.
  Subsections then appear exactly when their family is in the program.
- **Fixed-length figures show the length.** They have a second plot: lit
  time, dashed at `ActivationMs`. NonFeeding has one when `MaxOnMs` is set.
  Without them, *wrong activation length* and *max on exceeded* could not
  be seen. The relight-delay histogram has no red, because S1 makes no
  verdict on single Activations.
- **Per-Paradigm values are recomputed with S1's functions**, some of them
  private, because `opto_light_qc.csv` sums a group over its Paradigms. A
  test pins the per-group sums to the QC table. Making those helpers public
  is left as a follow-up.
- **Headings are level 2**, since `report_layout` has two levels.
- **The open-loop subsection's lowest lit fraction** reads
  `opto_light_intervals.csv` (whole windows). S1 trims each window's start,
  so the two can differ by a row or two.
- **Light behaviour rows by family**: by `ParadigmType`; mixed rows by
  their DFM's program; Open-Role rows in open loop only; Acclimation as its
  own subsection.
- **Generation 3 only.** On and Off shading and restart bands show on
  generation 3 only.
- **A failure stays contained.** If a rule subsection or the yoked
  comparison fails, it becomes one red box rather than costing the report.
- **Found and fixed: the Progressive Ratio Project report's two red
  boxes.** `project_report._pooled_figure` fed the breaking-point scatter
  figures rows from `faceted_data`, not `breaking_point_data`.

**The open-loop rates** (b60400f): the light and dark rates counted the
baseline lead-in as dark. So a chamber lit for the whole program had a
dark rate of 0 and an index of 1. Only rows under a Program Interval count
now, and a phase shorter than `MIN_LIGHT_PHASE_MIN` (1 minute) has no rate.

**Joining the streams** (144ddb2): the Progressive Ratio light QC calls
`rule_checks.requirement_series_mismatches`. The light table reads the
tolerance through `OptoQCSettings`.

**S6** (help, guides and records):
- **The terms and ADRs were already written.** *Paradigm Family* entered
  `CONTEXT.md`, and ADR-0017 and ADR-0015's addendum were written, when the
  plan was accepted (41800e4). S6 updated `CONTEXT.md`'s Progressive Ratio
  entries for solo groups, which the plan's S6 list did not name.
- **The QC guide's rule checks are a section of their own**, section 7 of
  `docs/qc-user-guide.md`, one subsection per family. Progressive Ratio,
  Projects, the checklist and troubleshooting moved to sections 8 to 11.
- **"Which Experiment Type?"** is a table in `docs/GETTING_STARTED.md`; the
  help topic *Experiment types* says the same in its table of shipped types.
- **New help anchors**: `concepts-optogenetics#paradigm-families`,
  `#each-paradigms-own-rule` and `#paired-and-yoked-designs`,
  `plots-catalog#rule-figures` and
  `concepts-progressive-ratio#without-yoked-controls`.
- **Decision 3 was half built** when S6 documented it: generations 1 and
  2 kept their checks, but their report did not name the rule checks that
  did not run. The coordinator then added that sentence to the light QC
  section, for every generation-1 or -2 DFM (see "After the streams").
- **No README row**: no new guide was added.

**After the streams** (the coordinator, on the merged tip):
- **Decision 3 completed.** The light QC section names, for each
  generation-1 or -2 DFM, the firmware 4.0.0 rule checks that did not run,
  and why: older firmware records only which LEDs were lit at each record,
  which cannot time a light period.
- **A restart raises one warning.** Its rows under no instruction, before
  PyMCU resent it, no longer count toward *unknown-instruction rows*, as
  its gap no longer counts toward *lost records*: *DFM restarted* reports
  both.
- **No dead LED.** The new checks no longer give "a dead LED" as a cause.
  `OnMs` and `OptoCol1` are the firmware's record of driving the LED, and
  nothing senses light, so a lamp that fails in the lid does not show in
  the data. *Non-feeding dark* is a drifting signal read as contact, or a
  longer `OnDelayMs` than `Program.txt` states.
- **Progressive Ratio wording** says that a group leaves with its yoked
  chamber "when it has one". It names *requirement series wrong* among the
  light QC failures, and the missing-groups error names all three ways to
  set groups.
- **The README's Experiment Types table** listed chamber layouts as types,
  as they were before ADR-0007; it now lists Custom, Hedonic and
  ProgressiveRatio.

**Coordination:**
- **The checks live in a module of their own**, `rule_checks.py`, so that
  S4 can import the series check.
- **S4 leaves the *requirement series wrong* call** in the Progressive
  Ratio light QC to the merge after S1.

## Not in this plan

- Fine mode (firmware 4.1.0, per-scan data). The ledger is keyed by `Index`,
  so a fine table can join it later.
- The Environmental Monitor's columns.
- Phase Facets outside Progressive Ratio (decision 19).
- New Experiment Types (decision 1).
- Lick microstructure under light: bout structure within an Activation
  against outside it.
- Analyses of their own for Circadian programs, or for Mutual groups,
  beyond Roles.
- **On the bench, to calibrate the constants**:
  - a recording of each type;
  - PyMCU's FixedRatio recording of 10/17/2026;
  - a DFM that restarts mid-recording.
