# Hub selection plan: checkboxes and one button per panel

The plan for turning the Hub's QC, Analyze and Plots panels from a button per
action into a checkbox per item over one button, following PySurvAnalysis's
ADR-0012. The decision and its reasons are in
[adr/0018](adr/0018-the-hub-runs-a-selection-not-actions.md). Terms are
[../CONTEXT.md](../CONTEXT.md)'s: *QC Set*, *Analysis Set*, *Plot Set*,
*Selection*.

**Status (2026-10-18): being built on `v4_Dev`.**

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

The **Project panel's *Analyze all*** runs Run QC, Run analysis and Generate
plots for every member, each honouring its selection, without opening tabs.

## The three sets

Ids are what `global.omit:` names. *Writes* gives the outputs a run removes
when the item is left out. A `*` is a DFM id or a metric.

### QC Set (`omit: qc:`), run by *Run QC*

| Group | Id | Label | Requires | Writes |
|---|---|---|---|---|
| QC reports | `integrity` | Data integrity | | `qc/integrity/` |
| | `data_breaks` | Data breaks | | `qc/data_breaks/` |
| | `raw_signal` | Raw signal plots | | `qc/raw_signal/` |
| | `baselined_signal` | Baselined signal plots | | `qc/baselined/` |
| | `cumulative_licks` | Cumulative licks plots | | `qc/cumulative_licks/` |
| | `simultaneous_feeding` | Simultaneous feeding | two-well | `qc/simultaneous_feeding/` |
| | `bleeding` | Bleeding between wells | two-well | `qc/bleeding/` |
| Optogenetics | `opto_light_qc` | Light QC tables | optogenetic | `qc/opto/*.csv` |
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
| Optogenetics | `light_tables` | Light tables | optogenetic | `analysis/light_summary*.csv`, `analysis/light_wells*.csv` |
| | `yoked_comparison` | Paired and yoked comparison | optogenetic, not Progressive Ratio; greyed when no yoked group | `analysis/yoked_comparison.csv` |
| Progressive Ratio | `paired_yoked_diff` | Paired − yoked difference | Progressive Ratio; greyed when no group has a yoked chamber | `analysis/paired_yoked_diff.csv` |
| | `cumulative_diff` | Cumulative difference table | Progressive Ratio | `analysis/pr_cumulative_diff.csv` |
| | `breaking_point` | Breaking point | Progressive Ratio | `analysis/pr_breaking_point.csv` |
| Hedonic | `weighted_duration` | Weighted duration summary | Hedonic | the weighted-duration CSV (`weighted_duration_summary(save=True)`) |
| Report | `experiment_report` | Experiment report (PDF) | | `analysis/experiment_report.pdf`, written last so it reflects the run |

### Plot Set (`omit: plots:`), run by *Generate plots*

| Group | Id | Label | Requires | Writes |
|---|---|---|---|---|
| Figures | `feeding_summary_plot` | Feeding summary | | `analysis/feeding_summary.png` |
| | `well_comparison` | Well A vs B | two-well | `analysis/well_comparison_*.png` |
| Chosen metric | `binned_time_course` | Binned time course | | `analysis/binned_*.png` |
| | `dot_plot` | Dot plot | | `analysis/dot_*.png` |
| Progressive Ratio | `pr_cumulative_diff_plot` | Cumulative difference curve | Progressive Ratio | `analysis/pr_cumulative_diff.png` |
| | `pr_cumulative_licks` | Training-aligned traces | Progressive Ratio | `analysis/pr_cumulative_licks_dfm*.png` |
| | `pr_still_responding` | Still-responding curve | Progressive Ratio | `analysis/pr_still_responding.png` |
| | `pr_breaking_point_plots` | Breaking-point plots | Progressive Ratio | `analysis/breaking_point_dfm*.png` |
| Hedonic | `hedonic_plot` | Hedonic feeding plot | Hedonic | the hedonic figure (`hedonic_feeding_plot(save=True)`) |

Each item calls the same function as today's button or action, with the
same inputs. The exact output names are those the code writes. A stream
that finds one different here follows the code and corrects this table.

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

**`pyflic/base/run_selection.py`**:

```python
@dataclass
class SelectionRun:
    ran: list[Item]; left_out: list[Item]; not_applicable: list[tuple[Item, str]]
    removed: list[Path]; figures: list[tuple[str, Any]]   # (title, figure) for tabs

def run_qc(exp, *, omit=None, log=print) -> SelectionRun
def run_analysis(exp, *, binsize_min=30.0, omit=None, log=print) -> SelectionRun
def run_plots(exp, *, metric="Licks", binsize_min=30.0, omit=None, log=print,
              keep_figures=True) -> SelectionRun
```

- **`omit`** defaults to the experiment's selection. A caller may pass more,
  for example `run_all_analyses: {reports: false}` adds
  `experiment_report`.
- **Each run logs** what it will run, what it leaves out (unticked) and what
  does not apply. It removes the left-out items' earlier outputs and logs
  each removal. *Run analysis* adds those lines to `summary.txt`.
- **Script actions.**
  - `run_qc`, the existing key, now calls `run_selection.run_qc`. With
    nothing omitted, it writes what `write_qc_reports` wrote.
  - `run_analysis` (new) takes the parameter `binsize`.
  - `run_plots` (new) takes `metric` and `binsize`.

  All three are in the `ACTIONS` catalogue and the runner. The Hub's buttons
  run these actions.
- **`Project.run_all`** runs, per member, `run_qc`, `run_analysis` (with
  `experiment_report` omitted when `make_reports` is false) and
  `run_plots(keep_figures=False)`. `skip_analyzed` and the failure handling
  are unchanged. `run_all_analyses` keeps `reports` (default false) and
  `skip_analyzed`.

## Streams

1. **Core** (`hs-core`): the contract above.
   - `write_qc_reports` split into per-item writers, behind its unchanged
     signature.
   - The script actions, `Project.run_all`, and lint.
   - Tests:
     - every item runs and writes what its table says;
     - `omit` leaves it out, and removes its earlier outputs;
     - `run_qc` with nothing omitted writes the same files as before, proven
       on the fixtures;
     - `run_all` honours a member's selection;
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
