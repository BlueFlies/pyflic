"""Mapping an ``experiment_type`` name to its ``ExperimentType`` (ADR-0019).

A name resolves to a definition (:mod:`.library`): shipped, else the copy
beside the data, else the lab library.  Adding a type takes no code: build
it in the Experiment Type Editor.

Note what is *not* here: ``two_well`` and ``single_well``.  Those stopped being
experiment types — they are Chamber Layouts, one level down.  A config still
naming one of them is reported by :func:`get_experiment_type` with the
migration in the message, because a silent fallback to Custom would quietly
change which analyses run.
"""

from __future__ import annotations

from pathlib import Path

from . import library
from .base import ExperimentType

#: Values that used to be experiment types and are now Chamber Layouts.
RETIRED_AS_LAYOUT = {"two_well", "twowell", "single_well", "singlewell"}


def get_experiment_type(name, where: str | Path | None = None) -> ExperimentType:
    """Return an ExperimentType instance for *name*.

    ``None`` or blank resolves to the Custom Experiment.  *where* is the
    Experiment Directory or Project the config belongs to, whose
    ``experiment_type.yaml`` copy a lab type is read from first.  A retired
    layout name raises with the migration spelled out; any other unknown
    name raises with the known list.
    """
    if name is None or str(name).strip() == "":
        etype = ExperimentType(library.shipped_definition("Custom"))
        etype.resolved_from = "shipped"
        return etype
    if library.name_key(name) in {library.name_key(r) for r in RETIRED_AS_LAYOUT}:
        layout = "single_well" if "single" in str(name).lower() else "two_well"
        raise ValueError(
            f"experiment_type '{name}' is no longer an experiment type — it is "
            f"a chamber layout (ADR-0007). Remove the experiment_type key and "
            f"set 'chamber_layout: {layout}' under global: instead. Run "
            f"'pyflic lint' for the full migration."
        )
    definition, found = library.resolve(name, where)
    etype = ExperimentType(definition)
    etype.resolved_from = found
    return etype


def available_experiment_types(where: str | Path | None = None) -> list[ExperimentType]:
    """One instance of each type a config here can name: the shipped ones
    (Custom first), the lab library's, and the copy beside the data at
    *where* when the library lacks it.  A library file that cannot be used is
    left out (``pyflic lint`` and the editor report it)."""
    definitions = list(library.shipped_definitions())
    lab, _problems = library.library_definitions()
    definitions += sorted(lab, key=lambda d: d.name.lower())
    try:
        copy = library.read_copy(where)
    except ValueError:
        copy = None
    if copy is not None and library.name_key(copy.name) not in {
            library.name_key(d.name) for d in definitions}:
        definitions.append(copy)
    return [ExperimentType(d) for d in definitions]
