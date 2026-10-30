# Script Editor

A visual editor for the `scripts:` section of your configuration file. It writes the same
YAML you could write by hand, but it knows which actions exist and which parameters each
one takes, so you cannot invent an action that does not exist or misspell a parameter.

Open it from the Hub: **Open Script Editor** on the Scripts panel edits the loaded
member's `flic_config.yaml`, and **Edit scripts…** on the Project panel edits the
Project's `project.yaml`. The Config Editor opens it too, on the config it has open:
**File → Script Editor…** (Ctrl+E) or the scripts button in its top bar, once the config
has been saved. Press **F1**, or the `?` in its top bar, for this topic.

## Layout

The script switcher sits in the top bar. Below it, three panes side by side — the palette,
the canvas and the inspector — with the YAML preview beneath them.

Watch the preview while you work. It is the fastest way to build an accurate mental model
of the file format, and it means the editor never becomes a black box — you can always see
exactly what will be saved.

### The script switcher

**Script:** is a dropdown of the scripts in this file. The buttons beside it create a new
script, rename the current one and delete it. A deleted script stays recoverable until you
save: **Reload from disk** brings it back.

### The palette

The left pane, **Actions**: every action, grouped under LOAD, ANALYZE, QC and PLOTS, each
tile with its name and one line on what it does. Type in **Search actions…** to narrow the
list. Click a tile to add that step to the end of the script; with no script yet, the
editor asks for a name first. A dimmed tile does not fit this configuration's Experiment
Type — see [Actions for one Experiment Type](#actions-for-one-experiment-type). On a
`project.yaml` the tiles are the project actions — see
[Project Scripts in the editor](#project-scripts-in-the-editor).

### The canvas

The centre pane: the script's **Name:**, then its steps in order. Each step card shows the
action, the parameters set on it and, when something is wrong, a warning sign whose tooltip
says what.

- Select a step to edit it in the inspector.
- **Move up** and **Move down** reorder the selected step.
- The **⋯** on a card offers **Duplicate** (the copy goes to the end) and the same moves.
- The **✕** on a card deletes the step.

### The inspector

The right pane, **Step parameters**: the selected step's action and one field per
parameter, each with a note on what it does. A required parameter is marked `*`. A field
with **inherit from UI / script** ticked is left out of the YAML and inherits — see
[Inherited parameters](#inherited-parameters). Problems with the step, such as a missing
required parameter or an Experiment Type it does not fit, are listed at the bottom.

### The YAML preview

The bottom pane: the current script as it will be written. Tick **Show full scripts:
block** to see every script in the file instead.

## Working in it

1. Pick the script to edit, or create a new one, in the switcher.
2. Click an action in the palette to append it to the canvas.
3. Select a step on the canvas; set its parameters in the inspector.
4. Reorder steps until the sequence is right — order matters; see below.
5. **Save to config**.

**● unsaved changes**, at the right of the file path, shows there is something to save,
and **Save to config** works only then. **Reload from disk** discards your changes and
re-reads the file, which is what you want if you have also edited the YAML in a text
editor. Closing the window with unsaved changes asks whether to save them.

Saving rewrites the whole file, so **comments and formatting in it are not kept**. Keys the
editor does not show — a script's `notes:` or its `slice:`, a Project's
`experiment_scripts:` — are kept.

## Order matters

The canvas is a sequence, not a set, and several steps depend on what came before:

- `remove_chambers` must precede any analysis whose results should exclude those chambers.
- `write_summary` after `remove_chambers` records what was actually excluded.
- Plot and analysis steps can be in any order among themselves.

A `load` step, which older scripts begin with, does nothing wherever it sits: the member is
already loaded when a script starts. See
[The member is already loaded](scripts-overview.md#the-member-is-already-loaded).

## Inherited parameters

`slice` and, on most steps that take it, `binsize` have an **inherit from UI /
script** box in the inspector, ticked on a new step. Ticked, the parameter is left out of
the step and inherits: `slice` from the script's own `slice:`, else the whole recording;
`binsize` from the Analyze panel's **Bin size** box when the script
runs from the Scripts panel, else 30 minutes. The light figure, the Program timeline and
the Progressive Ratio curves have no such box: their `binsize` has its own default. See
[Where values come from](scripts-overview.md#where-values-come-from).

This is why a script can be re-run at another bin just by changing the Bin size box: leave
`binsize` inherited on the steps and they follow it. Untick the box and set a value when the
bin is part of the analysis rather than a thing you vary. The editor has no field for the
script's own `slice:`; write it in the YAML.

## Naming scripts

A script's name — set in the switcher or in the canvas's **Name:** field — is the default
exclusion group for a bare `remove_chambers` step, so pick names deliberately and keep them
consistent with the groups in your `remove_chambers.csv`.

An Experiment Script named `batch` has no special meaning any more — subdir-batch mode is
retired, and `pyflic lint` reports such scripts so you can rename them. The Project Script
named `batch` is different: it is what a Batch Run executes by default. See
[Running many projects at once](scripts-batch.md).

## Actions for one Experiment Type

The palette offers every action, but some need a particular layout or Experiment Type —
`plot_well_comparison` and `transition_matrix` a two-well layout, `plot_hedonic` and
`weighted_duration` a type with the Hedonic module, the `pr_*` and breaking-point actions a
type with the Progressive Ratio module. The palette dims those that do not match the
configuration's type, with the reason in the tooltip; you can still add one. The canvas
marks such a step with a warning sign, and the inspector repeats the reason. At run time a
step on the wrong kind of experiment is skipped with a log line.

The optogenetic actions — `opto_light_qc`, `plot_opto_light`, `light_summary` and
`plot_program_timeline` — are not dimmed, because whether a member is optogenetic depends on
its data. On one that is not, they are skipped with a log line too.

## Project Scripts in the editor

On a `project.yaml` the editor edits the Project Scripts in its `scripts:`, and its palette
and inspector offer the project actions instead of the Experiment Script ones — see
[Project actions](scripts-actions.md#project-actions). Add them, set their parameters,
reorder, delete and duplicate them as in an Experiment Script. None is dimmed: every project
action runs on any Project. To run an Experiment Script in the members, add
`run_in_experiments` and name the script.

An Experiment Script action found in a Project Script shows on the canvas with a warning
sign, as an unknown action, because a Project Script holding one is refused when it runs.
The Project's `experiment_scripts:` are not shown; edit those in the YAML.

---

Related: [What a script is](scripts-overview.md) · [Script actions](scripts-actions.md)
