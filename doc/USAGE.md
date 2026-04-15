# pyflic Usage Guide

Source code: [https://github.com/PletcherLab/pyflic](https://github.com/PletcherLab/pyflic)

---

## Table of Contents

1. [What pyflic does](#1-what-pyflic-does)
2. [Project directory layout](#2-project-directory-layout)
3. [Configuration file (`flic_config.yaml`)](#3-configuration-file-flic_configyaml)
4. [Scripts — automated hub pipelines (`scripts:`)](#4-scripts--automated-hub-pipelines-scripts)
5. [Command-line tools](#5-command-line-tools)
6. [Python API](#6-python-api)
7. [Typical workflows](#7-typical-workflows)
8. [Jupyter notebooks](#8-jupyter-notebooks)

---

## 1. What pyflic does

pyflic analyzes data from **FLIC (Fly Liquid-food Interaction Counter)** experiments, which measure licking behavior in fruit flies using electrical signal data. It detects feeding and tasting bouts, generates quality-control reports, and produces publication-ready plots and summary tables.

The main objects in pyflic map to the physical hardware:

- A **DFM** (Data File Module) is one physical FLIC device, reading up to 12 wells.
- A **chamber** is a group of wells (1 or 2) within a DFM assigned to one experimental treatment.
- An **experiment** is a collection of DFMs governed by a shared configuration.

---

## 2. Project directory layout

pyflic expects one directory per experiment with the following structure:

```
project_dir/
  flic_config.yaml        ← required; defines experiment structure and parameters
  data/                   ← DFM CSV files (one per DFM, named by device ID)
  qc/                     ← written by pyflic after running QC (do not create manually)
  analysis/               ← written by pyflic after running analysis (do not create manually)
```

---

## 3. Configuration file (`flic_config.yaml`)

The YAML config is the entry point for every experiment. It defines the experiment type, algorithm parameters, and how chambers are assigned to treatments. The easiest way to create one is with the `pyflic-config` GUI (see [Command-line tools](#4-command-line-tools)).

### Top-level structure

```yaml
global:
  experiment_type: ...
  constants: { ... }
  params: { ... }
  experimental_design_factors: { ... }   # optional
  well_names: { ... }                    # optional

dfms:
  1:
    params: { ... }
    chambers:
      1: TreatmentA
      2: TreatmentB
  2:
    ...

scripts:                                 # optional — see Section 4
  - name: "My Pipeline"
    steps:
      - action: load
      - action: basic_analysis
```

---

### `global.experiment_type`

Determines which analysis class is loaded. If omitted, pyflic selects automatically based on `chamber_size`.

| Value | Class | Use when |
|---|---|---|
| `single_well` | `SingleWellExperiment` | 12 independent wells per DFM |
| `two_well` | `TwoWellExperiment` | Two-well choice experiments |
| `hedonic` | `HedonicFeedingExperiment` | Two-well with hedonic/reward-based analysis |
| `progressive_ratio` | `ProgressiveRatioExperiment` | Progressive-ratio schedules |

---

### `global.constants`

Hard limits used during data validation. Chambers that exceed these thresholds are flagged or excluded.

| Key | Default | Description |
|---|---|---|
| `min_untransformed_licks_cutoff` | *(unset)* | Minimum non-transformed lick count; chambers where at least one well is below this are excluded by `auto_remove_chambers()` |
| `max_med_duration_cutoff` | `13` | Maximum median bout duration (seconds); chambers above are flagged |
| `max_events_cutoff` | `150000` | Maximum number of raw events; chambers above are flagged |

---

### `global.params`

Algorithm parameters used for bout detection. These are global defaults; any DFM-level `params` block overrides them for that device only.

**Timing**

| Key | Default | Description |
|---|---|---|
| `baseline_window_minutes` | `3` | Duration (minutes) of the rolling window used to compute baseline signal |
| `samples_per_second` | `5` | Hardware sampling rate in Hz |

**Feeding detection**

| Key | Default | Description |
|---|---|---|
| `feeding_threshold` | `10` | Signal rate threshold (counts/s) above which a sample is considered feeding |
| `feeding_minimum` | `10` | Minimum duration (seconds) for a detected bout to be counted as feeding |
| `feeding_minevents` | `1` | Minimum number of raw events within a bout window |
| `feeding_event_link_gap` | `5` | Maximum gap (in samples) between events that can be bridged into one bout (~1 s at 5 Hz) |

**Tasting detection**

| Key | Default | Description |
|---|---|---|
| `tasting_minimum` | `0` | Minimum duration (seconds) for a taste bout |
| `tasting_maximum` | `10` | Maximum duration (seconds); contacts longer than this are not counted as tasting |
| `tasting_minevents` | `1` | Minimum raw events per taste bout |

**Hardware / experiment design**

| Key | Required | Description |
|---|---|---|
| `chamber_size` | Yes | Wells per chamber: `1` (single-well) or `2` (two-well choice) |
| `pi_direction` | No | Which side is the preference-index reference: `"left"` or `"right"` |
| `correct_for_dual_feeding` | No | If `true`, corrects simultaneous licks in two-well experiments |

> Many parameter names have accepted aliases (e.g. `baseline_window` is equivalent to `baseline_window_minutes`, `link_gap` to `feeding_event_link_gap`). The config editor handles these automatically.

---

### `global.experimental_design_factors` (optional)

Defines a factorial experimental design. Each key is a factor name; its value is the list of levels. When factors are defined, chamber assignments in `dfms` must be written as comma-separated factor levels in the same order as the factors are listed here.

```yaml
experimental_design_factors:
  paired: [Paired, Unpaired]
  genotype: [Chrim, WCS]
```

With this definition a chamber assigned `"Paired,Chrim"` will be tagged with `paired=Paired` and `genotype=Chrim`.

---

### `global.well_names` (optional)

Human-readable labels for the wells within each chamber, used in plots and reports.

```yaml
# Two-well (chamber_size: 2)
well_names:
  A: Sucrose
  B: Yeast

# Single-well (chamber_size: 1)
well_names:
  1: Water
  2: 10 mM Sucrose
```

---

### `dfms`

One entry per physical DFM device. The key (or `id` field) matches the device number used in the CSV filenames.

```yaml
dfms:
  1:
    params:
      pi_direction: left      # override global param for this DFM only
    chambers:
      1: Paired,WCS           # chamber 1 → Paired genotype WCS
      2: Unpaired,WCS         # chamber 2 → Unpaired genotype WCS
  2:
    params: {}                # no overrides; inherits all global params
    chambers:
      1: Unpaired,Chrim
      2: Paired,Chrim
```

- The `params` block accepts the same keys as `global.params` and takes precedence over global defaults for that DFM.
- The `chambers` block maps chamber index to treatment name (or comma-separated factor levels if `experimental_design_factors` is defined).

---

### Complete example

```yaml
global:
  experiment_type: hedonic
  constants:
    min_untransformed_licks_cutoff: 20
    max_med_duration_cutoff: 13
    max_events_cutoff: 150000
  params:
    chamber_size: 2
    pi_direction: left
    baseline_window_minutes: 3
    samples_per_second: 5
    feeding_threshold: 10
    feeding_minimum: 10
    feeding_minevents: 1
    feeding_event_link_gap: 5
    tasting_minimum: 0
    tasting_maximum: 10
    tasting_minevents: 1
    correct_for_dual_feeding: true
  experimental_design_factors:
    paired: [Paired, Unpaired]
    genotype: [Chrim, WCS]
  well_names:
    A: Sucrose
    B: Yeast

dfms:
  1:
    params:
      pi_direction: left
    chambers:
      1: Paired,WCS
      2: Unpaired,WCS
  2:
    params:
      pi_direction: right
    chambers:
      1: Unpaired,Chrim
      2: Paired,Chrim
```

---

## 4. Scripts — automated hub pipelines (`scripts:`)

The optional `scripts:` key in `flic_config.yaml` lets you define named analysis pipelines that run in a single click from the **pyflic-hub** GUI. When at least one script is defined, a dropdown and **Run Script** button appear in the Load group of the hub.

### Structure

```yaml
scripts:
  - name: "Standard Analysis"       # label shown in the hub dropdown
    start: 0                        # optional — default start minute for all steps
    end: 0                          # optional — 0 means end of recording
    steps:
      - action: load
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

  - name: "Quick Plots"
    steps:
      - action: load
      - action: plot_feeding_summary
      - action: plot_dot
        metric: Licks
      - action: plot_dot
        metric: PI
```

Each script is a named list of **steps**. Every step has an `action:` key plus optional parameters. Steps execute in order; they all share the experiment loaded by the first `load` step (or auto-loaded on first use if no `load` step appears).

---

### Parameter resolution order

For each step, parameter values are resolved in this order:

1. **Per-step value** — set directly on the step (e.g. `binsize: 30`)
2. **Script-level default** — `start:` / `end:` set at the script level
3. **UI value** — the spinbox / control value currently shown in the hub

---

### Supported actions

| `action:` | Parameters | Experiment type |
|---|---|---|
| `load` | `start`, `end`, `parallel` | all |
| `basic_analysis` | `start`, `end` | all |
| `feeding_csv` | `start`, `end` | all |
| `binned_csv` | `start`, `end`, `binsize` | all |
| `weighted_duration` | `start`, `end` | hedonic only |
| `plot_feeding_summary` | `start`, `end` | all |
| `plot_binned` | `metric`, `mode`, `binsize`, `start`, `end` | all |
| `plot_dot` | `metric`, `mode`, `start`, `end` | all |
| `plot_well_comparison` | `metric`, `start`, `end` | two-well only |
| `plot_hedonic` | `start`, `end` | hedonic only |
| `plot_breaking_point` | `config` (1–4), `start`, `end` | progressive_ratio only |

Actions that require a specific experiment type (e.g. `plot_hedonic` on a two-well experiment) are skipped with a log message rather than raising an error. Unknown action names are also skipped.

---

### `plot_binned` and `plot_dot` — `metric` and `mode`

`metric` names for **two-well** experiments:
`Licks`, `PI`, `EventPI`, `LicksA`, `LicksB`, `Events`, `MedDuration`, `MedDurationA`, `MedDurationB`, `MeanDuration`, `MedTimeBtw`

`metric` names for **single-well** experiments:
`Licks`, `Events`, `MedDuration`, `MeanDuration`, `MedTimeBtw`, `MeanInt`, `MedianInt`

`mode` is optional. When omitted, a sensible default is chosen automatically:
- Metrics ending in `A` → `A`
- Metrics ending in `B` → `B`
- Duration / interval metrics without a suffix → `mean_ab`
- `Licks`, `Events`, `PI` without a suffix → `total`

Valid `mode` values: `total`, `mean_ab`, `A`, `B`

---

### `plot_well_comparison` — `metric`

Valid `metric` names: `MedDuration`, `MeanDuration`, `Licks`, `MedTimeBtw`, `MeanTimeBtw`, `MeanInt`, `MedianInt`

---

### Example

```yaml
scripts:
  - name: "Standard Analysis"
    start: 0
    end: 0
    steps:
      - action: load
      - action: basic_analysis
      - action: feeding_csv
      - action: binned_csv
        binsize: 30
      - action: plot_feeding_summary
      - action: plot_binned
        metric: Licks
        mode: total
        binsize: 30
      - action: plot_binned
        metric: PI
      - action: plot_dot
        metric: MedDuration
      - action: plot_well_comparison
        metric: MedDuration
```

After this script runs, all CSVs and PNG files are written to the `analysis/` subdirectory and each plot opens in its own window.

---

## 5. Command-line tools

Three tools are installed with pyflic.

### `pyflic-hub`

Opens the graphical Analysis Hub (PyQt6) — the primary interactive interface for running analyses and generating plots without writing Python. Accepts an optional project directory as an argument.

```bash
pyflic-hub /path/to/project_dir
```

The hub automatically reads `flic_config.yaml` from the selected project directory and shows the appropriate controls for the experiment type. If a `scripts:` section is present in the config, a dropdown and **Run Script** button appear in the Load group (see [Section 4](#4-scripts--automated-hub-pipelines-scripts)).

### `pyflic`

Prints a summary of available commands and the Python API. Takes no arguments.

```bash
pyflic
```

### `pyflic-config`

Opens a graphical configuration editor (PyQt6) for creating and editing `flic_config.yaml`. Automatically loads an existing config if one is present in the current directory.

```bash
pyflic-config
```

Use this before running any analysis to set up experiment structure, chamber assignments, and parameter values without editing YAML by hand.

### `pyflic-qc`

Opens an interactive QC viewer (PyQt6) for a project that has already had QC reports computed. Displays one tab per DFM with:

- **Integrity report** — per-chamber validation results
- **Data breaks** — detected time gaps in the raw signal
- **Simultaneous feeding matrix** — which wells are licked at the same time (two-well only)
- **Bleeding check** — cross-well signal contamination
- **Signal plots** — raw, baselined, and cumulative lick plots

```bash
pyflic-qc /path/to/project_dir
```

> QC reports must be computed first (via `exp.write_qc_reports()` in Python or `execute_basic_analysis()`). The viewer reads pre-computed files from `project_dir/qc/` and does not reload raw data.

---

## 6. Python API

### Loading an experiment

```python
from pyflic import load_experiment_yaml

exp = load_experiment_yaml(
    "/path/to/project_dir",
    range_minutes=(0, 0),   # (start, end) in minutes; (0, 0) means the full recording
    parallel=True,           # load DFMs concurrently
)
```

`load_experiment_yaml` reads `flic_config.yaml` and returns the appropriate subclass (`SingleWellExperiment`, `TwoWellExperiment`, `HedonicFeedingExperiment`, or `ProgressiveRatioExperiment`).

You can also load a specific subclass explicitly:

```python
from pyflic import HedonicFeedingExperiment
exp = HedonicFeedingExperiment.load("/path/to/project_dir")
```

---

### Experiment class hierarchy

```
Experiment (base)
├── SingleWellExperiment        # chamber_size=1; 12 independent wells per DFM
└── TwoWellExperiment           # chamber_size=2; two-well choice
    ├── HedonicFeedingExperiment
    └── ProgressiveRatioExperiment
```

All subclasses share the same core API. Specialized methods (breakpoint analysis, hedonic metrics) are added in the subclasses.

---

### Key methods

**Accessing data**

```python
exp.dfms                        # dict of DFM objects keyed by DFM ID
dfm = exp.get_dfm(1)            # get a single DFM
exp.design                      # ExperimentDesign (structure, treatments, factor levels)
```

**Running QC**

```python
# Compute and write QC reports to project_dir/qc/
exp.write_qc_reports()

# Or just get results as Python dicts without writing files
results = exp.compute_qc_results()
```

**Feeding summary**

```python
# Full-experiment feeding summary (returns a DataFrame)
df = exp.feeding_summary()
# Columns: Chamber, Treatment, DFM, Licks, Events, MeanDuration, MedDuration, ...

# Restrict to a time window
df = exp.feeding_summary(range_minutes=(30, 90))

# Time-binned summary (30-minute bins)
binned = exp.binned_feeding_summary(binsize_min=30)
# Extra columns: Interval, Minutes (bin midpoint)
```

**Plotting**

```python
# Faceted jitter + boxplot for all feeding metrics grouped by treatment
fig = exp.plot_feeding_summary()
exp.write_feeding_summary_plot()           # saves to project_dir/analysis/

# Cumulative licks for one chamber
fig = exp.plot_cumulative_licks_chamber(dfm_id=1, chamber=1)

# Binned time-series metrics
fig = exp.plot_binned_metric_by_treatment(binned, metric="Licks")
fig = exp.plot_binned_licks_by_treatment(binned)
```

**Full pipeline in one call**

```python
results = exp.execute_basic_analysis()
# Runs: write_qc_reports → write_summary → write_feeding_summary → write_feeding_summary_plot
# Returns a dict with paths to all output files
```

**Text summary**

```python
print(exp.summary_text())          # prints to console
exp.write_summary()                # saves to project_dir/analysis/summary.txt
```

---

### DFM objects

Individual DFM objects expose the raw and processed data:

```python
dfm = exp.get_dfm(1)

dfm.raw_df                         # raw CSV as a DataFrame
dfm.baseline_df                    # baseline-subtracted signal
dfm.feeding_summary()              # per-chamber feeding metrics for this DFM

dfm.plot_raw()                     # raw signal plot
dfm.plot_baselined()               # baseline-subtracted signal plot
dfm.plot_cumulative_licks()        # cumulative lick count plot
```

---

## 7. Typical workflows

### Workflow A — One-click analysis with a script

The fastest path once your config is set up:

1. Add a `scripts:` section to `flic_config.yaml` (see [Section 4](#4-scripts--automated-hub-pipelines-scripts)).
2. Open the hub:
   ```bash
   pyflic-hub /path/to/project_dir
   ```
3. Select the script from the dropdown in the **Load** group.
4. Click **Run Script** — the hub loads the experiment, runs all analysis steps, writes outputs to `analysis/`, and opens each plot in its own window.

---

### Workflow B — Full analysis from scratch

```bash
# 1. Create the config file with the GUI
pyflic-config

# 2. Run analysis in Python (or in a Jupyter notebook)
```

```python
from pyflic import load_experiment_yaml

exp = load_experiment_yaml("/path/to/project_dir")
exp.execute_basic_analysis()
```

```bash
# 3. Inspect QC results interactively
pyflic-qc /path/to/project_dir
```

---

### Workflow C — Custom analysis in a notebook

```python
from pyflic import load_experiment_yaml

exp = load_experiment_yaml("/path/to/project_dir")

# Explore structure
print(exp.summary_text())

# Get feeding metrics
df = exp.feeding_summary()
display(df)

# Filter to a treatment group
sucrose = df[df["Treatment"].str.contains("Sucrose")]

# Custom jitter plot
fig = exp.plot_jitter_summary(sucrose, x_col="Treatment", y_col="Licks")
fig.show()

# Time-binned analysis (60-minute bins, first 4 hours)
binned = exp.binned_feeding_summary(binsize_min=60)
fig = exp.plot_binned_licks_by_treatment(binned)
```

---

### Workflow D — QC only

If you want to inspect data quality before running a full analysis:

```python
exp = load_experiment_yaml("/path/to/project_dir")
exp.write_qc_reports()
```

```bash
pyflic-qc /path/to/project_dir
```

---

## 8. Jupyter notebooks

The `doc/` directory contains a series of tutorial notebooks. Work through them in order for a complete introduction, or jump to the one that matches your experiment type.

### `doc/01_GettingStarted.ipynb`

**Start here.** Covers:
- The Experiment class hierarchy and when to use each subclass
- Loading an experiment from a project directory
- Accessing DFMs and printing experiment summaries
- Basic CLI tool overview

### `doc/02_GroupedAnalysis.ipynb`

Covers analysis grouped by treatment and factor levels:
- Inspecting and filtering the feeding summary DataFrame
- Grouping results by experimental factors
- Customizing and exporting summary tables

### `doc/03_ChoiceChamberAnalysis.ipynb`

For **two-well choice experiments**:
- Well-by-well metrics (preference index, simultaneous feeding)
- Two-well specific QC (bleeding check, simultaneous feeding matrix)
- Plotting utilities for choice behavior

### `doc/HedonicFeeding.ipynb`

For **hedonic feeding experiments**:
- Multi-level factorial designs (e.g., concentration × genotype)
- Hedonic-specific QC and filtering
- Weighted duration summaries and specialized plots
- End-to-end example with a real dataset

### `doc/ProgressiveRatio.ipynb`

For **progressive-ratio experiments**:
- Breakpoint detection and analysis
- Time-series and transition visualization
- Schedule-specific parameter recommendations

---

The `notebooks/` directory contains additional working examples:

- **`notebooks/load_experiment.ipynb`** — detailed walkthrough of loading a project directory, inspecting raw DFM objects, and manually overriding parameters
- **`notebooks/run_flic_config_6h.ipynb`** — complete 6-hour experiment pipeline: config setup → QC → full analysis → advanced plotting
