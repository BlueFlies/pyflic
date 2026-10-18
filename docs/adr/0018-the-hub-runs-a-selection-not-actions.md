---
status: accepted
---

# The Hub runs a selection, not actions; the selection is configuration

The Hub's QC, Analyze and Plots panels had a button per action. Analyze had
eight: Basic analysis, Feeding summary CSV, Faceted summary CSV, Binned CSV,
Event statistics, PDF report and two Progressive Ratio tables. QC had eleven,
and Plots had nine. Getting everything a member needs meant clicking a dozen
buttons in the right order. Nothing said which had been run, and a Batch Run
produced a different set of files from the ones a person clicked. This
follows PySurvAnalysis's ADR-0012, which made the same change for the same
reasons.

## Decisions

- **Each panel is a checkbox per item over one button that runs them.**
  - QC lists the **QC Set** above *Run QC*.
  - Analyze lists the **Analysis Set** above *Run analysis*.
  - Plots lists the **Plot Set** above *Generate plots*.

  Items that only some designs have sit in a group box of their own:
  Optogenetics, Progressive Ratio, Hedonic, and the plots of a chosen metric.
  A group is hidden when the member cannot have it. An item the design allows
  but the data cannot answer is greyed, with the reason in its tooltip.
  Windows and look-ups stay buttons, because they run nothing: Open QC Viewer,
  View QC plots and Open qc folder.
- **The ticks are configuration, not UI state.** `global.omit:` names the ids
  a run leaves out, under `qc:`, `analyses:` and `plots:`. It sits in a
  standalone experiment's `flic_config.yaml`, or in the Project's design,
  which is the authority over every member's `global:`. Storing what is left
  *out* means a config nobody touched runs everything, and an item a later
  version adds is included until someone unticks it. `pyflic lint` warns on
  an id no run produces, because a misspelt id would leave nothing out.
- **One code path for a click and a script.** The Hub's three buttons run
  the script actions `run_qc`, `run_analysis` and `run_plots`. Each runs its
  set minus the config's `omit:`, so a script that names them and a click
  produce the same files. The single-item actions stay the script
  vocabulary, and `basic_analysis` keeps its meaning for scripts that name
  it.
- **Analyze all and Batch Runs are unchanged.** The Project's *Analyze all*
  and the `run_all_analyses` step still run each member's Basic analysis,
  with its report unless `reports: false`, and do not read the Selection.
- **The core always runs.** *Run analysis* always writes the feeding
  summary, its Facet variant, `summary.txt` and the removed chambers.
  Every other item reads them, so they are not in the set.
- **A run states what it left out.** The log and `summary.txt` list each
  left-out item as a choice. They list separately the items that do not
  apply, which is a property of the data. No run removes a file: an item
  left out keeps whatever an earlier run wrote, and the log and
  `summary.txt` say that this run left it out.

## Considered options

- **Ticks as Hub-session state, with scripts and Batch Runs running
  everything.** Rejected: the same experiment would yield different files
  depending on who ran it, with nothing saying why.
- **Analyze all and `run_all_analyses` running Run QC, Run analysis and
  Generate plots for every member, each honouring its Selection.**
  Considered and dropped by the user's choice: Analyze all and Batch Runs
  keep Basic analysis. A Batch Run's files can therefore differ from a
  click's. The Selection still governs the Hub's buttons and any script
  that names the three actions.
- **A run removing a left-out item's earlier outputs**, so a folder never
  shows a stale result as current. Considered and dropped by the user's
  choice: no run deletes a file.
- **Store what is included.** Rejected: an item added later would be
  silently missing from every existing experiment.
- **Keep the single-item buttons beside the checkboxes.** Rejected: that
  gives two ways to run one analysis. The single items remain script steps.
- **Each member of a Project keeps its own selection.** Rejected: a
  Project's replicates are analysed alike, and the design already holds what
  they share.
