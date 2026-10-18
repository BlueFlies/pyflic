# Paradigm analyses plan: a light QC and a summary for each Paradigm type

The plan for giving each Paradigm type of the firmware 4.0.0 program language
its own light QC, its own summary columns and its own report content, under
every Experiment Type. It follows [v4-data-plan.md](v4-data-plan.md), which
made pyflic read the new data, and begins with a check of pyflic against the
firmware and PyMCU as they stood on 10/17/2026.

**Status (2026-10-17): proposed.** The decisions below are recommendations,
not yet accepted. The fixes listed under [Where pyflic stands](#where-pyflic-stands)
as *fixed* are done on `v4_Dev`; everything else is to build.

Terms are [../CONTEXT.md](../CONTEXT.md)'s: *Paradigm*, *Program Interval*,
*Activation*, *Hold*, *Requirement* / *Progress*, *Firmware Event*, *Phase* /
*Acclimation*, *Role*, *Linkage Group*, *Trigger Well*. One new term is
proposed, *Paradigm Family* (decision 2), to be added to the glossary on
acceptance. The firmware's rules are DFMV3_V2's `src/LEDControl.c`, which is
the authority; PyMCU's `docs/ProgramFormat.md` states them in words.

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
| **PyMCU's own simulator** (`scripts/simulate_recording.py`): simulated flies, run through PyMCU's real record parser and file writer, with a truth folder. | An independent end-to-end check. | **Run**, on two DFMs over two hours of Progressive Ratio. pyflic's light table matched the truth exactly for all twelve triggering wells. The six measures were Activations, Acclimation Activations, Acclimation end, last Requirement met, Progress at end and lit time. The Progressive Ratio type could not load the design, which has no yoked controls (decision 13). |
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
| Non-feeding | *non-feeding light during feeding*, on borrowed constants; a dead LED goes unflagged | its own constants; *non-feeding dark*; *max on exceeded*; the relight delay reported | UnlitSec; Suppressions, counted per record, which also counts `MaxOnMs` ends | Suppressions from the light periods themselves; MedianSuppressionSec |

The settings `MaxOnMs`, `LockoutMs`, `OnDelayMs`, `EventGapMs` and the series
are parsed today but used by no check. Of the light-table measures, only
Activations, LitSec, FirmwareEvents and AcclimationEndMin reach a report.

---

## Decisions

Recommended, not yet accepted. Once accepted, the streams implement them, and
a stream that finds one unworkable stops and reports rather than deciding
otherwise.

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
   the rows.
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

One agent, on `v4_Dev`, before the others start.

**P0a. The simulator** (`tests/v4_fixtures.py`):
- `DFMSpec.restarts`: a list of `(at_s, down_s)`. The simulator drops the
  records of the outage and offsets `Index`, as PyMCU does. It writes `NA`
  Interval rows (Phase `M`, `OnMs` 0, Activations carried) until the
  instruction is resent, then restarts every well's state. It writes PyMCU's
  two restart errors to `Messages.csv`.
- Fault injection: `write_v4_recording(..., program_override=...)` writes a
  `Program.txt` whose settings differ from what ran; `led_faults` blanks a
  well's `OnMs` (dead) or fills it (stuck) over a span; `drop_activations`
  removes rises.
- One spec per family edge case:
  - ClosedLoop with `MaxOnMs` and bouts longer than it;
  - FixedInterval with `LockoutMs` both below and above `ActivationMs`;
  - NonFeeding with `MaxOnMs`;
  - Exponential ProgressiveRatio;
  - FixedRatio with Acclimation;
  - a yoked ClosedLoop design;
  - a Repeating OpenLoop schedule.

  `stress_spec` joins the QC and light-table tests, which do not use it
  today.

**P0b. `ParadigmState`** (`pyflic/base/paradigm_state.py`): `restarts()`
returns the row indices. Paradigm-state runs split there, and
`acclimation_runs`, `requirement_met`, the K numbering and `training_end`
honour the split.

**P0c. The ledger and the family registry.** The events-table columns of
decision 4 come from `opto_light.events_table` and `opto_qc`. A new
`pyflic/base/paradigm_families.py` holds, for each family:
- `FAMILY_OF[type]`;
- the checks, as functions over the ledger and the state;
- the summary columns;
- the headline metrics;
- the QC table's columns;
- the rule figure.

Streams S1 to S3 read the registry, so a family is added in one place.

**P0d. Integrity** (`dfm.py`):
- the restart lines;
- the No Ack note: with no lost or repeated records, the report explains
  that PyMCU builds before 10/17/2026 caused it and nothing was lost;
- a cross-check of `Messages.csv`'s lost-record counts against the `Index`
  gaps.

**P0e.** Decision 16.

**P0f.** Decision 17's PyMCU-simulator test, `tests/test_pymcu_simulator.py`
(marked slow), with the launcher as `tests/pymcu_sim_runner.py`.

Acceptance:
- the restart spec loads, and its state runs split;
- the ledger columns are exact on the simulator's truth for every spec;
- the PyMCU-simulator test passes, or skips with a reason;
- the firmware cross-check still passes;
- the existing generation-1 tests are unchanged.

## Stream S1: rule checks

Files: `opto_qc.py`, `opto_light.py`, and the Opto editors for the
constants.

- **The new flags** of decisions 6, 15 and 18, with the constants of
  decision 7. Each check is a function in the family registry, applied per
  Linkage Group and window, on generation 3.
- **New columns in `opto_light_qc.csv`**: ShortActivations,
  OverMaxOnActivations, CutOffs, WrongLengthActivations,
  LockoutViolations, MissedContacts, SeriesMismatches, NonFeedingDarkSec,
  RelightDelayMs, and IntervalLagSec (the worst).
- **The QC Viewer's Opto tab** lists them (`OptoTab._COLUMNS`).
- **Open loop**: the lit fraction is judged per Program Interval.
- **Non-feeding** gets its own constants and *non-feeding dark*. Its windows
  now expect light, so *no light recorded* can fire for a dead LED.

Acceptance:
- every flag fires on its injected fault, and the reason names the setting
  and the measured value;
- no new flag fires on any clean spec, on the PyMCU-simulator recording or
  on the quiet bench run;
- generations 1 and 2 have the new columns `NA`, with the reason in
  `summary.txt`.

## Stream S2: summary columns and headline metrics

Files: `light_summary.py`, `pubfigures.py` (`LIGHT_METRICS`), and
`analytics.light_phase_summary`, which becomes the source of the light and
dark rates.

- the columns of decision 8, and the redefinitions of decision 10;
- `HEADLINE_METRICS` becomes a function of the families present, per
  decision 9;
- the Project stacks keep every column.

Acceptance:
- each column is exact on the simulator's truth for its spec;
- every column is `NA` off-family;
- the PyMCU-simulator recording's values match its truth where the truth
  has them.

## Stream S3: reports, figures and views

Files: `opto_light.report_qc_blocks`, `pdf_report`, `project_report`,
`report_content`, `program_timeline`, and the QC Viewer's Program tab.

- **Quality control**: after the group table, one subsection per Paradigm in
  the program, ordered by family. Each has:
  - the rule in one sentence with its settings, for example "CL500 (closed
    loop): lit during contact and for 500 ms after; at most 2500 ms per
    light period";
  - the family's check table per Linkage Group, with the verdict;
  - its rule figure:
    - Closed loop: a histogram of lit time per Activation, with lines at the
      Hold and `MaxOnMs`;
    - Fixed length, Interval: a histogram of onset-to-onset spacing, with a
      line at the lockout, and the length histogram;
    - Fixed length, Ratio: Requirement met against K for each Trigger Well,
      over the program's series;
    - Non-feeding: a histogram of the relight delay, with a line at
      `OnDelayMs`;
    - Open loop: the Program timeline already shows the schedule, so it has
      no figure of its own.

  On generation 3, the generic paragraph's "decay" wording gives way to these
  per-rule sentences.
