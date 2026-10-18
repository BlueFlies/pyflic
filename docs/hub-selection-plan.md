# Hub selection plan: checkboxes and one button per panel

The plan for turning the Hub's QC, Analyze and Plots panels from a button per
action into a checkbox per item over one button, following PySurvAnalysis's
ADR-0012. The decision and its reasons are in
[adr/0018](adr/0018-the-hub-runs-a-selection-not-actions.md). Terms are
[../CONTEXT.md](../CONTEXT.md)'s: *QC Set*, *Analysis Set*, *Plot Set*,
*Selection*.

**Status (2026-10-18): implemented on `v4_Dev`** (merged at d02ea6a; the gate on 0d25431 passes with only the eight pre-existing failures). *Analyze all* and Batch Runs are unchanged and do not read the Selection, and no run removes an output, by the user's choice.

- [What the user sees](#what-the-user-sees)
- [The three sets](#the-three-sets)
- [The contract](#the-contract)
- [Streams](#streams)

## What the user sees

The **QC panel** has a *QC* card and a *View* card.

- The *QC* card has group boxes of checkboxes: *QC reports*, then
  *Optogenetics* and *Progressive Ratio* when the member has them. **Run QC**
  is underneath.
- The *View* card keeps the three buttons that run nothing: **Open QC
  Viewer**, **View QC plots** and **Open qc folder**.

The **Analyze panel**:

- the *Bin size (min)* box, which the binned summary and the report use;
- the group boxes *Analyses*, *Optogenetics*, *Progressive Ratio*, *Hedonic*
  and *Report*;
- **Run analysis** underneath.

The core (feeding summary, its Facet variant, `summary.txt`, removed
chambers) always runs and has no checkbox. One line says so.

The **Plots panel** has the group boxes *Figures*, *Chosen metric* (with its
metric menu), *Progressive Ratio* and *Hedonic*, with **Generate plots**
underneath. Generate plots saves each ticked figure and opens it in a tab, as
the buttons did.

Every checkbox has a tooltip saying what it writes, and each group box keeps
its `?` help.

- **Ticking or unticking** writes the selection at once and logs one line,
  for example "Event statistics: left out of every run of 2026_10_17_rep1
  (flic_config.yaml global.omit)".
- **An item the data cannot answer** is greyed, with the reason, for example
  "No yoked group: no linkage group lights a Yoked chamber".
- **A hidden group** is one the member cannot have: two-well items on a
  single-well layout, optogenetic items on a run without light, a type's
  items under another type.

The **Project panel's *Analyze all*** is unchanged. It and a Batch Run's
`run_all_analyses` step run each member's Basic analysis, and its report
unless `reports: false`, and they do not read the Selection.

**No run removes a file.** An item left out keeps whatever an earlier run
wrote. The log and `summary.txt` say that this run left it out.

Two parts of the first version of this plan were considered and dropped by
the user's choice:

- *Analyze all* and `run_all_analyses` running Run QC, Run analysis and
  Generate plots for every member, each honouring its Selection;
- a run removing a left-out item's earlier outputs.

## The three sets

Ids are what `global.omit:` names. *Writes* gives the outputs the item
writes, as the code names them. A `*` is a DFM id or a metric.

### QC Set (`omit: qc:`), run by *Run QC*

| Group | Id | Label | Requires | Writes |
|---|---|---|---|---|
| QC reports | `integrity` | Data integrity | | `qc/integrity/DFM*_integrity_report.csv`, `.txt` |
| | `data_breaks` | Data breaks | | `qc/data_breaks/DFM*_data_breaks.csv` (the folder alone when no DFM has a break) |
| | `raw_signal` | Raw signal plots | | `qc/raw_signal/DFM*_raw.png` |
| | `baselined_signal` | Baselined signal plots | | `qc/baselined/DFM*_baselined.png` |
| | `cumulative_licks` | Cumulative licks plots | | `qc/cumulative_licks/DFM*_cumulative_licks.png` |
| | `simultaneous_feeding` | Simultaneous feeding | two-well | `qc/simultaneous_feeding/DFM*_simultaneous_feeding_matrix.csv` |
| | `bleeding` | Bleeding between wells | two-well | `qc/bleeding/DFM*_bleeding_matrix.csv`, `DFM*_bleeding_alldata.csv` |
| Optogenetics | `opto_light_qc` | Opto light QC tables | optogenetic | `qc/opto/opto_light_qc.csv`, `opto_light_intervals.csv`, `opto_light_events.csv`, `opto_program.csv` |
| | `opto_light_figures` | Light explained by licks | optogenetic | `qc/opto/opto_light_dfm*.png` |
| | `program_timeline` | Program timeline | optogenetic; greyed when no DFM has a timeline | `qc/program/` |
| Progressive Ratio | `pr_light_qc` | Light QC table | Progressive Ratio | `analysis/pr_light_qc.csv`, `analysis/pr_light_events.csv` |
| | `pr_light_event_figures` | Licks per light event | Progressive Ratio | `analysis/pr_light_events_dfm*.png` |
| | `pr_resting_level_figures` | Sucrose Well resting level | Progressive Ratio | `analysis/pr_resting_level_dfm*.png` |

QC is computed once (`compute_qc_results`) and then written item by item.
`write_qc_reports` keeps its signature and writes every item, so its callers
outside the Hub, such as the QC Viewer's Run QC, are unchanged.

### Analysis Set (`omit: analyses:`), run by *Run analysis*

The core always runs first: the auto-removal, `removed_chambers.csv`,
`summary.txt`, `feeding_summary.csv` and, with Facets,
`feeding_summary_facet.csv`.

| Group | Id | Label | Requires | Writes |
|---|---|---|---|---|
| Analyses | `binned_summary` | Binned summary | | `analysis/binned_feeding_summary.csv` |
| | `event_statistics` | Event statistics | | `analysis/tidy_feeding_events.csv` |
| Optogenetics | `light_tables` | Light tables | optogenetic | `analysis/light_summary.csv`, `light_wells.csv` and, with Facets, `light_summary_facet.csv`, `light_wells_facet.csv` |
| | `yoked_comparison` | Paired and yoked comparison | optogenetic, not Progressive Ratio; greyed when no yoked group | `analysis/yoked_comparison.csv` |
| Progressive Ratio | `paired_yoked_diff` | Paired-Yoked Difference | Progressive Ratio; greyed when no group has a yoked chamber | `analysis/paired_yoked_diff.csv` |
| | `cumulative_diff` | Cumulative difference table | Progressive Ratio | `analysis/pr_cumulative_diff.csv` (one-minute bins) |
| | `breaking_point` | Breaking point | Progressive Ratio | `analysis/pr_breaking_point.csv` |
| Hedonic | `weighted_duration` | Weighted duration summary | Hedonic | `analysis/treatment_means.csv` (`weighted_duration_summary(save=True)`) |
| Report | `experiment_report` | Experiment report (PDF) | | `analysis/experiment_report.pdf`, written last so it reflects the run |

### Plot Set (`omit: plots:`), run by *Generate plots*

| Group | Id | Label | Requires | Writes |
|---|---|---|---|---|
| Figures | `feeding_summary_plot` | Feeding summary | | `analysis/feeding_summary.png` |
| | `well_comparison` | Well A vs B | two-well | `analysis/well_comparison_*.png` (it draws `MedDuration`) |
| Chosen metric | `binned_time_course` | Binned time course | | `analysis/binned_*.png` |
| | `dot_plot` | Dot plot | | `analysis/dot_*.png` |
| Progressive Ratio | `pr_cumulative_diff_plot` | Cumulative difference curve | Progressive Ratio | `analysis/pr_cumulative_diff.png` |
| | `pr_cumulative_licks` | Training-aligned traces | Progressive Ratio | `analysis/pr_cumulative_licks_dfm*.png` |
| | `pr_still_responding` | Still-responding curve | Progressive Ratio | `analysis/pr_still_responding.png` |
| | `pr_breaking_point_plots` | Breaking-point plots | Progressive Ratio | `analysis/breaking_point_dfm*.png` |
| Hedonic | `hedonic_plot` | Hedonic feeding plot | Hedonic | `analysis/hedonic_feeding_plot.png` (`hedonic_feeding_plot(save=True)`) |

Each item calls the same function as today's button or action, with the
same inputs. The exact output names are those the code writes. A stream
that finds one different here follows the code and corrects this table.
Core corrected the tables to the code (2026-10-18), and fixed three inputs
where the button and the action disagreed:

- the optogenetic figures and the Program timeline are drawn as
  `write_qc_reports` draws them (10-minute bins), not at the Hub's Bin size;
- the Progressive Ratio's cumulative curves (`cumulative_diff`,
  `pr_cumulative_diff_plot`, `pr_cumulative_licks`) keep their one-minute
  resolution, the actions' and Basic analysis's default, rather than the
  Bin size the old buttons passed;
- *Run analysis*'s `summary.txt` includes the QC summary, as *Analyze all*'s
  Basic analysis writes it.

## The contract

**`pyflic/base/selections.py`** (pure: no Qt and no plotting imports):

```python
QC, ANALYSES, PLOTS = "qc", "analyses", "plots"          # the omit: kinds
OMIT_KINDS = (QC, ANALYSES, PLOTS)

@dataclass(frozen=True)
class Item:
    id: str
    kind: str              # QC | ANALYSES | PLOTS
    group: str             # the group box's title
    label: str
    caption: str           # the tooltip: what it is and what it writes
    requires: str | None   # "two_well" | "optogenetic" | "progressive_ratio" | "hedonic"
    outputs: tuple[str, ...]   # globs under the experiment directory

QC_SET: tuple[Item, ...]; ANALYSIS_SET: tuple[Item, ...]; PLOT_SET: tuple[Item, ...]
def items(kind) -> tuple[Item, ...]
def groups(kind) -> list[str]                            # in panel order
def applies(item, experiment) -> bool                    # requires met: else hidden
def unavailable(item, experiment) -> str | None          # applies but the data cannot: the reason
def omitted(experiment_or_config, kind) -> frozenset[str]
def set_included(experiment, kind, item_id, included) -> Path    # writes; returns the file written
def validate_omit(config) -> list[str]                   # for pyflic lint
```

- **`set_included`** writes `global.omit.<kind>`. For a member of a Project
  it writes to the Project's design in `project.yaml`, as the Design
  Editor writes design keys. For a standalone experiment it writes to
  `flic_config.yaml`. An empty list is removed, and the block with it.
  `omit` joins `DESIGN_KEYS`, and `yaml_lint`'s known global keys.
- **As built**, Core added, without changing the above:
  - `Item.excludes` (default `None`): the yoked comparison's "not
    Progressive Ratio";
  - `not_applicable_reason(item, experiment) -> str | None`, the reason
    behind `applies`;
  - `item(kind, item_id)`, `all_items()`, `selection_file(experiment) ->
    Path` and `selection_where(experiment, kind) -> str` (for log lines);
  - `set_included(..., *, project=None)`: given the loaded `Project`, its
    design is updated in memory, so the members it loads next see the
    change. A Member whose own `global:` states `omit:` has it
    removed, so it inherits. A Member of a Project with no `design: global:`
    raises `ValueError`, since there is no design to hold its Selection.
  - The Design Editor and the Config Editor keep `omit` when they save.

**`pyflic/base/run_selection.py`**:

```python
@dataclass
class SelectionRun:
    ran: list[Item]; left_out: list[Item]; not_applicable: list[tuple[Item, str]]
    figures: list[tuple[str, Any]]   # (title, figure) for tabs

def run_qc(exp, *, omit=None, log=print) -> SelectionRun
def run_analysis(exp, *, binsize_min=30.0, omit=None, log=print) -> SelectionRun
def run_plots(exp, *, metric="Licks", binsize_min=30.0, omit=None, log=print,
              keep_figures=True) -> SelectionRun
```

- **`omit`** defaults to the experiment's selection. A caller may pass more,
  for example the selection plus `experiment_report`. A given `omit` is used
  as given. The log calls an id that is in the Selection "unticked", and any
  other id "left out by this run".
- **As built**, `SelectionRun` also has `kind`, `written` (every file,
  the core's included), `item_outputs` (the files by item id), `reasons`
  (why each item was left out) and `lines()` (the left-out and
  not-applicable lines).
- **Each run logs** what it will run, what it leaves out (unticked) and what
  does not apply. *Run analysis* adds those lines to `summary.txt`. No run
  removes a file.
- **Script actions.**
  - `run_qc`, the existing key, now calls `run_selection.run_qc`. With
    nothing omitted, it writes what `write_qc_reports` wrote.
  - `run_analysis` (new) takes the parameter `binsize`.
  - `run_plots` (new) takes `metric` and `binsize`.

  All three are in the `ACTIONS` catalogue and the runner. The Hub's buttons
  run these actions.
- **`Project.run_all`** and the `run_all_analyses` step are unchanged: Basic
  analysis per member, and its report unless `reports: false`. They do not
  read the Selection (considered and dropped, see
  [What the user sees](#what-the-user-sees)).

## Streams

1. **Core** (`hs-core`): the contract above.
   - `write_qc_reports` split into per-item writers, behind its unchanged
     signature.
   - The script actions and lint.
   - Tests:
     - every item runs and writes what its table says;
     - `omit` leaves it out, says so, and removes nothing;
     - `run_qc` with nothing omitted writes the same files as before, proven
       on the fixtures;
     - `run_all` still runs Basic analysis;
     - the selection is written to the right file in both cases.
2. **Hub** (`hs-hub`, after Core):
   - the three panels as described, the View card, the tooltips, greyed
     items and hidden groups;
   - ticking writes through `set_included`;
   - the buttons run `run_qc`, `run_analysis` and `run_plots`, with the bin
     size and metric from the panel, and Generate plots opens its figures in
     tabs.
   - The Hub tests that pinned the old buttons are rewritten to pin the new
     panels.
   - The help topics: `app-hub.md`, `getting-started-first-run.md`,
     `plots-catalog.md`, `scripts-actions.md`, `reports.md` and the others
     that name the old buttons.
   - The CHANGELOG.

The gate for each: `python -m pytest tests -q -p no:cacheprovider`, with only
the eight pre-existing failures.
