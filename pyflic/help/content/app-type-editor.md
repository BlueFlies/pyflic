# Experiment Type Editor

Where a lab builds its own [Experiment Types](concepts-experiment-types.md): the assays it
runs, each defined once and then chosen in any Project's design.

```bash
pyflic-types
```

It also opens from the Hub's **Tools** panel, and from **New type…** beside the Experiment
Type list of the Project design editor and the Config Editor. Closing it refreshes those
lists, so a type you have just saved can be chosen at once.

## The list of types

On the left, every type you can use: the three that ship with pyflic (Custom, Hedonic,
Progressive Ratio), then your lab's. A shipped type opens **read-only**; to change one,
start a type of your own from it.

- **New** starts an empty type.
- **New from…** copies the selected type, shipped or not, under a new name.
- **Save to library** writes the type to the lab's type library. Renaming a type saves
  it under the new name and leaves the old one; delete the old one if it is no longer
  wanted.
- **Delete** removes a lab type from the library. Projects that carry a copy of it keep
  analysing with their copy.

The library's folder is shown under the list, with a button to change it. Point it at a
shared drive and everyone in the lab builds on the same types.

## What a type states

The form follows the definition, top to bottom:

| Part | What you choose |
|---|---|
| **Name** | What `experiment_type:` holds: letters, digits and underscores, starting with a letter, never a shipped type's name. Beside it, the display name and the sentence the report cover shows |
| **Layout** | Single-well, two-well, or either (the config then states it) |
| **Light** | None, any, or the Paradigm types the program may run; OpenLoop and dark intervals are always allowed beside a list |
| **Wells and factors** | The wells that must be named, and the factor names every Design of the type declares |
| **Analysis Modules** | One checkbox per module, with what it adds |
| **Control comparisons** | A Role comparison (two Roles) and a Treatment control (one of the factors) |
| **Plots** | The built-in Plot Specs the report shows, and Plot Specs of the type's own, imported from a Project's Plot Editor settings |
| **Facets and constants** | Default facet cutoffs and names, and default quality cutoffs |

## Problems

Below the form, a list of what stops the type from running: a module whose needs the type
does not meet, two modules that exclude each other, a Treatment control naming a factor the
type does not have, a Role comparison on a type that expects no light. **Save** stays off
while the list has anything in it.

## The copy beside the data

Saving a Project design (or a standalone config) whose type is one of your lab's writes the
type beside it as `experiment_type.yaml`, so the data analyses the same on any machine.
Choosing a shipped type later removes that copy. When the library's version of the type
changes, the Project design editor and the Hub's Project panel say that the copy differs
and offer to update it.

---

Related: [Experiment types and chamber layouts](concepts-experiment-types.md) ·
[Project design](concepts-project.md) · [Config Editor](app-config-editor.md)
