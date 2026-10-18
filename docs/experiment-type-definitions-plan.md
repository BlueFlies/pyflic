# Experiment Type definitions: the build plan

ADR-0019 decides that an Experiment Type is a definition a lab builds from
Analysis Modules. This plan turns that into code. The terms are in
`CONTEXT.md`: *Experiment Type*, *Analysis Module*, *Control Comparison* and
*Experiment Type Editor*. Branch: `experiment-type-definitions`, from
`v4_Dev`.

The scope is ADR-0019's decisions and nothing else. Behaviour outside them
stays as it is, apart from the one fix the ADR names: the two-well cutoffs.

## The core (done first, on the branch)

- **The definition.** `experiment_types/definition.py` holds
  `TypeDefinition`, `parse_definition`, `read_definition`,
  `definition_problems`, `dump_definition` and `write_definition`. The yaml
  keys are listed in the module docstring. `light:` is `none`, `any`, or a
  list of Paradigm types in PyMCU's spelling. `chamber_layout:` is
  `single_well`, `two_well` or `either`.
- **The modules.** `analysis_modules/` holds `ratio`, `hedonic`, `yoked` and
  `light_dark`. Each states what it needs (`needs_layout`, `needs_light`,
  `needs_paradigms`), what it excludes (`conflicts`), its `experiment_class`,
  its `default_constants`, its Plot Specs (`plots`) and its outputs. Ratio
  carries the code that was `ProgressiveRatioExperimentType`.
- **The type.** `ExperimentType(definition)` takes every attribute from the
  definition and its modules, and keeps the interface every caller used.
  The new members are:
  - `modules`, `module_ids` and `has_module(id)`;
  - `light` and `light_problems(program, dfm_ids)`;
  - `layout_free`, `is_shipped` and `resolved_from`;
  - `control_level(global_cfg)` and `plot_specs()`.

  `is_custom` now means the type is named Custom. `layout_free` means the
  config states the layout.
- **The shipped types.** They are the yaml files in
  `experiment_types/shipped/`. Each reproduces what its class did, and adds
  the two ADR changes: Hedonic expects no light, and ProgressiveRatio
  expects ProgressiveRatio or FixedRatio.
- **Where definitions live.** `experiment_types/library.py` reads shipped
  types, the copy `experiment_type.yaml` beside `project.yaml` or a
  standalone `flic_config.yaml`, and the lab library. The library's folder
  is `type_library` in `~/.config/pyflic/ui.json`, or the
  `PYFLIC_TYPE_LIBRARY` environment variable. Its other functions are
  `save_to_library`, `write_copy`, `copy_drift` and `resolve`. Names compare
  without case, spaces, hyphens or underscores, and a lab type may not take
  a shipped name.
- **Resolution.** `get_experiment_type(name, where)` reads a lab type from
  the copy at *where* first, then from the library.
  `available_experiment_types(where)` lists the shipped types, then the
  library's, then the copy.
- **The light check.** `load_experiment_yaml` fails when the Opto Program
  runs a Paradigm type the type does not expect. OpenLoop wells and dark
  intervals are always allowed beside a set of expected types, and an
  all-`Off` interval runs nothing. A type read from the library, not from a
  copy, prints a note.
- **Re-keying on modules.**
  - Plots: `PLOT_TYPES[...]["module"]`, `plot_allowed` and
    `plots_for_layout`, which take a type or module ids.
  - Selection items: `requires` names a module id, or a tuple of
    requirements that must all be met.
  - The Script Editor: `capabilities_for(global_cfg, where)` gives
    `two_well` plus the module ids. This fixes `two_well` never being
    offered.
  - The reports: the paired and yoked blocks and the light and dark figure
    show only under their modules.
  - The Config Editor's Progressive Ratio widgets follow the `ratio`
    module.
- **The two-well cutoffs.** `TwoWellExperiment.auto_remove_chambers`
  applies `max_med_duration_cutoff` and `max_events_cutoff` to every
  two-well type. Hedonic loses its copy of the filter, and Progressive Ratio
  calls the shared helper.

## Stream C: Control Comparisons

