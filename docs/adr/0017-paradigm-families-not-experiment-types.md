---
status: accepted
---

# Paradigm Families, not Experiment Types, decide the light content

Firmware 4.0.0 runs six Paradigm types. Each lights the LED by its own rule,
with settings the old firmware lacked: a closed loop's Hold and `MaxOnMs`, a
FixedInterval's lockout, a progressive ratio's series, a NonFeeding's relight
delay. After the v4 work, pyflic read all of them but checked few: one light
QC with type-specific branches, and one light table whose report showed the
same four measures for every program. The plan in
`docs/paradigm-analyses-plan.md` gives each type a QC against its own rule and
the summaries its rule makes meaningful. The question was where that content
hangs. The term is in `CONTEXT.md` (*Paradigm Family*).

## Decisions

- **The Paradigm types in `Program.txt` decide the light content, under every
  Experiment Type.** An Experiment Type describes the feeding design: the
  chamber layout, PI, Training and Test. A Paradigm describes the light, and
  one program can mix types across DFMs, Program Intervals and Phases. So the
  light QC, the light table's columns, the report's rule subsections and the
  *Light behaviour* results follow the types present, whatever the type of
  the experiment. Progressive Ratio remains an Experiment Type, because its
  Training, Test and breaking point are a feeding design, and it reads the
  ratio family's checks like any other type.
- **Four families share code**: open loop, closed loop (with Acclimation),
  fixed length (with an Interval and a Ratio branch), and non-feeding. A type
  gets a check of its own only for a setting its family's rule lacks:
  `MaxOnMs`, `LockoutMs` or the Requirement series. A Well's family follows
  its Phase, so Acclimation is judged as closed loop under any type.
- **One ledger of Activations feeds every family.** The generation-3
  light-events table gains each Activation's lit milliseconds, its timing to
  the millisecond and its place in its Paradigm-state run. Every family check
  and summary is an aggregation over the ledger, so a family is added in one
  place, the registry in `pyflic/base/paradigm_families.py`.
- **The checks run on generation 3 only.** Snapshots of `OptoCol1` every 200
  ms cannot time a light period, so generations 1 and 2 keep the checks they
  had, and the report names the ones that did not run.

## Considered options

- **An Experiment Type per Paradigm type** (ClosedLoop, FixedInterval,
  NonFeeding, OpenLoop). Rejected. A program that runs ClosedLoop then
  ProgressiveRatio, or a different type on each DFM, would fit no single
  type. The light would also be tied to choices about layout and statistics
  that have nothing to do with it, and every design would have to be
  declared twice: once in the config, once in `Program.txt`.
- **A check per Paradigm type with no grouping.** Rejected. ClosedLoop and
  Acclimation share the hold rule, and FixedInterval shares the fixed length
  with the ratio types. Six separate checks would duplicate both and could
  drift apart.
- **Leave the content generic** and add the new measures to the CSVs only.
  Rejected. The measures that distinguish the rules never reached a report,
  so a broken lockout or a wrong series went unseen.
