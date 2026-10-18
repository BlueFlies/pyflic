# Experiment Type Editor

Where a lab builds its own [Experiment Types](concepts-experiment-types.md): the assays it
runs, each defined once and then chosen in any Project's design.

```bash
pyflic-types
```

It also opens from the Hub's **Tools** panel (**Experiment type editor**), and from **New
type…** beside the Experiment Type list of the Project design editor and the Config Editor.
Closing it refreshes those lists, so a type you have just saved can be chosen at once.
**F1** opens this topic, and every card carries a `?` for its own section.

## The list of types

On the left, every type you can use: the three that ship with pyflic (Custom, Hedonic,
Progressive Ratio), then your lab's. A shipped type opens **read-only**; to change one,
start a type of your own from it. A file in the library that cannot be used is counted
under the list, with the reasons in its tooltip.

The buttons in the top bar:

- **New** starts an empty type.
- **New from…** copies the type on screen, shipped or not, under a name you give it.
  Nothing links the two afterwards.
- **Save to library** writes the type to the lab's type library. Renaming a type saves
  it under the new name and leaves the old one; delete the old one if it is no longer
  wanted.
- **Delete** removes a lab type from the library. Projects that carry a copy of it keep
  analysing with their copy.

Leaving a type with unsaved changes, by opening another or starting a new one, asks first.

## The lab library

The **Lab library** card, under the list, shows the folder the lab's types are kept in, with
**Change folder…** to choose another. Point it at a shared drive and everyone in the lab
builds on the same types. The choice is remembered in your pyflic settings; the
`PYFLIC_TYPE_LIBRARY` environment variable, when set, wins over it.

## What a type states

The form follows the definition, top to bottom, one card each.

### Type

- **Name** — what `experiment_type:` holds: letters, digits and underscores, starting with
  a letter, never a shipped type's name. Names that differ only in case, spaces, hyphens or
  underscores count as the same.
- **Display name** — how menus and the report cover say it.
- **Description** — the paragraph the report cover shows: what the assay is and how to
  read it.

### Layout, wells and factors

- **Chamber layout** — single-well, two-well, or either (the config then states it).
- **Wells named** — Well A and Well B, ticked when every config of the type must name
  them.
- **Factor names** — the design factors every Design of the type declares, comma
  separated; each Design gives their levels.

### Light

What the Opto Program may run: **No light**, **Any light or none**, or **These Paradigm
types:** with one box per Paradigm type. OpenLoop and dark intervals are always allowed
beside a set of Paradigm types. A recording whose program runs anything else fails to
load. See [The light a type expects](concepts-experiment-types.md#the-light-a-type-expects).

### Analysis Modules

One checkbox per module, with what it adds under it. Each module states what it needs,
and the problems list says when a choice cannot run. See
[Analysis Modules](concepts-experiment-types.md#analysis-modules).

### Control comparisons

What the report leads with: a **Role comparison** (one Role against another) and a
**Treatment control** (one of the type's factors, whose control level each Design names).
Both are optional; with both, the Role comparison comes first. See
[Control comparisons](concepts-experiment-types.md#control-comparisons).

### Plots

- The **built-in figures** the type's report draws, after its modules' own, ticked from a
  list. A figure the layout cannot draw is skipped.
- **Plot Specs of its own** — labels, colours and order made in the
  [Plot Editor](app-plot-editor.md), copied from a Project's `plot_specs.yaml` with
  **Import from a Project…** (and **Remove** to drop one). A new Project of this type
  starts with them.

### Facets

The default facet **Cutoffs** (minutes) and their **Names**. Tick **Fixed** and a config
may not change them. A module whose Facets come from the data, such as the Progressive
Ratio module, overrides them. See [Facets](concepts-facets.md).

### Default constants

Defaults for each config's `constants:` block, one row each (**Add**, **Remove**), such as
the auto-removal cutoffs. A config's own value wins.

## Problems

Below the form, a list of what stops the type from running: a module whose needs the type
does not meet, two modules that exclude each other, a Treatment control naming a factor the
type does not have, a Role comparison on a type that expects no light, a shipped type's
name. **Save to library** stays off while the list has anything in it.

## The copy beside the data

Saving a Project design (or a standalone config) whose type is one of your lab's writes the
type beside it as `experiment_type.yaml`, so the data analyses the same on any machine.
Choosing a shipped type later removes that copy. When the library's version of the type
changes, the Project design editor and the Hub's Project panel say that the copy differs
and offer to update it.

---

Related: [Experiment types and chamber layouts](concepts-experiment-types.md) ·
[Project design](concepts-project.md) · [Config Editor](app-config-editor.md)
