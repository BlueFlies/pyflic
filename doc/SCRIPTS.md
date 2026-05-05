# pyflic Scripts and the Script Editor

Scripts are named analysis pipelines stored inside `flic_config.yaml`. A script is a list of **steps** that run in order when you click **Run Script** in the hub. Each step calls one analysis action — loading data, computing a statistic, writing a CSV, or generating a plot — with the parameters you specify.

Scripts let you capture a complete, reproducible analysis workflow and re-run it in a single click, across any number of projects.

---

## Table of Contents

1. [How scripts work](#1-how-scripts-work)
2. [YAML structure](#2-yaml-structure)
3. [Available actions and parameters](#3-available-actions-and-parameters)
4. [Using the Script Editor](#4-using-the-script-editor)
5. [Running scripts from the hub](#5-running-scripts-from-the-hub)
6. [Tips and patterns](#6-tips-and-patterns)

---

## 1. How scripts work

When you run a script, the hub executes each step in the order they appear. Steps share a single loaded experiment object — loading happens once (in the `load` action) and every subsequent step operates on that same in-memory experiment.

**Output location.** All files written by a script go to:

```
project_dir/<config_stem>_results/analysis[_<start>_<end>]/
```

For example, running a script against `flic_config.yaml` with a start/end range of 0–240 minutes writes to `flic_config_results/analysis_0_240/`.

**Parameter resolution.** For any parameter that a step does not set explicitly, the value is resolved in this order:

1. The value set directly on the step in YAML (e.g. `binsize: 30`)
2. The hub's current spinbox value for that parameter

This means a step can deliberately inherit the user's current hub settings by leaving a parameter blank.

**Experiment type gating.** Some actions only make sense for a specific experiment type (e.g. `plot_well_comparison` requires a two-well experiment, `weighted_duration` requires hedonic). Actions that do not match the loaded experiment type are skipped with a log message — they do not raise an error.

---

## 2. YAML structure

Scripts live under the top-level `scripts:` key in `flic_config.yaml`. Each script is a YAML mapping with a `name` and a `steps` list.

```yaml
scripts:
  - name: "Standard Analysis"
    steps:
      - action: load
        start: 0
        end: 240
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
      - action: plot_dot
        metric: PI
      - action: pdf_report

  - name: "Quick Overview"
    steps:
      - action: load
      - action: basic_analysis
      - action: plot_feeding_summary
```

You can define as many scripts as you like. Each appears as an entry in the hub's script dropdown. Use **Run All Scripts** to execute every script in the YAML in sequence.

### The `load` step

Every script should start with a `load` step. It reads the DFM CSV files, applies the time window, and prepares the experiment object for all subsequent steps.

```yaml
- action: load
  start: 0      # minutes; omit to inherit from the hub
  end: 240      # minutes; 0 means through end of recording
  parallel: true
```

If no `load` step is present, the hub auto-loads with its current settings before running the first step.

### The `remove_chambers` step

Applies exclusions from `remove_chambers.csv`. If `group` is omitted, the script's `name` is used as the exclusion group key.

```yaml
- action: remove_chambers
  group: "Standard Analysis"   # optional; defaults to the script name
```

---

## 3. Available actions and parameters

All actions and their parameters are listed below. Parameters marked **required** must be present for the step to be valid. Parameters marked **inheritable** can be left blank to pick up the hub's current value.

---

### Load actions

#### `load`

Read DFM CSV files into memory.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | Start of the time window |
| `end` | float (min) | inherit | End of the time window; `0` = through end |
| `parallel` | bool | inherit | Load DFMs on a thread pool |

#### `remove_chambers`

Apply chamber exclusions from `remove_chambers.csv`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `group` | string | script name | Named exclusion group in the CSV |

#### `write_summary`

Write `summary.txt` to the analysis output directory. Records the experiment metadata, design table, and excluded chambers. Safe to call at any point in a script.

*(No parameters.)*

---

### Analyze actions

#### `basic_analysis`

Run the built-in feeding-summary pipeline. Equivalent to the hub's **Run full basic analysis** button.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `feeding_csv`

Write the per-chamber feeding summary to a CSV file.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `binned_csv`

Write per-chamber feeding metrics binned over time.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `binsize` | float (min) | inherit | Width of each time bin |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `weighted_duration`

Write a weighted-duration summary. *Requires hedonic experiment type.*

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `tidy_export`

Write a long-format CSV with one row per bout.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `kind` | `feeding` \| `tasting` | `feeding` | Which event class to export |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `bootstrap`

Compute nonparametric bootstrap confidence intervals for a metric, resampling at the chamber level.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | string | `PI` | **Required.** Metric name (e.g. `PI`, `MedDuration`, `Events`) |
| `mode` | `total` \| `A` \| `B` \| `mean_ab` | `total` | Which well/aggregation |
| `n_boot` | int | `2000` | Number of bootstrap iterations |
| `ci` | float | `0.95` | Confidence level (e.g. `0.95` for 95% CIs) |
| `seed` | int | `0` | Random seed for reproducibility |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `compare`

Run ANOVA or a linear mixed model comparing a metric across treatment groups, with optional Tukey HSD posthoc.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | string | `MedDuration` | **Required.** Metric to compare |
| `mode` | `total` \| `A` \| `B` \| `mean_ab` | `A` | Which well/aggregation |
| `model` | `aov` \| `lmm` | `aov` | `aov` = ANOVA; `lmm` = linear mixed model (DFM as random intercept) |
| `factors` | list of strings | — | Optional design factors to include in the model |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `light_phase_summary`

Write per-chamber feeding metrics split by light vs dark phase (requires `OptoCol1` in the DFM data).

*(No parameters.)*

#### `param_sensitivity`

Sweep a detection parameter across a list of values and report how key metrics change per treatment.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `parameter` | string | — | **Required.** Detection parameter to vary. One of: `feeding_event_link_gap`, `feeding_threshold`, `feeding_minimum`, `tasting_minimum`, `tasting_maximum`, `feeding_minevents`, `tasting_minevents`, `baseline_window_minutes`, `samples_per_second` |
| `values` | list of floats | — | **Required.** Values to sweep, e.g. `[0, 2, 5, 10, 15, 20]` |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `transition_matrix`

Write A-to-A, A-to-B, B-to-A, B-to-B bout transition counts per chamber. *Requires two-well experiment type.*

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `pdf_report`

Generate a multi-page PDF combining the feeding summary, binned time-course plots, and statistical tables.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metrics` | list of strings | `Licks, Events, MedDuration` | Metrics to include in the report |
| `binsize` | float (min) | inherit | Bin width for time-course plots |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

---

### Plot actions

All plot actions write a PNG to the analysis output directory and also display the figure in the hub's output panel.

#### `plot_feeding_summary`

Bar/jitter plot of per-chamber feeding metrics, one panel per metric.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `plot_binned`

Line plot of a metric binned over time, one line per treatment group.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | metric | `Licks` | **Required.** Metric to plot |
| `mode` | `total` \| `A` \| `B` \| `mean_ab` | auto | Well/aggregation (auto-selected from metric when omitted) |
| `binsize` | float (min) | inherit | |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `plot_dot`

Jittered dot plot of a metric by treatment, with mean ± SEM.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | metric | `Licks` | **Required.** Metric to plot |
| `mode` | `total` \| `A` \| `B` \| `mean_ab` | auto | Well/aggregation |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `plot_well_comparison`

Side-by-side comparison of a metric for Well A vs Well B. *Requires two-well experiment type.*

| Parameter | Type | Default | Description |
|---|---|---|---|
| `metric` | metric | `MedDuration` | **Required.** |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `plot_hedonic`

Hedonic-specific feeding plot. *Requires hedonic experiment type.*

| Parameter | Type | Default | Description |
|---|---|---|---|
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

#### `plot_breaking_point`

Per-DFM breaking-point plots. *Requires progressive_ratio experiment type.*

| Parameter | Type | Default | Description |
|---|---|---|---|
| `config` | int (1–4) | `1` | Breaking-point config number |
| `start` | float (min) | inherit | |
| `end` | float (min) | inherit | |

---

### Metric names

**Two-well experiments:** `Licks`, `PI`, `EventPI`, `LicksA`, `LicksB`, `Events`, `MedDuration`, `MedDurationA`, `MedDurationB`, `MeanDuration`, `MedTimeBtw`

**Single-well experiments:** `Licks`, `Events`, `MedDuration`, `MeanDuration`, `MedTimeBtw`, `MeanInt`, `MedianInt`

---

## 4. Using the Script Editor

The Script Editor is a dedicated GUI for building and editing scripts without hand-editing YAML. Open it from:

- The **Config Editor** toolbar (script icon, to the right of the theme toggle)
- The **Analysis Hub** → Load card → **Open Script Editor** button

The editor reads and writes the `scripts:` section of the currently open `flic_config.yaml`. Everything else in your YAML is left untouched.

> **Note:** Comments and custom formatting in `flic_config.yaml` are not preserved when the editor saves. The YAML is re-serialised cleanly, but all content is kept.

---

### Editor layout

The window is divided into four areas:

```
┌───────────────┬──────────────────────────┬───────────────┐
│               │  Script switcher bar     │               │
│   Palette     ├──────────────────────────┤   Inspector   │
│  (left pane)  │       Canvas             │  (right pane) │
│               │    (center pane)         │               │
└───────────────┴──────────────────────────┴───────────────┘
│                     YAML preview                         │
│                   [ Save to config ]                     │
└──────────────────────────────────────────────────────────┘
```

---

### Script switcher bar

The bar at the top of the canvas shows the currently selected script and provides three buttons:

| Button | Action |
|---|---|
| **+** (new) | Create a blank script |
| **rename** | Rename the current script |
| **delete** | Delete the current script (after confirmation) |

Use the dropdown to switch between scripts. Unsaved changes to the current script are preserved in memory while you switch.

---

### Palette (left pane)

The palette lists every available action, grouped by category (Load, Analyze, Plots). Each tile shows the action name, a short description, and a category colour on its left edge.

- **Search box** at the top filters tiles by name or description as you type.
- Actions that do not apply to the current experiment type are **dimmed** but still visible (hovering shows the reason).
- **Click** a tile to add that action as a new step at the end of the current script's step list.

---

### Canvas (center pane)

The canvas is the step list for the currently selected script.

**Script name.** The **Name** field at the top sets the script's `name:` in YAML. This name also appears in the hub's script dropdown and is used as the default exclusion group key for `remove_chambers` steps that don't set `group:` explicitly.

**Step cards.** Each step is shown as a card with:
- Its sequential number
- A category icon and colour strip
- The action name in bold
- A summary chip showing the key parameter values
- A warning icon (⚠) if the step has a validation issue (unknown action, missing required parameter, or incompatible experiment type)
- A **⋯** menu for duplicate, move up, move down
- A **✕** button to delete the step

**Reordering steps.** Select a step (click on it) and use the **▲ Move up** / **▼ Move down** buttons above the list to change its position. The same options are also available in the **⋯** context menu on each card.

**Selecting a step.** Clicking a card selects it (shown with a light blue tint) and loads its parameters into the Inspector on the right.

---

### Inspector (right pane)

The inspector shows the editable parameters for the currently selected step.

Each parameter is displayed with:
- Its label and a note explaining what it does
- An appropriate input widget (text field, number field, checkbox, or dropdown)
- For `start`, `end`, and `binsize`: an **Inherit** checkbox. When checked, the step leaves that parameter blank in YAML, so it picks up the hub's current value at run time.

Changes in the inspector are applied immediately to the step card and to the YAML preview.

---

### YAML preview (bottom pane)

The YAML preview shows the exact YAML that will be written to `flic_config.yaml` when you save. It updates live as you edit. The **Show full file** toggle switches between showing just the `scripts:` block and the entire YAML file content.

---

### Saving and reloading

| Button | Action |
|---|---|
| **Save to config** | Write all scripts to `flic_config.yaml`. The hub picks up the changes automatically. |
| **Reload from disk** | Discard any unsaved edits and re-read from the current file on disk. Prompts for confirmation if there are unsaved changes. |

---

## 5. Running scripts from the hub

Once scripts are saved in `flic_config.yaml`, they appear in the **Scripts** panel of the hub.

- **Script dropdown** — select which script to run. Hidden in subdir batch mode (see below).
- **Run Script** — execute the selected script. Output is streamed to the hub's output panel in real time. In subdir batch mode the label changes to **Run 'batch' in subdirs (N)**.
- **Run All Scripts** — run every script in the YAML in sequence. Useful for generating a complete set of outputs in one click. Hidden in subdir batch mode.

The hub also shows the Script Editor button (or use **Load → Open Script Editor**) to jump directly into editing.

### Subdir batch mode

The Project card has a **"Run 'batch' script in every subdirectory"** toggle. When enabled, clicking **Run Script** walks every immediate subdirectory of the project directory and runs the script named exactly `batch` from every YAML in each subdir that defines one. Each subdirectory is treated as its own independent project, so output files land inside that subdir's results folder.

- Subdirs whose YAMLs do not define a `batch` script are skipped with a log message.
- The single-project Load, Analyze, Plots, and Tools cards are hidden while this mode is active.
- This mode is mutually exclusive with the **"Run action for every YAML config"** toggle; enabling one disables the other.

To use this mode, give your pipeline script the name `batch` in each project YAML:

```yaml
scripts:
  - name: "batch"
    steps:
      - action: load
        start: 0
        end: 0
        parallel: true
      - action: basic_analysis
      - action: feeding_csv
      - action: pdf_report
```

---

## 6. Tips and patterns

### Name your multi-project pipeline script `batch`

If you run the same analysis across many experiment directories that live as siblings under a parent folder, name the pipeline script `batch` in each project's YAML. The hub's **"Run 'batch' script in every subdirectory"** mode (Project card) then lets you trigger all of them in a single click from the parent directory, without opening each project individually.

```yaml
scripts:
  - name: "batch"          # this exact name activates subdir batch mode
    steps:
      - action: load
        start: 0
        end: 0
        parallel: true
      - action: basic_analysis
      - action: feeding_csv
      - action: pdf_report
```

---

### Always start with `load`

Put a `load` step first with explicit `start` and `end` values. This makes the script self-contained — it will behave identically regardless of what the hub spinboxes happen to be set to.

```yaml
- action: load
  start: 0
  end: 240
```

### Follow `load` with `remove_chambers` and `write_summary`

This pattern documents the analysis conditions right after loading:

```yaml
- action: load
  start: 0
  end: 240
- action: remove_chambers
- action: write_summary
```

### Use `remove_chambers` groups to keep exclusion sets separate

If you have multiple scripts that use different exclusion criteria, give each script a distinct `group:` name in its `remove_chambers` step. The QC Viewer lets you save exclusions under named groups.

```yaml
scripts:
  - name: "Conservative"
    steps:
      - action: load
      - action: remove_chambers
        group: "Conservative"
      ...
  - name: "Permissive"
    steps:
      - action: load
      - action: remove_chambers
        group: "Permissive"
      ...
```

### Run multiple time windows from separate scripts

```yaml
scripts:
  - name: "First 2h"
    steps:
      - action: load
        start: 0
        end: 120
      - action: basic_analysis
      - action: plot_feeding_summary

  - name: "Last 2h"
    steps:
      - action: load
        start: 360
        end: 480
      - action: basic_analysis
      - action: plot_feeding_summary
```

Each script writes to its own `analysis_0_120/` or `analysis_360_480/` directory.

### Full pipeline example

```yaml
scripts:
  - name: "Full Analysis"
    steps:
      - action: load
        start: 0
        end: 0          # 0 = through end of recording
        parallel: true
      - action: remove_chambers
      - action: write_summary
      - action: basic_analysis
      - action: feeding_csv
      - action: binned_csv
        binsize: 30
      - action: tidy_export
      - action: compare
        metric: MedDuration
        model: aov
      - action: bootstrap
        metric: PI
        n_boot: 5000
        ci: 0.95
        seed: 42
      - action: transition_matrix
      - action: plot_feeding_summary
      - action: plot_binned
        metric: Licks
        mode: total
        binsize: 30
      - action: plot_binned
        metric: PI
        binsize: 30
      - action: plot_dot
        metric: PI
      - action: plot_dot
        metric: MedDuration
        mode: A
      - action: plot_well_comparison
        metric: MedDuration
      - action: pdf_report
        metrics: "Licks, PI, MedDuration"
        binsize: 30
```

### Sensitivity sweep before committing to parameters

Use `param_sensitivity` early in development to find a stable link gap before finalising the config:

```yaml
- action: load
- action: param_sensitivity
  parameter: feeding_event_link_gap
  values: [0, 2, 5, 10, 15, 20, 30]
```

The output CSV contains mean and SEM for Licks, Events, and MedDuration per treatment at each value, making it straightforward to plot a sensitivity curve in a notebook.
