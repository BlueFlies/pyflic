---
status: accepted
---

# Experiment Types are definitions a lab builds, not classes

pyflic shipped three Experiment Types as code: Custom, Hedonic and
ProgressiveRatio. A lab runs more designs than that. Each one combines a
light (none, or one of six Paradigm types), a layout (one well or two), a
control (paired and yoked chambers, an unlit or open-loop DFM, a control
genotype) and a set of analyses and plots. We first tried a class tree rooted
in the Paradigm types, with Hedonic under ClosedLoop and the ratio types
under a fixed-length group. Hedonic alone needed three light variants with
three different parents, and the controls and layouts multiplied the rest.
So an Experiment Type becomes a definition: data that combines analyses
pyflic provides. The terms are in `CONTEXT.md` (*Experiment Type*,
*Analysis Module*, *Control Comparison*, *Experiment Type Editor*).

## Decisions

- **A type is a reusable definition of an assay's shape.** It states:
  - the Chamber Layout: single-well, two-well, or either;
  - the light it expects: none, any, or a set of Paradigm types;
  - its Control Comparisons: a Role pair (Paired vs Yoked, lit vs Unlit,
    closed loop vs Open), a Treatment control, or both, with the Role pair
    first;
  - its Experimental Design Factor names;
  - its Analysis Modules;
  - the built-in plots it picks, and Plot Specs of its own;
  - default `constants:`, facets, required well names and the report intro.

  The Design names the type and supplies what changes from study to study:
  the factor levels (including which level is the control), the well names
  and the detection `params:`. A Design may add factors beyond the type's.
- **A type combines analyses; it never creates one.** Each Analysis Module is
  code: the Hedonic durations, the Ratio analysis (Training, Test, breaking
  point, Sucrose Persistence), the paired−yoked difference, and feeding in
  light and dark. Each module states what it needs, and a type that cannot
  meet that cannot include it. A new analysis takes code, and then appears in
  the editor.
- **The config names the type, and the Opto Program is checked against it.**
  A mismatch fails to load and names the Paradigms found. OpenLoop light (a
  whole DFM, or wells set `On`) and dark Program Intervals may run beside a
  type that expects a set of Paradigm types, as controls. Nothing may run
  beside a type that expects no light. Custom accepts any light or none.
- **The light is still judged by the Paradigms present; ADR-0017 stands.** A
  type says what light it expects; it never changes how a Paradigm is
  checked. An OpenLoop control DFM in a ClosedLoop experiment is judged as
  open loop, and Acclimation as closed loop.
- **Types are flat.** No type is built on another. *New from…* copies any
  type as a starting point, so editing one type never changes another's
  results.
- **Custom, Hedonic and ProgressiveRatio ship as read-only definitions.**
  They use the same mechanism as a lab's types, and existing configs keep
  their names. Hedonic expects no light. ProgressiveRatio expects
  ProgressiveRatio or FixedRatio, so FixedRatio programs analysed today need
  no change. `pyflic lint` points a Hedonic config whose recording is lit to
  a type built for that light.
- **The data carries its type.** A lab type is copied to
  `experiment_type.yaml`, beside `project.yaml` or beside a standalone
  `flic_config.yaml`, so the data analyses the same on any machine. The lab
  library is a folder set in pyflic's settings: the user's app-data folder by
  default, or a shared drive. pyflic flags a copy that differs from the
  library's and offers to update it. Shipped types are referenced by name,
  and names are unique across shipped and lab types.
- **The type decides what is offered; the Selection decides what runs.** The
  QC, Analysis and Plot Sets (ADR-0018) offer the items of the type's
  modules, the built-in plots it picks and its own Plot Specs. A Project's
  `global.omit:` leaves items out of that offer.
- **The Experiment Type Editor builds types.** It opens from the Hub, and
  from *New type…* wherever a type is chosen (the Design editor, the Config
  Editor). A shipped type opens read-only.
- **pyflic goes first.** PyTrackingAnalysis keeps its types in code (its
  ADR-0001). MIRRORED.md records this change as originating in pyflic, with
  the sibling apps not planned.

## Considered options

- **A class tree rooted in the Paradigm types**: ClosedLoop over
  Hedonic_Closed, and fixed length over FixedInterval and over Ratio, which
  holds FixedRatio and ProgressiveRatio. Rejected. Hedonic needed a no-light,
  an open-loop and a closed-loop variant with three parents. Every control
  and layout multiplied the classes, and each combination a lab wanted needed
  a new release.
- **Add the missing fields to the Design.** Rejected. A Design belongs to one
  Project, and an assay repeats across Projects whose treatments differ.
- **Definitions that build on a base.** Rejected. The reason to inherit was
  to get a parent's light QC, and the program decides that anyway. Editing a
  base would silently change every type built on it, and the base would have
  to travel with the data too.
- **Refer to a shared library by name, without a copy.** Rejected. A machine
  without the library could not analyse the Project.
- **Let the type decide how the light is judged.** Rejected, as in ADR-0017.
  One program can run several Paradigm types, and a control DFM must be
  judged by its own rule.

## Consequences

- ADR-0007's split stands: the layout is the shape of the data and the type
  is the assay. What changes is that the type is data rather than a strategy
  class in code.
- Everything that branches on a type's name branches on its modules instead.
  That includes the Script Editor's `requires`, the Hub's groups,
  `pubfigures`, `project.py` and `opto_light.py`. ADR-0018's per-type groups
  (Progressive Ratio, Hedonic) become one group per module.
- The MedDuration and Events cutoffs move to the two-well layout, so every
  two-well type applies them. Today Hedonic and ProgressiveRatio each
  implement them, and Custom two-well ignores them although the Config Editor
  shows them.
