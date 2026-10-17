# v4 data plan: reading firmware 4.0.0 recordings in pyflic

The plan for making pyflic analyse recordings written by PyMCU 4.0.0 from DFM
firmware 4.0.0: explicit, named Paradigms of six types, and a data file that
carries each Well's Paradigm state in every 200 ms row. It records every
decision made in the October 2026 design review and specifies the work as
seven streams that several agents can implement, with the interfaces the
streams share written down before the parallel ones start.

The decision and its reasons are in [adr/0016](adr/0016-the-data-file-is-the-authority-on-what-the-light-did.md),
with addenda to [adr/0014](adr/0014-progressive-ratio-breaking-point-is-the-first-gap-rule.md)
and [adr/0015](adr/0015-the-opto-program-and-a-light-qc-for-every-type.md).
Terms are in [../CONTEXT.md](../CONTEXT.md): *Generation*, *Paradigm*,
*Program Interval*, *Activation*, *Requirement* / *Progress*, *Firmware
Event*, *Phase* / *Acclimation*, *Hold*, and the redefined *Training* and
*Light Event*.

**Status (2026-10-17):** implemented on `v4_Dev` (Phase 0 and streams 3 to 7
merged); where the build departed from this plan is listed under
[As built](#as-built). Still open: the [bench checkpoint](#the-bench-checkpoint),
because no recording from a 4.0.0 board exists yet, so every statement about
the file comes from the PyMCU and firmware source; and a re-run of the real
Progressive Ratio dataset, which was not on the machine the streams ran on, so
decision 1's identity check rests on the generation-1 fixtures alone. The
pyflic-side reference for the data file is
[firmware-4-data-in-pyflic.md](firmware-4-data-in-pyflic.md).

- [Sources of truth](#sources-of-truth)
- [What changes for the user](#what-changes-for-the-user)
- [Decisions](#decisions)
- [The three generations](#the-three-generations)
- [Phase 0: the shared contract](#phase-0-the-shared-contract)
- [Stream 3: the light QC under explicit Paradigms](#stream-3-the-light-qc-under-explicit-paradigms)
- [Stream 4: Progressive Ratio on recorded state](#stream-4-progressive-ratio-on-recorded-state)
- [Stream 5: the light table, Program Facets, reports and figures](#stream-5-the-light-table-program-facets-reports-and-figures)
- [Stream 6: integrity, messages and the QC views](#stream-6-integrity-messages-and-the-qc-views)
- [Stream 7: help, guides and records](#stream-7-help-guides-and-records)
- [Delivery](#delivery)
- [As built](#as-built)
- [The bench checkpoint](#the-bench-checkpoint)
- [Not in this plan](#not-in-this-plan)

## Sources of truth

Sibling checkouts beside pyflic, both on branch `v4_Dev`. Where this plan and
they disagree, they win, and the plan is corrected.

| What | Where |
|---|---|
| Every data-file column, its missing-value rule and when it is meaningful | `PyMCU/docs/DataFileColumns.md` |
| The Program file format, the six Paradigm types, their settings and defaults | `PyMCU/docs/ProgramFormat.md` |
| What each firmware version can run | `PyMCU/docs/FirmwareCompatibility.md` |
| The design and its reasons | `PyMCU/docs/v4-paradigms-plan.md`, `PyMCU/docs/adr/0001`, `0002` |
| Shared vocabulary | `PyMCU/CONTEXT.md` |
| How the columns are written | `PyMCU/StatusPacket.py` (`DATA_COLUMNS`, `PARADIGM_COLUMNS`, `MISSING = "NA"`, `_ParadigmColumns`) |
| Interval / Cycle / Paradigm lookup, the Activation carry, the baseline, `Messages.csv`, `Program.txt` writing | `PyMCU/DFM.py`, `PyMCU/DFMGroup.py`, `PyMCU/MessagesList.py` |
| The export text | `PyMCU/Program.py`, `PyMCU/InstructionSet.py`, `PyMCU/Instruction.py`, `PyMCU/Paradigm.py` |
| The Paradigm rules, per millisecond, hardware-free | `DFMV3_V2/src/LEDControl.c`, tests in `DFMV3_V2/tests/test_ledcontrol.c` |
| Example programs | `PyMCU/FLICPrograms/ParadigmExamples.txt`, `OptoTest1`–`6` |

pyflic's own `docs/dfm-firmware-4-data-guide.md` (12 Oct) predated
`DataFileColumns.md` (16 Oct) and was superseded by it where they differ:
missing values are the literal `NA` (development builds before 16 Oct wrote
blanks, which the reader also accepts), baseline rows carry `Interval` 0 with
`Cycle` `NA`, `Phase` reads `M` during `Interval` 0, and three behaviours the
guide called open are settled by the firmware source (below). Stream 7
replaced the guide with [firmware-4-data-in-pyflic.md](firmware-4-data-in-pyflic.md)
and deleted it; its export example (its §7.1) is `tests/fixtures/Program_v4.txt`.

Facts from the source that the plan relies on and the documents do not all
state:

- OpenLoop and `On` wells never count Activations (`LEDControl.c`, the early
  return for `THRESHOLD_ON` and the OpenLoop case).
- `Requirement` is reported during Acclimation, as the first Main
  Requirement, with `Progress` 0.
- `Progress` returns to 0 in the same millisecond the Activation starts, and
  `Requirement` moves to the next value then. **The Requirement an Activation
  met is the one on the row before the row where `Activations` rises.**
- `OnMs` is a byte that counts 1 ms steps since the previous record,
  saturating at 255; it is nominally 200 but not clamped there.
- `Interval` `NA` after the program ends cannot reach the file: the idle
  instruction is sent only after the file is closed. `NA` rows come from
  toggling outputs during a recording, or an instruction number older than
  PyMCU's 256-entry history.
- `Program.txt` prints only Intervals whose first-pass start falls inside the
  Duration, lists only the first pass of a Repeating program, prints Circadian
  stamps as start plus elapsed, and prints thresholds before the baseline
  exists (raw on a first run; baseline-adjusted if the same loaded Program is
  run again without reloading).
- `Messages.csv` is unquoted CSV, its `Sample` column holds the record
  `Index`, its `Millisecond` is an unformatted float, and message text can
  contain commas.
- A recording's `DFM99_<n>.csv` is the Environmental Monitor: 27 columns,
  `W1`–`W6` relay and output states.

## What changes for the user

- A recording from a 4.0.0 board loads and is analysed as before, and the
  analysis also knows which Paradigm each row ran under, when each well left
  Acclimation, how many Activations each well earned, how much light each
  well received, and under a ratio Paradigm which Requirement each Activation
  met.
- Every optogenetic experiment, of any type, gets a **light table**
  (`analysis/light_summary.csv`, per chamber, and `light_wells.csv`, per
  well) carrying the same Treatment and factor columns as the feeding
  summary, so the Combined Analysis, the reports and the Plot Editor pool and
  test light behaviour like feeding.
- A **`Role`** column (Paired, Yoked, Mutual, Self, Open, Unlit) on every
  per-chamber row of an optogenetic experiment, derived from the program or,
  on a 4.0.0 recording, from the data.
- **Program Facets**: `facet_source: program` in the Design splits every
  metric by Program Interval, labelled by Paradigm name.
- The Progressive Ratio type covers both ratio Paradigms (ProgressiveRatio
  and FixedRatio), reads Training from `Phase`, Light Events from
  `Activations`, and reports the Requirement each Activation met.
- The light QC judges each Paradigm type by its own rule and reads the
  firmware's decisions instead of emulating them; five new checks with their
  own constants.
- A **Program timeline** figure and a per-well Paradigm-state table in the QC
  Viewer; `Messages.csv` on the Integrity tab; lost records, late records and
  unknown-instruction rows in the integrity report.
- A recording from an un-updated DFM through the new PyMCU (generation 2)
  says "no training information" everywhere instead of silently losing every
  Progressive Ratio group.

## Decisions

Every one of these was put to the design review and accepted. The streams
below implement them; a stream that finds one unworkable stops and reports
rather than deciding otherwise.

**Scope**

1. All three generations are supported. Generation 1 outputs stay identical
   on existing datasets (the real Progressive Ratio dataset is the regression
   baseline), with one deliberate exception, decision 24.
2. Fine mode (firmware 4.1.0, per-scan data) is out. The per-row Paradigm
   frame is keyed by `Index` so a fine table can join later; nothing else.
3. `DataFileColumns.md` and `ProgramFormat.md` are the authority. The pyflic
   guide is rewritten as a short pyflic-side document.
4. `Program.txt` stays optional. A generation-3 recording without one gets a
   loud warning (`pyflic lint`, `summary.txt`, the report cover, the Hub) and
   degraded analysis: type-dependent results are `NA` with the reason.
5. The Environmental Monitor (`DFM99_*.csv`, id 99) is never scaffolded, is
   refused as a DFM with a clear message if a config names it, and is not
   read. Its environment columns are a later change.

**Analysis**

6. New Paradigms meet the Experiment Types through a cross-cutting
   **light-behaviour layer** for every type, not a type per Paradigm. The
   Progressive Ratio type covers both ratio Paradigms. OpenLoop, ClosedLoop,
   FixedInterval and NonFeeding designs are analysed as Custom or Hedonic
   plus that layer.
7. Program Facets are a Design option, `facet_source`: `cutoffs` (default,
   today's `facet_cutoffs`), `program` (one Facet per Program Interval, its
   Cycles pooled), `program_cycles` (one per Interval and Cycle). Labels are
   the Paradigm name, prefixed `I<k> ` only when a DFM uses the same name in
   two Intervals; the label is the same across DFMs for the same name, so
   pooling within a Facet pools chambers under the same Paradigm. On
   generation 1 the Facets come from the program's clock schedule, noted as
   approximate; without a program, `facet_source: program` is a lint and
   load error. The Progressive Ratio type owns `facet_source`, as it owns
   `facet_cutoffs`.
8. `Phase` is not a Facet in general; it is `AcclimationEndMin` on the light
   table. The exception is Progressive Ratio, whose Training/Test Facets are
   the Paired Sucrose Well's Phase.
9. `Role` is general. Paired and Yoked keep their meaning in any design (one
   trigger chamber plus linked `Off` chambers); Mutual is linked trigger
   chambers, Self an unlinked trigger chamber, Open an `On` chamber, Unlit
   the rest. PR keeps `paired_chambers` as its config key and cross-checks it.
10. On generation 3 the no-program fallback derives trigger wells from
    `Activations` > 0 and linkage from identical `OnMs` columns, so Role, the
    light table and the lick-free checks work without a program.
11. Training on generation 3 ends at the Paired Sucrose Well's **first row in
    Phase `M` under a ratio Paradigm**: a preceding ClosedLoop Interval is
    part of Training, and Acclimation 0 with no preceding Interval makes
    Training empty, complete, and said so. A Paired Sucrose Well that never
    reaches `M` under a ratio Paradigm never completed Training.
12. The Test window ends where the ratio Paradigm's run ends, not at the end
    of the recording; only the first ratio run is the Test, a later one is
    noted and left to Program Facets. `pr_test_window_min` still caps it.
13. The Breaking Point keeps ADR-0014's rule. `pr_breaking_point.csv` gains
    `BreakRequirement` (the Requirement the last counted Activation met, read
    from the row before the increment) and `FirmwareEvents`; the Light Event
    Ledger gains `Requirement`, `FirmwareEvents` and `Phase`. The licks-per-
    event trend is also judged on Firmware Events per Activation.
14. For a FixedRatio Paradigm the type runs the same first-gap machinery;
    `BreakRequirement` is the constant Ratio, the report section is titled
    "Fixed ratio: activations earned", and the trend check is skipped.
15. A generation-2 Progressive Ratio member loads with one Facet labelled
    `Recording`, keeps every group, and says "no training information:
    recorded with DFM firmware older than 4.0.0" in `summary.txt`, the report
    cover, the Hub status, the Project Report's member row and the Stats
    text's flagged block. It is never pooled into Test.
16. The light table's headline metrics tested between treatments by default
    are `Activations`, `LitSec`, `FirmwareEvents` and `AcclimationEndMin`.
    Its full column set is in stream 5.
17. Light metrics appear in the experiment report's Results as a "Light
    behaviour" section for optogenetic members (dot plots by treatment per
    Facet with the generic comparisons), pooled the same way in the Project
    Report, and join the Plot Editor's faceted-metric family.
18. A generic Paired-minus-Yoked difference table outside Progressive Ratio
    is a follow-up, not in this plan (see Not in this plan).

**QC**

19. Explained Light per Paradigm type: ClosedLoop as today with `HoldMs` as
    the hold and `MaxOnMs` as the cut-off; FixedInterval and both ratio types
    explain an Activation's whole `ActivationMs` of light when the trigger
    well had a lick or touch within the tolerance of its onset, and contact
    during a FixedInterval lockout that earned nothing is expected;
    Acclimation rows follow the ClosedLoop rule with `ActivationMs` as the
    hold; NonFeeding is not judged by Explained Light but checked for light
    that stayed on through feeding; OpenLoop and `On` wells get the
    lit-fraction check only. On generation 3 lit time is attributed to
    Activations exactly (from the Activations increments and `OnMs`), so
    "unexplained" is "lit time of Activations whose onset had no pyflic
    activity". The thresholds (10 % warn, 30 % fail, 30 s floor) are the same
    for every type.
20. Fail: unexplained light (as today), broken yoking, a row Paradigm name
    absent from `Program.txt`. Warn: Acclimation count mismatch, lost
    records, late records, unknown-instruction rows beyond the `Idle`
    lead-in, Firmware Events disagreeing with pyflic's events, `Program.txt`
    missing on generation 3.
21. New design constants, each with a field in the Project Design dialog and
    the Config Editor:

    | Constant | Default | Meaning |
    |---|---|---|
    | `opto_event_disagreement_warn_fraction` | 0.25 | per trigger well, \|FirmwareEvents − pyflic feeding events\| / FirmwareEvents above this warns |
    | `opto_yoking_fail_fraction` | 0.01 | share of lit records in which linked wells' `OnMs` differ by more than 1 ms; above this the group fails |
    | `opto_lost_records_warn` | 25 | records missing from `Index` (5 s) above which the DFM warns |
    | `opto_unknown_rows_warn_fraction` | 0.01 | share of rows with an unknown instruction, after the `Idle` lead-in, above which the DFM warns |
    | `opto_late_records_warn` | 10 | rows with `OnMs` > 200 above which the DFM warns |

    None has data behind it; the bench checkpoint revisits all five.
22. The data-break detector is fixed (it crashes on any version-3 file with a
    break, and on a 90-column file fails on `Interval` first).
23. The simultaneous-feeding table reports the pre-correction counts
    (`lick_matrix`, already computed and discarded) beside the
    post-correction ones.
24. The light-phase summary becomes per chamber (a chamber's own wells'
    light) on every generation. This changes `light_phase_summary.csv` on
    generation 1 wherever chambers were lit at different times, and is the
    one exception to decision 1, named in the changelog.

**Vocabulary and records**

25. PyMCU's words are adopted for every concept new with 4.0.0; Training and
    Light Event stay pyflic's words for the PR-level ideas, each defined by
    generation. "Decay" leaves new prose for Hold; `opto_default_decay_ms`
    keeps its name. The data-file column is exposed as `ProgramInterval`,
    never bare `Interval`.
26. One ADR, 0016, with addenda to 0014 and 0015. The plan lives here, on
    `v4_Dev`.

**Test data and delivery**

27. Generation-3 test data come from a Python per-millisecond simulator in
    `tests/`, written first and shared by every stream, pinned to the
    firmware's golden values, with an opt-in cross-check that compiles the
    firmware's `LEDControl.c` through the installed `ziglang` package.
28. Phase 0 (fixtures, loader frames, program grammar, roles) is one
    sequential piece. Streams 3 to 6 are four parallel agents on branches off
    `v4_Dev`, each in its own worktree, gated on the full suite with no new
    failures (the suite has 6 pre-existing failures). Stream 7 runs last.
29. The disk cache's key gains a version bump and the mtimes of `Program.txt`
    and `Messages.csv`.
30. Baseline rows (`Interval` 0) and the `Idle` lead-in stay inside
    whole-recording feeding metrics and outside every Program Facet and every
    light judgement.
31. On generation 3 the feeding summary's `OptoOn_sec*` and the PR
    `LightOn_sec` come from `OnMs` (exact), and the summary says which source
    was used.

## The three generations

| Generation | Written by | Header | Paradigm columns | Training | Light |
|---|---|---|---|---|---|
| 1 | PyMCU 3.x, any V3 firmware | 27 columns | absent | `W` values above 40000 are in training; value − 65536 is the signal | `OptoCol1`, sampled at 5 Hz |
| 2 | PyMCU 4.0.0, firmware before 4.0.0 | 90 columns | present, every value `NA` | **none** | `OptoCol1` |
| 3 | PyMCU 4.0.0, firmware 4.0.0 | 90 columns | filled | `Phase` per well | `OnMs` exact; `OptoCol1` as a check |

Detection, once at load: no `Phase1` column → 1; `Phase1` present and every
value `NA` or blank → 2; any `A` or `M` → 3. `Phase` is filled on every
4.0.0 row, which is why it is the column tested; `Interval`, `Cycle` and
`Paradigm` can be `NA` on 4.0.0 rows. The `version` (2 or 3) that the file
name gives stays as a second axis.

## Phase 0: the shared contract

One agent, sequentially, on `v4_Dev`. Everything after Phase 0 imports these
names, so they are fixed here. A later stream that needs a change to them
proposes it in its report rather than making it.

### 0a. The simulator and fixtures: `tests/v4_fixtures.py`

A per-millisecond simulation of the six Paradigm rules as `LEDControl.c`
implements them, writing a complete recording folder.

```python
ON, OFF = "On", "Off"
CHOICE_LINKAGE = (1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6)

@dataclass(frozen=True)
class ParadigmSpec:
    name: str
    type: str                      # OpenLoop | ClosedLoop | FixedInterval | NonFeeding | ProgressiveRatio | FixedRatio
    frequency: int = 40
    pulse_width: int = 8
    hold_ms: int = 0               # ClosedLoop
    max_on_ms: int = 0             # ClosedLoop, NonFeeding
    activation_ms: int = 0         # FixedInterval, ProgressiveRatio, FixedRatio (and Acclimation)
    lockout_ms: int = 0            # FixedInterval
    on_delay_ms: int = 0           # NonFeeding
    series: str = "Arithmetic"     # ProgressiveRatio: Arithmetic | Exponential
    first_requirement: int = 1
    step: int = 0
    scale: float = 5.0
    rate: float = 0.2
    cap: int = 65535
    ratio: int = 0                 # FixedRatio
    event_gap_ms: int = 100
    acclimation: int = 0           # FixedInterval and ratio types

@dataclass(frozen=True)
class IntervalSpec:
    paradigm: str
    dark: bool
    thresholds: tuple[int | str, ...]   # 12 of int | ON | OFF
    minutes: float

@dataclass(frozen=True)
class Bout:                        # one scripted contact at a well
    start_s: float
    duration_s: float
    amplitude: float = 40.0

@dataclass(frozen=True)
class DFMSpec:
    dfm_id: int
    intervals: tuple[IntervalSpec, ...]
    bouts: Mapping[int, Sequence[Bout]]   # well (1-12) -> bouts
    linkage: tuple[int, ...] = CHOICE_LINKAGE
    program_type: str = "Linear"          # Linear | Repeating | Circadian | Constant

@dataclass(frozen=True)
class RecordingSpec:
    start: datetime
    duration_min: float
    paradigms: Mapping[str, ParadigmSpec]
    dfms: tuple[DFMSpec, ...]
    baseline: bool = True
    samples_per_second: int = 5
    seed: int = 7
    lead_in_records: int = 25      # Interval 0 rows before the first instruction

@dataclass
class SimTruth:                    # per DFM, what the engine did, for assertions
    activation_onset_ms: dict[int, list[int]]        # well -> ms of each Activation start
    requirement_met: dict[int, list[int | None]]     # well -> Requirement each Activation met (None outside ratio types)
    event_spans_ms: dict[int, list[tuple[int, int]]] # well -> Firmware Events
    acclimation_end_ms: dict[int, int | None]
    on_ms_total: dict[int, int]

@dataclass
class SimResult:
    rows: pd.DataFrame             # the 90 columns, typed as pandas reads them
    truth: SimTruth

def simulate(spec: RecordingSpec) -> dict[int, SimResult]
def program_text(spec: RecordingSpec) -> str                   # the 4.0.0 export, grammar of ProgramFormat §Program.txt
def messages_text(spec, *, index_gaps) -> str
def write_v4_recording(data_dir: Path, spec: RecordingSpec, *, split_hours: float = 12.0,
                       index_gaps: Mapping[int, Sequence[tuple[int, int]]] = {},   # dfm -> [(after_index, missing)]
                       error_bits: Mapping[int, Sequence[tuple[int, int]]] = {},   # dfm -> [(index, bits)]
                       program: bool = True, messages: bool = True,
                       blank_missing: bool = False) -> dict[str, Path]
def write_gen2_recording(data_dir, spec, **kw) -> dict[str, Path]  # same rows, every Paradigm column NA, W values clean
```

Engine rules, per well, per millisecond, from `LEDControl.c`:

- Signal: a resting level near 8 plus Gaussian noise (σ 0.3) plus the
  amplitude of any active bout. The 128-scan smoothing is **not** simulated;
  the signal is generated as the firmware's averaged value. The firmware
  threshold is the authored level plus the well's baseline, the mean of its
  first ten records, when `baseline` is true; the file writes the raw signal.
- Contact: signal above the firmware threshold. Firmware Event: starts when
  contact begins and the well's own light is off (`wasLit` is the well's own
  output, never linked light); ends once the signal has stayed below the
  threshold for `event_gap_ms`.
- OpenLoop: lit except `Off` wells; no Activations. ClosedLoop: lit during
  contact and `hold_ms` after; a continuous on-period is cut off at
  `max_on_ms` (0 = none) and stays off until the Event ends; one Activation
  each time the light comes on. FixedInterval: contact starts an Activation of
  `activation_ms` when none is running and `lockout_ms` has passed since the
  previous start; contact in progress starts the next one as soon as the
  lockout passes. NonFeeding: lit at the Paradigm's start, off during contact,
  on again `on_delay_ms` after contact ends, for at most `max_on_ms`; an
  Activation each time it comes on. Ratio types: an Event that brings Progress
  to Requirement starts an Activation of `activation_ms`, Progress returns to 0
  **at the start**, Requirement moves to the next series value then. Series:
  Arithmetic `first + step·(k−1)`, Exponential `round(scale·e^(rate·k) −
  scale)`, capped, k counting Main Activations only. Acclimation: each of the
  first N Events lights the LED during contact and `activation_ms` after,
  counts an Activation, and the Nth's end moves the well to `M`; Requirement
  shows the first Main value and Progress 0 throughout `A`.
- `On` and `Off` wells run no Paradigm: Phase `M`, no Activations,
  Requirement and Progress `NA`. Linkage ORs the lit mask; `OnMs` counts
  milliseconds after linkage and saturates at 255; `OptoCol1` is the mask at
  the record instant. Activations never reset within a recording. The same
  Paradigm name in consecutive Intervals keeps every well's state; a different
  name resets it.
- Rows: `Date`, `Time`, `MSec` from `start + Index × 0.2 s`; `Sample` counts
  rows written and `Index` counts records, so an injected gap advances `Index`
  but not `Sample`; `Dark`, `OptoFreq`, `OptoPW` from the Interval's Paradigm,
  0 on the lead-in; `Temp`, `Humid`, `LUX` 0.00; `VoltsIn` 5.01; `Error`
  from `error_bits`. The lead-in rows have `Interval` 0, `Cycle` `NA`,
  `Paradigm` `Idle`, every Phase `M`, Activations 0, Requirement and Progress
  `NA`, `OnMs` 0. A 12-hour split starts a new file with its own header. Every
  missing value is `NA`, or blank with `blank_missing=True`.
- `Program.txt`: the header lines, the `Paradigms:` block (every setting, in
  the export's order and units, only the chosen Series' settings for
  ProgressiveRatio), one `***DFM n***` block per DFM with `Linkage:`, `Program
  Type:` and `(stamp) Dark|Lit, NAME, t1..t12, N min` lines, Intervals beyond
  the duration omitted. `Messages.csv`: the header, "Recording started" and
  "Recording ended" from DFM 0, one `Skipped index` error per injected gap.

Ready-made specs: `choice_pr_spec()` (PyMCU's example: `Closed` 30 min then
`PR10` with Acclimation 10, A wells 20, B wells `Off`, `CHOICE_LINKAGE`, with
healthy, drifting, dead-LED and never-training groups), `one_of_each_spec()`
(one DFM per Paradigm type as in `ParadigmExamples.txt`), `fixed_ratio_spec()`
(`FR5` with Acclimation 3), `repeating_open_loop_spec()` (3 min On, 12 min
Off), `yoked_controls_spec()` (chambers 1–3 trigger, 4–6 `Off` and linked
to them, for Role).

`tests/test_v4_fixtures.py`, the golden values the simulator must reproduce:

- Exponential defaults: Requirements 1, 2, 4, 6, 9, 12, 15, 20, 25, 32, 40,
  50, 62, 77, 95.
- Arithmetic `FirstRequirement 1, Step 2, Cap 5`: Activations at Events 1,
  4, 9, 14 (Requirements 1, 3, 5, 5).
- FixedRatio `Ratio 3`: Activations at Events 3, 6, 9.
- Acclimation 3: exactly three Activations in Phase `A`, each lasting contact
  plus `activation_ms`; the first Main Activation needs Requirement k = 1;
  Requirement during `A` is that value and Progress 0.
- A linked `Off` well's `OnMs` equals the trigger well's while its
  Activations stay 0 and its Requirement is `NA`.
- OpenLoop and `On` wells: `OnMs` 200 every record, Activations 0.
- Progress is 0 on the row where Activations rises, and that row already
  shows the next Requirement.
- Contact held through a ClosedLoop `MaxOnMs` cut-off counts one Activation;
  a new Event after the gap counts the next.
- FixedInterval: contact held across a lockout counts an Activation at each
  lockout expiry.
- `write_v4_recording` reloads through pandas with the dtypes
  `DataFileColumns.md` prescribes to 90 columns, `NA` where meaningless, and
  an injected gap appears in `Index` but not `Sample`.

`tests/test_ledcontrol_crosscheck.py` (opt-in): skipped unless
`python -m ziglang` imports and `../DFMV3_V2/src/LEDControl.c` exists. Builds
a small C harness (`tests/ledcontrol_harness.c`) with
`python -m ziglang cc -std=c99 -I ../DFMV3_V2/src`, feeds the same
per-millisecond signal (as sums of 128 scans) to both, and compares
Activations, Requirement, Progress and Phase per millisecond for
`choice_pr_spec()` and `fixed_ratio_spec()`. Marked `slow`.

### 0b. Generation and the Paradigm frame: `pyflic/base/paradigm_state.py`, `dfm.py`

```python
GENERATION_FLAG, GENERATION_EMPTY, GENERATION_PARADIGM = 1, 2, 3
PARADIGM_COLUMNS: tuple[str, ...]      # Interval, Cycle, Paradigm, Phase1..12, Activations1..12, Requirement1..12, Progress1..12, OnMs1..12
IDLE = "Idle"

def detect_generation(df: pd.DataFrame) -> int
def split_paradigm_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame | None]
    # (the 27 original columns plus Minutes/Seconds, the 63 Paradigm columns or None on generation 1)

@dataclass(frozen=True)
class IntervalRun:
    program_interval: int | None      # None = unknown instruction; 0 = baseline
    cycle: int | None
    paradigm: str | None
    i0: int                           # sample index, inclusive
    i1: int                           # exclusive
    kind: str                         # "program" | "baseline" | "unknown"

class ParadigmState:
    minutes: np.ndarray                      # (n,)
    index: np.ndarray                        # (n,) the DFM's record Index
    program_interval: pd.array               # Int64, NA = unknown
    cycle: pd.array                          # Int64
    paradigm: pd.array                       # string, NA = unknown
    phase_a: np.ndarray                      # (n, 12) bool
    activations: np.ndarray                  # (n, 12) int
    requirement: np.ndarray                  # (n, 12) float, NaN where NA
    progress: np.ndarray                     # (n, 12) float, NaN where NA
    on_ms: np.ndarray                        # (n, 12) int

    def interval_runs(self) -> list[IntervalRun]        # contiguous runs by (program_interval, cycle)
    def lead_in_rows(self) -> int                        # Idle / Interval 0 rows at the start
    def unknown_rows(self) -> np.ndarray                 # (n,) bool, after the lead-in
    def late_rows(self) -> np.ndarray                    # (n,) bool: any OnMs > 200
    def index_gaps(self) -> list[tuple[int, int, float]] # (last index before, records missing, minute)
    def activation_onsets(self, well: int) -> np.ndarray # sample indices where Activations rose (repeated for a rise of 2)
    def activations_between(self, well, i0, i1) -> int
    def lit(self) -> np.ndarray                          # (n, 12) bool: on_ms > 0
    def lit_seconds(self, well, i0, i1) -> float         # sum(on_ms) / 1000
    def ratio_rows(self, well) -> np.ndarray             # (n,) bool: requirement not NaN
    def acclimation_runs(self, well) -> list[tuple[int, int]]
    def acclimation_end(self, well) -> int | None        # first index in M after at least one A
    def training_end(self, well) -> int | None           # first index in M under a ratio Paradigm (decision 11)
    def requirement_met(self, well, onset: int) -> int | None   # requirement[onset - 1, well], None if NaN or onset == 0
    def firmware_event_rises(self, well) -> np.ndarray   # indices where progress rose
    def firmware_events_between(self, well, i0, i1) -> int      # Σ requirements met at onsets in [i0, i1) + progress delta
    def wells_with_activations(self) -> frozenset[int]
    def identical_on_ms_groups(self, wells) -> list[tuple[int, ...]]
```

`DFM` gains `generation: int` and `paradigm: ParadigmState | None`;
`_LoadedDFM` carries both; `with_params` copies them. `raw_df` no longer
holds the 63 Paradigm columns (they were being copied into five derived
frames), so nothing downstream sees them except through `paradigm`.

Training detection in `dfm.py`: generation 1 unchanged; generation 3 builds
`in_training_data` from `ParadigmState.training_end` (per well: `Minutes` of
that index, `EverFlagged` = the well has any `A` row or any row under a
non-ratio Paradigm before its training end, `Cleared` = a training end
exists); generation 2 marks every well `never_flagged` and sets
`DFM.training_info = "none"`. `training_end_minutes` and
`training_flag_state` keep their signatures.

Also in 0b:

- `data_breaks` inserts `BreakIndex` and `GapSeconds` instead of `Index` and
  `Interval` (decision 22), with a test on a version-3 fixture that has a
  break and on a 90-column one.
- DFM-id discovery (`yaml_config.py`, `layout.py`, `project.py`) excludes id
  99; the loader refuses `id: 99` with "DFM 99 is the Environmental Monitor,
  not a DFM"; lint reports it.
- `cache.py`: `_CACHE_VERSION` to `"3"`, and `_data_hash` includes
  `Program.txt` and `Messages.csv` when present.
- `integrity_report` returns and prints `generation`; the full integrity
  work is stream 6.
- `summary_text` names each DFM's generation under *DFM details*.
- On generation 3 `OptoOn_sec*` come from `ParadigmState.lit_seconds`
  (decision 31); `lights_df` is still built from `OptoCol1` for every
  generation as the common denominator.

Acceptance: a generation-1, a generation-2 and a generation-3 fixture each
load, report their generation, and keep it through `with_params`; the real
Progressive Ratio dataset's outputs are unchanged; `training_end` on
`choice_pr_spec()` is the first `M` row under `PR10` for each Paired Sucrose
Well and `None` for the never-training group; the generation-2 fixture gives
every well `never_flagged` and `training_info == "none"`; the two data-break
cases no longer raise.

### 0c. The 4.0.0 export grammar: `pyflic/base/opto_program.py`

A second grammar beside the existing one, chosen by content (a `Paradigms:`
line, or an interval line whose head token is bare `Dark` or `Lit`), behind
one API.

```python
ON = "On"; OFF = "Off"
Threshold = int | str                    # a level, ON or OFF
def is_trigger(t: Threshold) -> bool     # a level
def threshold_from_legacy(value: int) -> Threshold   # 0 -> ON, -1 or > 1023 -> OFF, else the level

OPEN_LOOP, CLOSED_LOOP, FIXED_INTERVAL, NON_FEEDING, PROGRESSIVE_RATIO, FIXED_RATIO  # paradigm type strings; FIXED_RATIO = "fixed ratio" is new
CLOSED_LOOP_MAX                           # kept for old exports; type CLOSED_LOOP with max_on_ms > 0
RATIO_PARADIGMS = (PROGRESSIVE_RATIO, FIXED_RATIO)
FEEDING_PARADIGMS = (CLOSED_LOOP, CLOSED_LOOP_MAX, FIXED_INTERVAL, PROGRESSIVE_RATIO, FIXED_RATIO)
ACCLIMATION_PARADIGMS = (FIXED_INTERVAL, PROGRESSIVE_RATIO, FIXED_RATIO)

@dataclass(frozen=True)
class Paradigm:
    name: str
    type: str                             # one of the six
    frequency_hz: int
    pulse_width_ms: int
    hold_ms: int | None = None            # ClosedLoop HoldMs
    max_on_ms: int | None = None          # ClosedLoop, NonFeeding
    activation_ms: int | None = None      # FixedInterval, ratio types
    lockout_ms: int | None = None
    on_delay_ms: int | None = None
    event_gap_ms: int | None = None
    acclimation: int = 0
    series: str | None = None
    first_requirement: int | None = None
    step: int | None = None
    scale: float | None = None
    rate: float | None = None
    cap: int | None = None
    ratio: int | None = None
    generated: bool = False               # a name PyMCU made from old-format settings
    legacy: OptoParams | None = None      # the pre-4.0.0 numbers this was inferred from

    @property
    def hold(self) -> int | None          # the Hold (CONTEXT.md): hold_ms for ClosedLoop, activation_ms for FixedInterval and ratio types, None otherwise
    def requirement_for(self, k: int) -> int | None
    def describe(self) -> str             # "PR10 (ProgressiveRatio): ActivationMs 500 ms, Series Arithmetic, …" as the export prints it

@dataclass(frozen=True)
class ProgramInterval:
    index: int
    start: datetime | None
    dark: bool
    thresholds: tuple[Threshold, ...]
    paradigm: Paradigm                    # always set: parsed, or synthesised from the old export's F/P/D/L/M
    duration_min: float
    def trigger_wells(self, wells=None) -> list[int]
    def open_wells(self, wells=None) -> list[int]
    def off_wells(self, wells=None) -> list[int]
    def group_mode(self, wells) -> str    # any ON -> OPEN_LOOP; all OFF -> LIGHTS_OFF; else paradigm.type (OpenLoop type -> OPEN_LOOP)

class OptoProgram:
    paradigms: dict[str, Paradigm]        # the Paradigms: block (old export: the synthesised ones)
    grammar: str                          # "legacy" | "v4" | "simple" (***ALL DFM***)
    def interval_for(self, dfm_id: int, k: int) -> ProgramInterval | None   # the k-th printed line, 1-based
```

Rules: `Paradigms:` lines are matched before the interval parser (they contain
commas); `***Env Mon***` is ignored; `***ALL DFM***` yields `grammar ==
"simple"`, no sections and a warning "recorded without a Program: every well
Off"; the header's legacy `Default Opto …` keys are accepted only with the
legacy grammar; a `NAME (Type): …` line whose type is not one of the six is a
section-independent warning and the Paradigm is dropped. `program_rows()` and
`OPTO_PROGRAM_COLUMNS` become `DFM, Interval, Start, DurationMin, ProgramType,
Paradigm, ParadigmType, Generated, Dark, FrequencyHz, PulseWidthMs, HoldMs,
MaxOnMs, ActivationMs, LockoutMs, OnDelayMs, EventGapMs, Acclimation, Series,
FirstRequirement, Step, Scale, Rate, Cap, Ratio, Linkage, TriggerWells,
OpenLoopWells, LegacyF, LegacyP` (the last two `NA` for the new grammar).
`OptoParams.paradigm` keeps inferring the type for the legacy path and is
wrapped into a `Paradigm` with `generated=True` and PyMCU's generated-name
pattern (`ClosedLoop-40Hz-8ms-Hold500-MaxOn0`).

Acceptance: the example of the former guide's §7.1 (`tests/fixtures/Program_v4.txt`) parses
with every DFM section accepted, `trigger_wells()` returns the level wells,
`open_wells()` the `On` wells; the `***ALL DFM***` and `***Env Mon***` cases
behave as above; every existing legacy fixture parses unchanged and
`program_rows()` for it shows the same type and hold as before under the new
column names; `Paradigm.requirement_for` reproduces the golden series.

### 0d. Roles: `pyflic/base/opto_roles.py`

```python
ROLE_PAIRED, ROLE_YOKED, ROLE_MUTUAL, ROLE_SELF, ROLE_OPEN, ROLE_UNLIT, ROLE_UNKNOWN = "Paired", "Yoked", "Mutual", "Self", "Open", "Unlit", ""

@dataclass(frozen=True)
class LinkageView:
    groups: dict[str, tuple[int, ...]]     # label -> wells
    trigger_wells: frozenset[int]
    open_wells: frozenset[int]
    source: str                            # "program" | "data" | "none"

def linkage_view(section: DFMProgram | None, state: ParadigmState | None, lights: np.ndarray | None) -> LinkageView
def chamber_roles(view: LinkageView, chamber_of_well: Mapping[int, int]) -> dict[int, str]
```

`linkage_view` prefers the program (groups from `Linkage:`, trigger and open
wells from the union over Intervals); without one, on generation 3, trigger
wells are `state.wells_with_activations()` and groups are
`state.identical_on_ms_groups()` (source `data`); on generation 1 it is the
existing identical-lighting inference with every lit well a trigger (source
`none`, and every role `ROLE_UNKNOWN`). `chamber_roles`: in a group spanning
more than one chamber, a chamber holding a trigger well is Paired when it is
the only one and Mutual otherwise, and the other chambers are Yoked; a
trigger chamber alone in its group is Self; a chamber whose wells are all
`On` (or in an OpenLoop group) is Open; the rest are Unlit. The Progressive
Ratio type's `paired_from_program` is reimplemented on `chamber_roles`.

Acceptance: `yoked_controls_spec()` gives chambers 1–3 Paired and 4–6 Yoked
with and without `Program.txt`; `one_of_each_spec()` gives Open for the
OpenLoop DFM's `On` chambers; a linkage of two trigger chambers gives Mutual;
the real PR dataset's `paired_chambers` derivation is unchanged.

## Stream 3: the light QC under explicit Paradigms

Files: `pyflic/base/opto_qc.py`, `opto_light.py`; tests
`tests/test_opto_qc.py`, new `tests/test_opto_qc_v4.py`.

- **Windows.** On generation 3, `analyze_dfm` windows by
  `ParadigmState.interval_runs()`: a `program` run joins to
  `program.interval_for(dfm, k)` by its `program_interval`; a run whose k is
  beyond the printed lines, or whose Paradigm name is not in
  `program.paradigms`, is judged by the Paradigm looked up by name alone (type
  and settings) with thresholds unknown, plus a note; a name absent from the
  program raises `PARADIGM_NOT_IN_PROGRAM` (fail). Baseline and unknown runs
  are not judged; unknown rows beyond the lead-in count toward
  `UNKNOWN_INSTRUCTION_ROWS`. The clock-time schedule is used only on
  generation 1.
- **Modes.** Per linkage group per window: any `On` member → open loop; all
  `Off` → off; OpenLoop type → open loop for its non-`Off` members; else the
  Paradigm type. A well's rows in Phase `A` are closed loop with hold
  `activation_ms` for that well.
- **Explained Light** per decision 19. On generation 3 each Activation of a
  trigger well is the unit: its lit time is `OnMs` from its onset to the next
  onset or the light going out, and it is explained when `activity` at the
  well lies within `[onset − tolerance, onset + tolerance]` (fixed-length
  types) or within the ClosedLoop window (`hold + tolerance` before, tolerance
  after, as today). Linked-only wells inherit their group's judgement.
  Generation-1 rules are unchanged.
- **Drift evidence.** On generation 3 the emulated trigger is not run.
  `ContactWithoutActivitySec` becomes the lit time of Activations, and the
  time of Firmware Event rises, with no pyflic lick or touch at the trigger
  well; `LikelyCause` is derived from it as today. `EmulationApproximate` is
  `NA` on generation 3.
- **New checks** (flags, constants from decision 21): `YOKING_BROKEN` (fail;
  within a linkage group, the share of lit records whose wells' `OnMs` differ
  by more than 1 ms exceeds `opto_yoking_fail_fraction`, or a linked `Off`
  well shows Activations), `PARADIGM_NOT_IN_PROGRAM` (fail),
  `ACCLIMATION_COUNT_MISMATCH` (warn; Activations during a well's `A` run ≠
  the Paradigm's `acclimation`), `EVENT_DISAGREEMENT` (warn; per trigger
  well), `LOST_RECORDS`, `UNKNOWN_INSTRUCTION_ROWS`, `LATE_RECORDS` (warn;
  DFM-level), `PROGRAM_MISSING` (warn; generation 3 and no section).
  `FAILING_FLAGS` and `WARNING_FLAGS` are extended; `verdict_of` unchanged.
- **Columns.** `OPTO_QC_COLUMNS` gains `Generation`, `Role`,
  `FirmwareEvents`, `PyflicEvents`, `AcclimationActivations`,
  `AcclimationExpected`. `OPTO_INTERVAL_COLUMNS` gains `ProgramInterval`,
  `Cycle`, `Paradigm`, `ParadigmType`, `HoldMs` (replacing `DecayMs`),
  `LitSource`. `OPTO_EVENT_COLUMNS` gains `Well`, `RequirementMet`,
  `FirmwareEvents`, `Phase`, `Source` (`activations` | `optocol1`).
- `opto_light.py`: `plot_dfm` weights lit time by `OnMs` on generation 3 and
  titles the drift panel "firmware events, no lick" there; `experiment_notes`
  adds the program-missing and generation lines; `qc_table` carries `Role`.
  The QC Viewer tab's `_COLUMNS` gains `Role` (stream 6 owns the tab's other
  changes; coordinate through the column constant).

Acceptance: on `one_of_each_spec()` every group is ok with no unexplained
light; on `choice_pr_spec()` the drifting group fails with cause drift and the
dead-LED group warns `unlit feeding`; a fixture whose linked `Off` well is
given its own Activations fails `YOKING_BROKEN`; a fixture whose row Paradigm
is renamed fails `PARADIGM_NOT_IN_PROGRAM`; an Acclimation 10 group whose
engine is forced to 9 warns the mismatch; the generation-1 fixtures and the
real PR dataset keep their verdicts.

## Stream 4: Progressive Ratio on recorded state

Files: `pyflic/base/progressive_ratio_experiment.py`, `pr_light_qc.py`,
`pr_breaking_point.py`, `experiment_types/progressive_ratio.py`; tests
`tests/test_progressive_ratio.py`, `test_pr_light_qc.py`,
`test_pr_breaking_point.py`, new `tests/test_pr_v4.py`.

- **Training** (decision 11): `group_training` reads
  `dfm.training_end_minutes(sucrose)` as today; on generation 3 the per-well
  notes about the other three wells are retired (they are `Off` and read `M`),
  and a second `A` run on the Paired Sucrose Well later in the recording is a
  note "Paradigm restarted at Program Interval k". Generation 2: every group
  `TrainingComplete = NA`, one Facet `Recording` (decision 15), the summary
  line, and `require_training_complete` does not remove.
- **Light Events** (decision 13): on generation 3 the Paired chamber's Light
  Events are `ParadigmState.activation_onsets(sucrose)`; `OptoCol1` onsets
  stay for generation 1. `LEDGER_COLUMNS` gains `Requirement`
  (`requirement_met`), `FirmwareEvents` (`firmware_events_between` the
  previous onset and this one), `Phase`. `light_events_table` and
  `light_events_ledger` carry them.
- **Breaking Point**: `BREAKING_POINT_SUMMARY_COLUMNS` gains
  `BreakRequirement` and `FirmwareEvents`; `LargestRequirement` is kept for
  generation 1 and equals `BreakRequirement` on generation 3. The report and
  the Stats text show `BreakRequirement` beside `BreakingPoint`.
- **Test window** (decision 12): `_test_window` ends at the end of the first
  contiguous run of rows where the Paired Sucrose Well's `requirement` is not
  NaN, then applies `pr_test_window_min`; `TestMinutes` reflects it; a later
  ratio run adds a note.
- **FixedRatio** (decision 14): `paradigms_in(program)` recognises
  `FIXED_RATIO`; the trend check is skipped when the Test Paradigm is
  FixedRatio; the report section title changes; `pr_light_qc.judge_group`
  gains `firmware_events: np.ndarray | None` so "no increasing trend" is also
  judged on Firmware Events per Activation (decision 13).
- **Yoking**: the Yoked chamber's wells must show zero Activations and `OnMs`
  equal to the Paired Sucrose Well's; a difference is reported through
  stream 3's `YOKING_BROKEN`, which this stream consumes for its verdict text.
- `paired_from_program` uses `opto_roles.chamber_roles`.
- Type-mismatch notes: a program whose ratio Paradigm runs on a non-PR type,
  or a PR type whose program has no ratio Paradigm, stays a warning in
  `summary.txt` and lint.

Acceptance: on `choice_pr_spec()` the ledger's `Requirement` column is 1, 11,
21, … for the healthy group and `FirmwareEvents` equals it; the training end
of each group is the first `M` row under `PR10`; `TrainingComplete` is false
for the never-training group; on `fixed_ratio_spec()` `BreakRequirement` is 5
and no trend warning appears; the generation-2 fixture yields one `Recording`
Facet and no removal; the generation-1 fixtures and the real PR dataset's
`pr_light_qc.csv`, `pr_breaking_point.csv` and `paired_yoked_diff.csv` are
unchanged.

## Stream 5: the light table, Program Facets, reports and figures

Files: new `pyflic/base/light_summary.py`; `experiment.py`,
`windowing.py`, `experiment_types/base.py`, `yaml_config.py`, `yaml_lint.py`,
`project.py`, `project_report.py`, `pdf_report.py`, `pubfigures.py`,
`plot_editor` modules, `design_editor.py`, `config_editor.py`, `hub.py`,
`script_editor/actions.py`, `script_editor/runner.py`; tests
`tests/test_light_summary.py`, `test_program_facets.py`, plus the existing
report, project and editor tests.

**The light table** (decisions 6, 16):

```python
# light_summary.py
LIGHT_WELL_COLUMNS = ("DFM", "Well", "Chamber", "Treatment", <factor columns>, "Role", "Generation",
    "Paradigm", "ParadigmType", "ProgramInterval", "Cycle", "WindowMinutes", "LitSec", "LitFraction", "LitSource",
    "Activations", "ActivationsPerHour", "AcclimationActivations", "AcclimationEndMin", "AcclimationComplete",
    "FirmwareEvents", "LastRequirementMet", "ProgressAtEnd", "EventsPerActivation",
    "LockedOutContactSec", "UnlitSec", "Suppressions", "PyflicEvents", "PyflicLicks")
LIGHT_CHAMBER_COLUMNS = ("DFM", "Chamber", "Treatment", <factors>, "Role", "Generation", "Paradigm", "ParadigmType",
    "ProgramInterval", "Cycle", "WindowMinutes", "LitSec", "LitFraction", "LitSource", "Activations", "ActivationsPerHour",
    "AcclimationActivations", "AcclimationEndMin", "AcclimationComplete", "FirmwareEvents", "LastRequirementMet",
    "ProgressAtEnd", "EventsPerActivation", "LockedOutContactSec", "UnlitSec", "Suppressions", "EventsA", "EventsB")
HEADLINE_METRICS = ("Activations", "LitSec", "FirmwareEvents", "AcclimationEndMin")

def light_wells(exp, *, range_minutes=(0, 0)) -> pd.DataFrame
def light_summary(exp, *, range_minutes=(0, 0)) -> pd.DataFrame     # chamber rows: counts and times summed over the chamber's trigger wells,
                                                                    # AcclimationEndMin the latest, AcclimationComplete all
def light_wells_facet(exp) -> pd.DataFrame; def light_summary_facet(exp) -> pd.DataFrame   # Facet, FacetRange inserted like feeding_summary_facet
```

`Paradigm`, `ParadigmType`, `ProgramInterval` and `Cycle` are the single
value over the window or `mixed`. `LitSource` is `OnMs` or `OptoCol1`.
Type-specific columns are `NA` where the type does not define them, and
every type-dependent column is `NA` with the program missing (decision 4).
Basic analysis writes `analysis/light_wells.csv`, `light_summary.csv` and
their `_facet` variants for optogenetic members; the Combined Analysis stacks
`<project>_LightSummary.csv` and `<project>_LightWells.csv` with `Experiment`
first. `Role` (0d) is also written onto `feeding_summary.csv` rows, beside
`LitSec` and `Activations`, for optogenetic members.

**Program Facets** (decision 7): a Design key `facet_source` with values
`cutoffs | program | program_cycles`, in `DESIGN_KEYS`, owned by types with
`facets_fixed`. The facet machinery gains a per-DFM form:
`Experiment.facet_windows_for(dfm_id) -> list[tuple[str, tuple[float, float]]]`
(the global windows for `cutoffs`; the DFM's `interval_runs` joined and
labelled for `program`, from the program's clock schedule on generation 1
with a `summary.txt` note; one per run for `program_cycles`), and
`feeding_summary_facet`, `light_*_facet` and every `data_derived_facets`
consumer (Project frames, Stats text, the two reports, the design editor)
take their windows from it. `facet_labels()` is the ordered union of labels
across DFMs. Lint and load reject `program` without a program and the
coexistence of `facet_source: program` with `facet_cutoffs`. The Design
dialog and Config Editor get the picker.

**Reports and figures** (decision 17): `pdf_report` adds a "Light behaviour"
section after the feeding results for optogenetic members: one dot plot per
`HEADLINE_METRICS` by Treatment per Facet with the generic treatment
comparisons; the Project Report pools the stacked table the same way and its
member table carries the generation and the training-information note
(decision 15). `pubfigures` adds the four headline metrics (and the rest of
`LIGHT_CHAMBER_COLUMNS` that are numeric) to the faceted-metric family's
metric list, resolved from the stacked light table, so `faceted_activations`,
`faceted_litsec`, `faceted_firmwareevents`, `faceted_acclimationendmin` are
Plot Specs on the existing shape. The Hub's Optogenetics group gains **Light
summary CSV**; script action `light_summary` (writes the four CSVs), gated
like `opto_light_qc`.

Acceptance: on `one_of_each_spec()` the chamber table has one row per
chamber with the right `ParadigmType`, `LitSec` within one record of the
simulator's `on_ms_total`, `Activations` equal to the truth, and the
type-specific columns `NA` off-type; on `repeating_open_loop_spec()`
`facet_source: program` yields two Facets (`Open` lit, `Open` off → labelled
`I1 Open`, `I2 Open`) with Cycles pooled and `program_cycles` one per pass;
a Project of two optogenetic members stacks `<project>_LightSummary.csv` and
its report shows the Light behaviour section; the Plot Editor renders
`faceted_activations`; generation-1 members produce the table from
`OptoCol1` with `LitSource = OptoCol1`.

## Stream 6: integrity, messages and the QC views

Files: `pyflic/base/dfm.py` (`integrity_report`, the crosstalk table),
new `pyflic/base/messages.py`, new `pyflic/base/program_timeline.py`,
`qc_viewer.py`, `hub.py`, `pdf_report.py` (QC section), `experiment.py`
(`write_qc_reports`), `script_editor/actions.py` and `runner.py`; tests
`tests/test_integrity.py` (new), `test_messages.py` (new),
`test_qc_viewer_ui.py`, `test_hub_ribbon_ui.py`.

- **Integrity by generation.** Error-bit labels: on generation 1 bits 0 and
  1 together as "No ACK / overflow" (the two 2.0.0 builds cannot be told
  apart), on generations 2 and 3 `No Ack` (0x01) and `Overflow` (0x02); bits
  2–7 as today. `Index` starts at 1 and rises by 1: gaps are reported as lost
  records (count, time, length) through `ParadigmState.index_gaps` on
  generation 3 and a plain diff otherwise; repeats as rewritten rows,
  de-duplicated by `Index` at load with a note. New fields: `generation`,
  `lost_records`, `repeated_records`, `unknown_instruction_rows`,
  `late_records`, `paradigm_sequence` (name, first and last minute, rows).
  The report's integrity table gains `Lost records` and the verdict counts
  them.
- **`Messages.csv`.** `messages.read(data_dir) -> pd.DataFrame` with columns
  `DFM, Time, Index, Message, MsgType`: a tolerant reader (unquoted fields,
  commas inside the message, the unformatted float millisecond). Its `Error`
  rows are listed in the integrity text and on the QC Viewer's Integrity
  sub-tab, filtered to the DFM plus the MCU's own rows (DFM 0).
- **Crosstalk** (decision 23): the simultaneous-feeding CSV gains
  `Both_pre`, `MaxMinSignalAtBoth_pre`, `HigherInCol1AtBoth_pre` from
  `lick_matrix`, the report's table shows both, and the QC guide's section
  3.4 is updated by stream 7.
- **Program timeline figure.** `program_timeline.plot_dfm(exp, dfm_id,
  *, binsize_min=10)`: a top band of Program Intervals coloured by Paradigm
  type and labelled by Paradigm name (with Cycle for Repeating), then one
  lane per well with its Phase (`A` shaded), its Activation onsets as ticks,
  and its `OnMs` per bin as a heat strip; the Role of each chamber in the
  lane label. Written to `qc/program/program_timeline_dfm<id>.png` by `QC
  reports` and basic analysis for generation-3 members, included in the
  report's Quality control section, and offered on the Hub's Optogenetics
  group as **Program timeline** (script action `plot_program_timeline`). On
  generation 1 with a program the band comes from the clock schedule and the
  lanes show `OptoCol1` only.
- **QC Viewer.** Each DFM tab gains a **Program** sub-tab: the timeline figure
  above, a per-well table below (`Well, Chamber, Role, Paradigm, Phase,
  AcclimationEndMin, Activations, Requirement, Progress, LitSec`) at the end
  of the loaded range, computed from the loaded experiment so a Params
  recompute refreshes it. The Integrity sub-tab shows the messages table
  under the integrity text.

Acceptance: a generation-3 fixture with two injected gaps and an error byte
reports the lost-record count, the gap minutes and the right labels; a
generation-1 file's integrity text is unchanged apart from the new generation
line; `messages.read` parses a message containing commas; the timeline
renders for every fixture spec and for the real PR dataset (generation 1);
the Program sub-tab appears for a generation-3 member and not for a
generation-1 member without a program.

## Stream 7: help, guides and records

Runs after streams 3–6 merge. Files: `pyflic/help/content/*.md`,
`pyflic/help/toc.py`, `docs/qc-user-guide.md`,
`docs/progressive-ratio-user-guide.md`, `docs/GETTING_STARTED.md`,
`docs/firmware-4-data-in-pyflic.md` (new), `docs/dfm-firmware-4-data-guide.md`
(deleted), `CONTEXT.md`, `CHANGELOG.md`, `README.md`.

- `concepts-optogenetics`: the 4.0.0 export (the `Paradigms:` block, the
  interval line, `On`/`Off`), the six types and which setting is the Hold,
  the generation table, the per-type Explained Light rules, the new checks
  and constants, `Role`, the light table, Program Facets.
- `concepts-progressive-ratio`: Training by generation, Light Events from
  Activations, `BreakRequirement`, FixedRatio, the Test window's end, the
  generation-2 case.
- `config-structure`: `facet_source`; `config-dfms-chambers`: DFM 99,
  `Role`; `reference-parameters` unchanged; `plots-catalog`: the Program
  timeline and the light dot plots; `reports`: the Light behaviour section;
  `scripts-actions`: `light_summary`, `plot_program_timeline`;
  `app-qc-viewer`: the Program sub-tab and the messages; `troubleshooting`:
  program missing, unknown Paradigm name, broken yoking, lost records,
  generation 2.
- `docs/qc-user-guide.md`: sections 3.1, 3.4 and 6 revised and a section on
  reading the Program timeline; `docs/progressive-ratio-user-guide.md`:
  sections 2, 5.1, 5.2, 5.6 and 8; `GETTING_STARTED.md`: `Program.txt`
  wording covers both exports.
- `docs/firmware-4-data-in-pyflic.md`: what pyflic does with each column and
  where, by generation, linking to the PyMCU documents; the old guide is
  deleted.
- `CONTEXT.md`: Paired / Yoked generalised (decision 9), Mutual, Self, Open,
  Unlit added; Program Facet and Light table added; `Role` noted on
  Treatment. `CHANGELOG.md`: one entry per stream plus the decision-24
  exception. `README.md`: the firmware-4 document in the documentation table.
- `tests/test_help_refs.py` and the docs link checker pass.

## Delivery

```
Phase 0 (one agent, sequential, on v4_Dev)
  0a fixtures ──► 0b loader + ParadigmState ──► 0c grammar ──► 0d roles
                                 │
      ┌──────────────┬───────────┴────────────┬───────────────┐
      ▼              ▼                        ▼               ▼
  Stream 3        Stream 4                 Stream 5        Stream 6
  light QC        Progressive Ratio        light table,    integrity,
                                           facets, reports QC views
      └──────────────┴───────────┬────────────┴───────────────┘
                                 ▼
                             Stream 7 docs
```

- Branches: Phase 0 was delivered as three branches merged into `v4_Dev`
  (`v4-phase0-fixtures` and `v4-phase0-grammar` in parallel, then
  `v4-phase0-loader` for 0b and 0d; tip bbe30bb). Streams 3–6 branch from
  bbe30bb, each in its own worktree. Stream 5 is split in two agents, because
  Program Facets reshape the facet machinery independently of the light table:
  `v4-stream-3-light-qc`, `v4-stream-4-pr`, `v4-stream-5a-light-table` (the
  light table, Role on rows, reports, figures, Hub, decision 24),
  `v4-stream-5b-program-facets` (the `facet_source` key, per-DFM multi-window
  Facets, their consumers and editors) and `v4-stream-6-integrity`. They are
  merged back to `v4_Dev` one at a time; stream 7 works on `v4_Dev` after the
  last merge.
- Gate for every merge: `python -m pytest tests -q -p no:cacheprovider`, run
  from the checkout's root with the main `.venv`'s Python, with no failure that
  is not one of the eight pre-existing ones on `v4_Dev` at fbbcda1
  (`test_hub_batch_ui::test_the_preflight_previews_the_sheet_without_writing_it`,
  `test_hub_ribbon_ui::test_the_analysis_card_appears_only_with_a_project`,
  `test_layout_and_exclusion_sheet::test_rows_are_scoped_to_the_projects_actually_running`,
  `test_opto_editors_ui::test_the_constants_are_written_only_when_set`,
  `test_opto_editors_ui::test_a_hidden_section_keeps_what_the_file_says` (both
  from the "Make auto-filters optional" merge, which writes
  `min_untransformed_licks_cutoff: None`), two `test_parity_r` fixture-missing
  cases, `test_project::test_a_project_key_cannot_escape_its_batch`); the
  existing generation-1 tests unchanged, because the real Progressive Ratio
  dataset was not on this machine on 2026-10-17 and its test skips; `pyflic
  lint` clean on the fixtures.
- Shared surfaces two streams touch, and who owns them: `qc_viewer.py`
  (stream 6; stream 3 changes only `OptoTab._COLUMNS`), `hub.py` buttons
  (stream 5 adds Light summary CSV, stream 6 adds Program timeline, both
  inside the Optogenetics group), `pdf_report.py` (stream 5 the Results
  section, stream 6 the QC section), `script_editor/actions.py` (each adds its
  own action), `experiment.py` (stream 5 facets and light outputs, stream 6
  `write_qc_reports`). A stream that must touch another's file keeps the
  change to the lines named here and says so in its report.
- Each stream's report names: files changed, the acceptance criteria met with
  the test names, any Phase 0 interface it needed and did not have, and any
  decision above it found unworkable.

## As built

Where the implementation on `v4_Dev` departs from the plan above, and why. The
code is the authority on names and columns;
[firmware-4-data-in-pyflic.md](firmware-4-data-in-pyflic.md) describes it.

- **`Roles`, not `Role`, in the opto QC table.** A Linkage Group can touch
  several chambers with different Roles, so `opto_light_qc.csv` lists each
  chamber's (`1 Paired, 2 Yoked`). Per-chamber tables carry `Role`.
- **`facet_windows_for` returns several windows per Facet**
  (`[(label, [(a, b), ...]), ...]`), not one. A `program` Facet pools a
  Repeating program's Cycles, which are disjoint windows; every consumer takes
  a list of windows.
- **Stream 5 was split** into 5a (the light table, Role on rows, reports,
  figures, the Hub button, decision 24) and 5b (`facet_source`, per-DFM
  multi-window Facets, their consumers and editors), because Program Facets
  reshape the facet machinery independently of the light table.
- **`requirement_met` returns `None` for Acclimation Activations and for an
  Activation on the first row of a new Paradigm name**, not only for `NA` and
  onset 0. An Acclimation Activation meets no Requirement although its row
  already shows the first Main one; at a Paradigm change the row before belongs
  to the old Paradigm. Consumers fall back to the program's
  `requirement_for(k)` for the second case.
- **The ledger's `FirmwareEvents` window is (previous onset, onset]**: the
  Event that completed the Requirement lands in the onset row, so under a ratio
  Paradigm's Main phase the column equals the `Requirement` met.
- **`light_events_table`'s Training/Test column is now `Facet`** (it was
  `Phase`), because `Phase` now names the firmware's `A`/`M` column in the
  ledger, and the column also holds `Recording` on generation 2.
- **Repeated records are matched on `Index` plus time** (`Date`, `Time`,
  `MSec`), not on `Index` alone, so a DFM that restarted and counts from 1
  again with new records loses nothing.
- **`EVENT_DISAGREEMENT` needs at least 5 events** in either count
  (`MIN_FEEDING_EVENTS`): a fraction of a handful of events is noise.
- **`PROGRAM_MISSING` replaces `NO_PROGRAM_SECTION` on generation 3**, for a
  missing file and a missing section alike; `NO_PROGRAM_SECTION` stays for
  generations 1 and 2.
- **`LightOnsets` was added** to both light tables: the rising edges of a
  well's own light on every generation, on generation 1 the nearest thing to
  an Activation count.
- **Generation-2 groups have no breaking-point rows.** With no Test phase
  there is no break to report; the group's light QC notes say why.
- **A sixth new flag, *non-feeding light during feeding*** (warning), is the
  NonFeeding check of decision 19, which decision 20's list did not name. It
  reuses `opto_unexplained_warn_fraction` and `opto_unexplained_min_sec`
  rather than adding a constant.
- ***Program mismatch* also covers rows that name a defined Paradigm other
  than the printed line's.** The rows win and are judged by their own
  Paradigm.
- **The Firmware Events trend is a witness, not a second judge** (decision
  13). `TrendRhoFirmware` is measured and reported; the *no increasing trend*
  warning stays on pyflic's licks, and a firmware trend that rises while the
  licks do not is a note pointing at the lick detection.
- **The Environmental Monitor's file is `EnvMon_<n>.csv`**, not
  `DFM99_<n>.csv` as *Sources of truth* and decision 5 say
  (`PyMCU/EnvMonV3.py`, `DataFileColumns.md`). pyflic's `DFM*.csv` discovery
  never matches it; the id-99 exclusion stands and guards a file PyMCU does
  not write. Filing treats only `DFM*.csv` as recording files, so a loose
  `EnvMon_<n>.csv` is filed into `extra_files/`.
- **Decision 15's message has two wordings.** The Progressive Ratio type says
  *no training information: recorded with DFM firmware older than 4.0.0*
  (`summary.txt`, the report, its light QC); the light table's
  `NO_TRAINING_INFORMATION`, which the Hub's Loaded line, the Project Report's
  member Note and the Stats text use, says *no training information (firmware
  older than 4.0.0)*.

Completed after the stream merges, to close gaps the streams reported:

- the generation-3 missing-program warning, *DFM n: firmware 4.0.0 recording
  without Program.txt: Paradigm types and settings unknown*, in `pyflic lint`,
  the report's *At a glance* and the Hub's Loaded line (decision 4);
- `ParadigmType` in `pr_breaking_point.csv`, so the Project Report can title
  its section *Fixed ratio: activations earned* when every pooled group ran
  FixedRatio (decision 14);
- `LitSec` and `Activations` on the Progressive Ratio Facet rows;
- the Hub's **View QC plots** opens the Program timelines, and its **Program
  timeline** button uses the Analyze panel's bin size;
- the QC Viewer's Opto Light QC detail tables hide columns empty on every row.

## The bench checkpoint

When the first recording from a 4.0.0 board exists, before the streams are
called done, one agent diffs it against the fixtures and the loader:

- Header is the 90 `PARADIGM_COLUMNS`; every row has 90 fields; missing
  values are `NA`.
- The lead-in: how many `Interval` 0 rows, their `Paradigm` (`Idle` or `NA`),
  their `Dark`/`OptoFreq`/`OptoPW` (0).
- `Interval` changes on the first row the DFM ran the new instruction; the
  lag against `Program.txt`'s stamps.
- `Activations` rises in the record where the light starts; `OnMs` of a linked
  `Off` well equals the trigger well's; `Requirement` during `A`; `Progress` 0
  on the rising row.
- `OnMs` values above 200 and their frequency; `OptoCol1` against `OnMs > 0`.
- `Program.txt`: thresholds raw or baseline-adjusted (a re-run program), the
  omitted Intervals, the Repeating first pass.
- `Messages.csv`: the actual field shapes and any message with commas.
- The five constants of decision 21 against what a clean recording shows.
- The simulator's signal model against real `W` traces around Activations
  (the 128-scan lag).

Findings go into this document's status line and into the fixtures.

## Not in this plan

- **Fine mode** (firmware 4.1.0, `DFM<id>_fine_<n>.bin`): its own ADR when
  it exists. `ParadigmState.index` is the join key it will need.
- **A generic Paired-minus-Yoked difference** for non-PR designs: needs its
  own statistics and report section; `Role` makes it a filter today.
- **Reading the Environmental Monitor's file** (`DFM99_*.csv`) for
  temperature, humidity and light; the DFM rows carry the same columns.
- **Telling the two 2.0.0 firmware builds apart** in generation-1 error
  labels: not recorded in the file.
- **Re-running a Paradigm offline** with other thresholds: needs fine data.
- **Fixing the firmware's documentation** where the code disagrees with it
  (OpenLoop Activations, Requirement during Acclimation, Progress reset,
  `Interval` `NA`, `Program.txt` omissions, `Messages.csv` quoting,
  CONTEXT.md's "Acclimation can precede any Paradigm"): reported to the
  PyMCU and DFMV3_V2 repos, not changed from here.
