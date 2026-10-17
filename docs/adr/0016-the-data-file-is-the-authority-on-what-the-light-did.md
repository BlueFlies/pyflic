---
status: accepted
---

# The data file is the authority on what the light did

DFM firmware 4.0.0 and PyMCU 4.0.0 replace the guessed optogenetic paradigm
with explicit, named **Paradigms** of six types (OpenLoop, ClosedLoop,
FixedInterval, NonFeeding, ProgressiveRatio, FixedRatio), and the data file
grows from 27 to 90 columns: per row, the Program Interval, Cycle and Paradigm
name, and per well its Phase (Acclimation or Main), its running Activations,
its Requirement and Progress under a ratio Paradigm, and the milliseconds its
LED was active. Until now pyflic inferred all of that: Training from a flag
hidden in the signal, Light Events from a 5 Hz snapshot of the LEDs, the
paradigm from which of five numbers were zero, and the firmware's own trigger
by emulating it on the raw signal. The firmware now records what it decided,
so pyflic reads the decisions and stops inferring them wherever the file
carries them. The plan is `docs/v4-data-plan.md`; terms are in `CONTEXT.md`
(*Generation*, *Paradigm*, *Program Interval*, *Activation*, *Requirement* /
*Progress*, *Firmware Event*, *Phase* / *Acclimation*, *Hold*).

## Decisions

- **Three generations, detected from the file, branched on everywhere.** No
  file states its firmware or PyMCU version, so each DFM file is classified
  once at load from the `Phase1` column: absent (generation 1, 27 columns),
  present and all `NA` (generation 2, new PyMCU with an un-updated DFM),
  filled (generation 3). Generation-1 outputs stay identical on existing
  datasets; generation 2 has no Training information and says so instead of
  removing every Progressive Ratio group; generation 3 reads the recorded
  state. `version` (2 or 3, from the file name) stays as a second axis.
- **PyMCU's words for what is new.** Paradigm, Program Interval, Cycle,
  Activation, Requirement, Progress, Phase, Acclimation and Firmware Event
  enter pyflic's glossary as PyMCU defines them. Training and Light Event stay
  pyflic's names for the Progressive Ratio ideas, each defined by generation
  (Training is the Paired Sucrose Well's Phase `A`; a Light Event is the
  Trigger Well's Activation). "Decay" leaves new prose for Hold. The data
  file's `Interval` column is exposed as `ProgramInterval`, because the
  binned tables already use `Interval` for a time bin.
- **A light-behaviour layer for every Experiment Type, not a type per
  Paradigm.** A per-chamber (and per-well) light table with the same
  Treatment and factor columns as the feeding summary, pooled, tested and
  plotted like it; the Progressive Ratio type covers both ratio Paradigms;
  everything else is analysed as Custom or Hedonic plus the layer. Designs
  differ in one Program line, and a type each would multiply types for no
  analytical gain.
- **Program Facets as a Design option.** `facet_source: program` makes every
  Program Interval a Facet labelled by its Paradigm name, Cycles pooled
  (`program_cycles` separates them). A third facet source beside Design
  cutoffs and the Progressive Ratio training split, so the facet machinery is
  generalised to windows per DFM rather than given another special case.
- **`Role` is general.** Paired and Yoked mean the same in any design, and
  Mutual, Self, Open and Unlit cover the rest; derived from the program or,
  on generation 3 without one, from Activations and `OnMs`.
- **`Program.txt` stays optional, with a loud warning on generation 3.** The
  rows carry the Paradigm name but not its type, settings, thresholds or
  linkage, so without the file type-dependent results are `NA` with the
  reason. A recording is never unanalysable because one file was not copied.
- **Training ends at the first Main row under a ratio Paradigm**, so a
  ClosedLoop Interval before the ratio Interval counts as Training, and the
  Test window ends where the ratio run ends. The Breaking Point keeps
  ADR-0014's first-gap rule and gains the recorded Requirement beside it.
- **Test data from a simulator pinned to the firmware's golden values**,
  cross-checked against the firmware's own hardware-free `LEDControl.c`
  through the installed `ziglang` package, because no 4.0.0 recording exists
  yet. The first bench recording is diffed against both before the work is
  called done.

## Considered options

- **One new "Optogenetic" Experiment Type driven by the program**, or one type
  per Paradigm. Rejected: the treatment/factor structure already pools any
  per-chamber table, so a paradigm-aware table is what makes every design
  analysable, and the Progressive Ratio type's paired/yoked machinery is the
  only type-level analysis a Paradigm needs.
- **Requiring `Program.txt` on generation 3.** Rejected for a warning: the
  export is weaker than it looks (Intervals past the duration omitted, only
  the first pass of a Repeating program, thresholds raw or baseline-adjusted
  depending on whether the program was reloaded), so the rows, not the file,
  are the schedule, and the file adds type and settings.
- **Switching the Breaking Point to the firmware's last Requirement met.**
  Rejected: a Firmware Event with no pyflic lick is still the drifting-sensor
  signature, so the lick-backed count stays the measure and the Requirement
  is reported beside it.
- **Keeping the emulated trigger on generation 3.** Rejected: the firmware's
  Activations and Firmware Events are its decisions, recorded; emulation
  would reproduce them approximately from a baseline the file does not carry.
- **Compiling the firmware's `LEDControl.c` as the fixture generator.**
  Rejected as the primary path for a Python simulator in pyflic's own
  toolchain; kept as an opt-in cross-check.

## Consequences

- New outputs: `analysis/light_summary.csv`, `light_wells.csv` and their
  `_facet` variants; `<project>_LightSummary.csv` and `<project>_LightWells.csv`;
  `qc/program/program_timeline_dfm<id>.png`; `Role`, `LitSec` and
  `Activations` on optogenetic feeding-summary rows; `BreakRequirement` and
  `FirmwareEvents` in `pr_breaking_point.csv`; `Requirement`,
  `FirmwareEvents` and `Phase` in the Light Event Ledger.
- Five new design constants (`opto_event_disagreement_warn_fraction`,
  `opto_yoking_fail_fraction`, `opto_lost_records_warn`,
  `opto_unknown_rows_warn_fraction`, `opto_late_records_warn`) and one new
  Design key (`facet_source`).
- The light-phase summary becomes per chamber on every generation, the one
  deliberate change to generation-1 numbers.
- The disk cache's key gains a version bump plus `Program.txt` and
  `Messages.csv`, so members analysed under the old code are recomputed.
- `DFM99_*.csv` is recognised as the Environmental Monitor and never loaded
  as a DFM.
- Fine mode (firmware 4.1.0) and a generic Paired-minus-Yoked table for
  non-PR designs are explicitly deferred.