- **Results, Light behaviour**: one subsection per family with its headline
  set (decision 9). Open loop adds *Feeding in light and dark*: each
  chamber's lit and dark rates, joined, by treatment, and the
  LightFeedingIndex compared between treatments. The Project report does the
  same, pooled.
- **The Program timeline** shades per-well `On` and `Off`, and marks
  restarts. The Requirement and Progress stay in the QC Viewer's well table.
- **The rule for empty content** (`NothingToDraw`) carries over: a family
  with no Activation gets a grey note, not a figure.

Acceptance:
- the reports of `one_of_each`, `stress`, `choice`, `yoked_controls` and the
  quiet bench run build with no red box and no "could not be drawn";
- each family's subsection appears exactly when its family is in the
  program.

## Stream S4: Progressive Ratio

Files: `progressive_ratio_experiment.py`, `experiment_types/progressive_ratio.py`
and `pr_light_qc.py`.

- solo Chamber Groups (decision 13): `CHAMBER_GROUPS` gives way to groups
  from the Linkage; the config value; the lint rule;
- the Fixed Ratio wording (decision 14);
- *requirement series wrong* in the PR light QC, reusing S1's check;
- restart censoring (decision 15).

Acceptance:
- the PyMCU-simulator recording loads as Progressive Ratio without
  `paired_chambers`, and every breaking point and `BreakRequirement` matches
  the truth;
- a fixed-ratio report has no progressive-only text;
- the restart spec's group is censored at the restart.

## Stream S5: the yoked comparison for every type

Files: `light_summary.behaviour_rows` and a new `yoked_comparison` in
`analytics.py`; the report blocks reach S3 through the registry.

- decision 12: the table of paired minus yoked differences by treatment, and
  Light behaviour statistics by Role;
- Progressive Ratio's paired-yoked code is reused, not copied.

Acceptance:
- on `yoked_controls_spec` under Custom, the difference table equals a hand
  computation, and the yoked chambers are absent from Activation statistics.

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
P0 (one agent, sequential, on v4_Dev)
  P0a simulator ──► P0b restarts in ParadigmState ──► P0c ledger + registry
                                  │                    P0d integrity, P0e, P0f
          ┌───────────────────────┼───────────────────────┐
          ▼                       ▼                       ▼
     S1 rule checks        S2 summary columns       S4 Progressive Ratio
          │                       │
          │                       ▼
          │                S5 yoked comparison
          └───────────┬───────────┘
                      ▼
            S3 reports, figures, views
                      ▼
                  S6 docs
```

- **Branches**: `pa-p0`, then `pa-s1-checks`, `pa-s2-summaries` and
  `pa-s4-pr` in parallel from P0's tip, each in its own worktree. Then
  `pa-s5-yoked` from S2's merge, and `pa-s3-reports` after S1, S2 and S5 are
  merged. S6 works on `v4_Dev` last.
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
  - `pdf_report.py` and `project_report.py`: S3 only.
  - `qc_viewer.py`: S1 owns the Opto tab, and S3 the Program tab.
  - `paradigm_families.py`: P0 creates it, and each stream adds only its
    own entries.
- **Each stream's report** names:
  - the files changed;
  - the acceptance criteria met, with test names;
  - any decision found unworkable;
  - the calibration evidence for each constant default.

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
