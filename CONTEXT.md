# pyflic

A toolkit for analysing FLIC (Fly Liquid-food Interaction Counter) feeding-behaviour experiments. Configures, loads, and visualises chamber-level lick/feeding data driven by per-experiment YAML configs.

## Language

**Project directory**:
A directory holding a single experiment: configuration YAML(s), a `data/` folder with raw DFM CSVs, and the analysis outputs pyflic writes (`analysis/`, `plots/`, `qc/`).
_Avoid_: project, folder, dataset directory.

**Active config**:
The single YAML file (default `flic_config.yaml`) currently driving the hub UI for one project.
_Avoid_: config, settings, yaml.

**Script**:
A named recipe inside a YAML's `scripts:` section — a list of pipeline `steps` (load, basic_analysis, plot_*, etc.) bound under one name and triggered from the hub's "Run Script" button.
_Avoid_: pipeline, recipe, job.

**Batch target**:
A directory at any depth under the chosen root that contains at least one YAML defining a script named `batch`. A run of subdir-batch mode executes that `batch` script once per target.
_Avoid_: subdir, subdirectory, project (when discussing batch).

**Subdir-batch mode**:
The hub mode (toggled by the "Run 'batch' script in every directory under here" checkbox) that walks the tree under the chosen root and runs the `batch` script in each batch target it finds.
_Avoid_: batch mode (ambiguous — see "yaml-batch mode"), subdir mode.

**YAML-batch mode**:
The separate hub mode that runs a chosen script across every YAML in a single project directory, writing into per-yaml output subfolders.
_Avoid_: batch mode.

## Relationships

- A **Project directory** holds one or more **Active configs** and zero or more **Scripts** per config.
- A **Batch target** is a **Project directory** that has a **Script** named `batch` in at least one of its YAMLs.
- **Subdir-batch mode** runs across many **Batch targets**; **yaml-batch mode** runs across many configs in one project.

## Example dialogue

> **Dev:** "When subdir-batch is on, does the *root* directory itself count?"
> **Domain expert:** "Yes — if the root contains a YAML with a `batch` script, it's a **batch target** like any other. The recursion includes the root."
>
> **Dev:** "What about a folder that has YAMLs but none with `batch`?"
> **Domain expert:** "Not a **batch target**. Skipped, but logged as a near-miss so the user notices if they forgot to add the script."

## Flagged ambiguities

- "subdirectory" historically meant both *one level down* and *a thing batch runs on*. Resolved: the second meaning is now **batch target**, decoupled from depth.
- "batch" alone is ambiguous between **subdir-batch mode** and **yaml-batch mode**. Always qualify.