A type's `control:` block declares a Role comparison (`roles: [A, B]`), a
Treatment control (`treatment: <factor>`), or both. The Design names the
control level as `global.control_level`. `ExperimentType.validate` already
checks the factor and the level.

- **Role comparison.**
  - `Paired` against `Yoked` is the paired−yoked comparison that already
    exists: `analytics.yoked_comparison` and `yoked_report`, or the Ratio
    module's Paired-Yoked Difference. Reuse it; do not recompute it.
    `definition_problems` should require the `yoked` or `ratio` module for
    that pair.
  - Any other pair compares per-chamber metrics between chambers of the two
    Roles. It uses the feeding summary's `Role` column, Welch's t within
    each Treatment and Facet, and the metrics `analytics.YOKED_METRICS` uses.
    That comparison is new code in `pyflic/base/control_comparisons.py`.
- **Treatment control.** Each level of the control factor is compared with
  the control level, with the other factors held at the same levels, per
  metric and Facet. Use `scipy.stats.dunnett`, which scipy 1.14 has, with
  the control as the reference.
- **The reports lead with them.**
  - In the experiment report, the blocks go first under *Results*, before
    the generic results (`pdf_report.py`, right after the Results heading).
  - In the Project Report, they go first in `_results_blocks`.
  - The trailing `_yoked_blocks` call must not repeat a Paired-vs-Yoked
    comparison that already leads.
  - Without a `control:` block, the reports are unchanged.
- **Tests.** Cover a lab type with each kind and with both, using the
  fixtures in `tests/opto_fixtures.py` and `tests/v4_fixtures.py`.

## Stream D: the Experiment Type Editor and the copy

- **The editor.** `pyflic/base/type_editor.py`: a PyQt6 `QMainWindow`
  called `ExperimentTypeEditor`, with `open_type_editor(parent=None,
  name=None)`. It edits a `TypeDefinition`:
  - name, display name and description;
  - layout and light;
  - required wells and factors;
  - modules, shown as checkboxes, each with its summary;
  - the control comparisons;
  - the plots picked from `pubfigures.PLOT_TYPES`, and its own Plot Specs,
    imported from a Project's `plot_specs.yaml`;
  - facets and constants.

  It also needs to:
  - show `definition_problems` live, and refuse to save while any remain;
  - list the shipped and library types; a shipped type opens read-only;
  - offer *New*, *New from…* (`TypeDefinition.with_name`), *Save to
    library* and *Delete*;
  - show the library folder and let the user change it
    (`library.set_library_dir`).
- **Where it opens.** From the Hub's Tools panel, and from a *New type…*
  entry beside the type combo in the Design editor and the Config Editor.
  Those combos list `available_experiment_types(where)`.
- **The copy.** When the Design editor saves a Project whose type is a lab
  type, it writes `experiment_type.yaml` beside `project.yaml`
  (`library.write_copy`). The Config Editor does the same beside a
  standalone `flic_config.yaml`. Choosing a shipped type removes a stale
  copy. A new Project of a type with Plot Specs of its own starts with them
  in its `plot_specs.yaml`.
- **Drift.** When `library.copy_drift(dir)` says the copy and the library
  differ, the Design editor and the Hub's Project panel say so and offer to
  update the copy.
- **Tests.** Write them in the `tests/test_*_ui.py` style, with an offscreen
  QApplication.

## Stream E: lint and migration

- `pyflic lint` reports `light_problems`. A Hedonic config whose program
  lights a well gets the hint to build a type for that light. Lint also
  reports a lab type with no copy beside the data, a copy that differs from
  the library, and library files that cannot be used.
- `migration_lint` skips `experiment_type.yaml`, in the same way it skips
  `project.yaml`.

## Stream F: the record

- The help topics: `concepts-experiment-types` (the definitions, the
  modules, light, controls, where they live), and a new
  `app-type-editor` topic, listed in `help/toc.py`.
- `docs/GETTING_STARTED.md`'s *Which Experiment Type?* table.
- `CHANGELOG.md`, with an entry under *Unreleased*.
- `MIRRORED.md`: under *Not mirrored — deliberate divergences*, this change
  originates in pyflic, and the siblings are not planned.

## Gate

`pytest tests -q -p no:cacheprovider`: everything passes apart from the
8 failures that existed before.
