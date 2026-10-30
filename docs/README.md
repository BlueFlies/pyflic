# pyflic documentation

The researcher's documentation ships inside pyflic as help topics: press
**F1** or a **`?`** button in any window, or run `pyflic help`. Their Markdown
is in [pyflic/help/content/](../pyflic/help/content/). This folder holds the
longer guides, the developer references and the decision records.

## Guides for researchers

- [Getting Started](GETTING_STARTED.md): installing and running pyflic, for
  someone new to Python.
- [Checking your data](qc-user-guide.md): every quality-control check, table
  and figure, including the optogenetic light QC and each Paradigm's rule
  checks.
- [Analysing a Progressive Ratio assay](progressive-ratio-user-guide.md): the
  Progressive Ratio assay end to end: settings, analyses, figures and
  statistics.
- [Slices: analysing part of a recording on its own](slices-user-guide.md):
  for users of the older ranged runs (`analysis_0_360/`): defining Slices,
  giving each the right excluded chambers, and where their results appear.
- [The firmware 4.0.0 data columns](v4-data-columns.md): the 63 columns a
  firmware 4.0.0 recording adds, and where pyflic uses them.

## For FLIC customers

- [Analysing FLIC Data: Options from the Pletcher Laboratory](flic-analysis-options.md):
  a short overview of the FLIC R Code and pyflic, where to get each, and why
  to move to pyflic.

## Guide for AI agents

- [Interpreting pyflic results](ai-agent-interpretation-guide.md): for an AI
  agent that summarises the outputs of a Batch, Project or experiment folder:
  every output file, how to recognise treatments and controls, how to weigh
  each QC check, and what each statistical test does and does not show.
  Written to be included in a larger prompt.

## References for developers

- [Firmware 4.0.0 data in pyflic](firmware-4-data-in-pyflic.md): what pyflic
  reads from each column of a DFM data file, by Generation; the light QC's
  checks; where each output is made and where it surfaces; and what is still
  to confirm on bench recordings.
- [Architecture decision records](adr/): one file per decision, numbered in
  the order they were made, each with its reasons and the options turned
  down.
- [CONTEXT.md](../CONTEXT.md): the glossary. The code, these documents and
  the help use its terms.

## Removed plans

Each of these plans set out a piece of work, recorded the decisions behind
it, and then said where the build departed from it. Once the work was built,
the plan was deleted. What a developer still needs from them is in
[Firmware 4.0.0 data in pyflic](firmware-4-data-in-pyflic.md), in the ADRs,
or below.

Code comments and tests still cite these plans by decision, stream or
contract, for example "decision 24 of docs/v4-data-plan.md". The text they
cite is in the commit given for each plan. To read it:

```bash
git show <commit>:docs/<file>
git show 82aace9:docs/v4-data-plan.md      # for example
```

- **`v4-data-plan.md`**, last text at **82aace9**. Reading firmware 4.0.0
  recordings: the three Generations, the Paradigm state, the 4.0.0
  `Program.txt` grammar, Roles, the light table, Program Facets, Progressive
  Ratio on recorded state, integrity and `Messages.csv`. It holds decisions 1
  to 31, Phase 0 (0a to 0d), streams 3 to 7 and an "As built" list. ADR-0016
  records the decision. Its bench checkpoint is now
  [To confirm on the first real recording](firmware-4-data-in-pyflic.md#to-confirm-on-the-first-real-recording).
- **`paradigm-analyses-plan.md`**, last text at **82aace9**. A light QC,
  summary columns and report content for each Paradigm Family, under every
  Experiment Type: the Activation ledger, the rule checks, the yoked
  comparison, Progressive Ratio solo groups and DFM restarts. It holds
  decisions 1 to 19, contracts C1 to C8, streams P0 and S1 to S6 and an "As
  built" list. ADR-0017 and ADR-0015's last addendum record the decisions.
  Its bench checkpoint is now
  [Bench checkpoint for the Paradigm analyses](firmware-4-data-in-pyflic.md#bench-checkpoint-for-the-paradigm-analyses).
  One follow-up is open: `rule_figures.py` recomputes the per-Paradigm values
  with private helpers of `opto_qc` and `rule_checks` (a test pins their sums
  to `opto_light_qc.csv`), and making those helpers public was left for
  later.
- **`hub-selection-plan.md`**, last text at **2b2360e**. The Hub's QC,
  Analyze and Plots panels as checkboxes over one button each: the QC,
  Analysis and Plot Sets, each item's id, requirement and outputs, and the
  contract of `selections.py` and `run_selection.py`, built as stream 1
  (Core) and stream 2 (Hub). ADR-0018 records the decision. The items, their
  ids and their outputs are now in `pyflic/base/selections.py`.
- **`experiment-type-definitions-plan.md`**, last text at **d0d559e**.
  Experiment Types as definitions built from Analysis Modules: the
  definition, the modules, the shipped types, the lab library and the copy
  beside the data, the light check, Control Comparisons (stream C), the
  Experiment Type Editor (stream D) and lint (stream E). ADR-0019 records the
  decision. Not built, as its "As built" list says: a mixed model for the
  Project's Role comparisons and Treatment controls, which use Welch's t and
  Dunnett's test on pooled chambers; and, in the editor, reordering the
  picked plots and resetting the library to its default folder. Still open:
  whether the real Progressive Ratio dataset's program fits the shipped
  ProgressiveRatio type
  ([To confirm on the first real recording](firmware-4-data-in-pyflic.md#to-confirm-on-the-first-real-recording)).
- **`progressive-ratio-implementation.md`**, last text at **ab74a95**. Three
  parts: a survey of the Progressive Ratio type before it was built (at
  8000615); the direction decided in the grilling sessions of 22 and 24
  September 2026; and two "As implemented" notes (2026-09-24, and 2026-10-17
  for solo groups, the Fixed Ratio wording, restarts and the series check)
  that mapped every output to the code. The type they describe,
  `ProgressiveRatioExperimentType`, is now the `ratio` Analysis Module
  (`pyflic/base/analysis_modules/ratio.py`), which the shipped
  ProgressiveRatio type includes. Its Chamber Group helpers are in
  `pyflic/base/experiment_types/progressive_ratio.py`, and the analysis is in
  `progressive_ratio_experiment.py`, `pr_light_qc.py` and
  `pr_breaking_point.py`. The notes' line numbers no longer match. ADR-0013
  and ADR-0014 record the decisions. For researchers, the
  [Progressive Ratio guide](progressive-ratio-user-guide.md) and the help
  topic *Progressive Ratio experiments* cover the same ground.

An earlier guide, `dfm-firmware-4-data-guide.md`, was replaced by
[Firmware 4.0.0 data in pyflic](firmware-4-data-in-pyflic.md) when the
firmware 4.0.0 work was documented. Tests still cite its export example
(its section 7.1, now `tests/fixtures/Program_v4.txt`); its last text is at
**9679d62**.
