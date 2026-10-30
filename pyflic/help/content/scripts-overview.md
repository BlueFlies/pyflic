# What a script is

A **script** is a named recipe: a list of steps under one name, run from the Hub. Instead
of clicking through the same panels every time you revisit an experiment, you define that
sequence once and run it in a click. The Hub's **Run QC**, **Run analysis** and **Generate
plots** are the steps `run_qc`, `run_analysis` and `run_plots`, so a script can do exactly
what they do.

Scripts also make an analysis reproducible. The sequence lives in the config alongside the
parameters that produced the results, so re-running months later gives the same output
without anyone remembering which buttons were pressed in which order.

## Two levels

There are two script levels with **separate action registries**, and they cannot mix. A
Project Script that names an Experiment Script action is refused before it starts, with
the step named. An Experiment Script that names a project action skips that step as an
unknown action.

| Level | Lives in | Acts on | Run from |
|---|---|---|---|
| **Experiment Script** | a member's `flic_config.yaml` `scripts:`, or a Project's `experiment_scripts:` | one loaded member | the **Scripts** panel |
| **Project Script** | `project.yaml` `scripts:` | the Project as a whole | the **Project** panel |

Each level is run from the panel of the thing it acts on, so the level a script belongs to
is never a question of which combo box you happened to click. The Scripts tile is dimmed
until a member is loaded, for the same reason Analyze and Plots are: with nothing loaded
there is nothing for an Experiment Script to run on. Project Scripts, needing no member,
stay available the moment a Project is open.

There is no third level. What a [Batch Run](scripts-batch.md) executes IS a Project Script.

The only bridge between the two is the `run_in_experiments` project action, which runs a
named Experiment Script in every member — or, with its optional `only:` list, in just
some of them.

```yaml
# project.yaml
experiment_scripts:              # one recipe, serving every member
  - name: standard
    steps:
      - action: basic_analysis
      - action: binned_csv
        binsize: 30

scripts:                         # Project Scripts
  - name: batch
    steps:
      - action: run_in_experiments
        script: standard
      - action: build_combined_analysis
      - action: project_report
      - action: render_publication_figures
```

Putting a recipe in `experiment_scripts:` means one copy serves every member instead of
being pasted into each of their configs. A member's own `scripts:` is the fallback when
the name is not found centrally.

Keep `build_combined_analysis` after the members' analyses. `project_report` builds the
Combined Analysis only when there is none yet, so without that step the report pools
whatever the last Combined Analysis held.

A Project Script is checked before it runs: every step must be a project action, and
`run_in_experiments` must name an Experiment Script that exists. It then stops at its first
failing step. `run_in_experiments` itself carries on past a member that fails, and logs how
many members ran.

### Built-in Project Scripts

Two pipelines every Project can run without authoring anything. Neither is written to
`project.yaml`, so they track the shipped default:

- **Standard Pipeline** — validate design → project report → render figures
- **Report Pipeline** — project report → render figures

Neither analyzes a member, and the report builds the Combined Analysis only when there is
none yet.

### The `batch` script every Project starts with

Every new `project.yaml` is seeded with a Project Script named `batch`, which is what a
Batch Run executes unless another script is designated:

- analyze all members → build combined analysis → project report → render figures

It has no `validate_design` step, which would fail Projects mid-migration. Edit or replace
it like any other script.

## Defining an Experiment Script

Scripts live under a `scripts:` key:

```yaml
scripts:
  - name: "Standard Analysis"
    slice: first_4h   # every step works on this Slice unless it names its own
    steps:
      - action: remove_chambers
      - action: write_summary
      - action: basic_analysis
      - action: feeding_csv
      - action: binned_csv
        binsize: 30
      - action: plot_feeding_summary
      - action: plot_binned
        metric: Licks
        mode: total
        binsize: 30
      - action: pdf_report

  - name: "Quick Overview"
    steps:
      - action: basic_analysis
      - action: plot_feeding_summary
```

Each script needs a `name` and a `steps` list. Each step needs an `action`; everything
else is optional. Define as many scripts as you like — each appears in the Scripts panel's
dropdown.

You do not have to write this by hand. The [Script Editor](scripts-editor.md) builds it
visually. The one thing it has no field for is the script-level `slice`: add it in the
YAML, and the editor keeps it when it saves.

## The member is already loaded

A script runs on a member that is already loaded: the one you loaded in the Hub, or, for
`run_in_experiments`, each member as the Project loads it. There is nothing to load first.

Scripts written for earlier versions begin with a `load` step. It still runs, and does
nothing: its `parallel` changes nothing, and a `start` and `end` on it are retired (see
[Slices](#slices)). Parallel loading is the Project panel's **Load DFMs in parallel**
option, used when you load a member.

## Start with `remove_chambers` and `write_summary`

```yaml
- action: remove_chambers
  group: "Standard Analysis"   # optional; defaults to the script's name
- action: write_summary
```

`remove_chambers` applies a group of exclusions from the member's `remove_chambers.csv`,
on top of the group its load already applied (see
[exclusions](config-dfms-chambers.md#excluding-chambers)). **When `group` is omitted it
defaults to the script's name**, which is what lets one CSV serve several scripts with
different exclusion sets. It also means a script name that does not match any group in the
CSV applies no exclusions at all, with only a log line saying the group lists no chambers —
so if exclusions seem not to be taking effect, check that spelling first.

`write_summary` records which chambers were excluded and what the experiment looked like
afterwards. Putting it immediately after exclusions means your summary describes the data
your results were actually computed from.

## Where values come from

For each step, a parameter is resolved in this order:

1. **The step itself** — `binsize: 30` written on that step
2. **The script level** — `slice:` set on the script
3. **The default** — for `slice`, the whole recording; for `binsize`, the Analyze
   panel's **Bin size** box when an Experiment Script runs from the Scripts panel, else 30
   minutes (in `run_in_experiments`, and so in a Batch Run). The light figure and the
   Program timeline (10 minutes) and the Progressive Ratio curves (1 minute) keep their own
   defaults instead.

So a step-level value always wins. A blank `binsize` follows the Hub's Bin size box, which
lets one script be re-run at another bin by changing it, while the values you *did* pin stay
pinned. A `slice` left blank on both the step and the script means the whole recording.

## Slices

A step works on the [Slice](concepts-slices.md) its `slice:` names, or the script's: the
Slice is loaded once, as the member was, and the step's outputs go to `slices/<name>/`. A
member whose recording does not cover the Slice skips the step and says why.

`run_qc`, `run_analysis` and `run_plots` without a `slice` run the whole recording and
every Slice the Selection keeps, as the Hub's buttons do; with one, that Slice alone.

The `start` and `end` steps once took are retired. A step that still states a window is
skipped with a log line naming the Slice to declare, and `pyflic lint` lists every such
script: a window that wrote into `analysis/` overwrote the whole recording's results.
To compare phases of one analysis side by side, declare [Facets](concepts-facets.md).

## Running them

- **Run** on the Scripts panel — the selected Experiment Script, on the loaded member
- **Run script** on the Project panel's Analysis card — the selected Project Script
- **Run Batch** on the Batch panel — one Project Script in every checked Project; see
  [Running many projects at once](scripts-batch.md)

Progressive Ratio members have their own actions — the difference table, the light QC,
the breaking point and their figures; see
[Script actions](scripts-actions.md#analyse-actions). A step whose action needs a different
Experiment Type is skipped with a log line, not an error.

---

Next: **[Script actions](scripts-actions.md)** — every action and its parameters.
