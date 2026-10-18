"""The ``AnalysisModule`` base class (ADR-0019).

An **Analysis Module** is one analysis pyflic provides that an Experiment Type
may include: its items in the QC, Analysis and Plot Sets, its Plot Specs in
the type's report, its checks of the config, its share of the report.  It
states what it needs of the type (a layout, a light) and which modules it
excludes, so the Experiment Type Editor refuses a combination that cannot
run.  Adding a module takes code; including one does not.
"""

from __future__ import annotations

from typing import Any, Mapping


class AnalysisModule:
    """Permissive base: needs nothing, adds nothing."""

    #: What a definition's ``modules:`` names, and what a Selection item's
    #: ``requires`` names.
    id: str = ""
    #: The Hub's group box and the editor's label.
    title: str = ""
    #: One sentence for the editor: what including it gives.
    summary: str = ""

    #: The Chamber Layout the module needs, or ``None``.
    needs_layout: str | None = None
    #: True when the module reads the light, so the type must expect some.
    needs_light: bool = False
    #: Paradigm types (PyMCU's spelling) of which the type must expect at
    #: least one, or ``()``.
    needs_paradigms: tuple[str, ...] = ()
    #: Modules this one cannot run beside, and why.
    conflicts: tuple[str, ...] = ()
    conflict_reason: str = ""

    #: Dotted path of the ``Experiment`` subclass that carries the module's
    #: maths, or ``None``.  A type may include one module that has one.
    experiment_class: str | None = None
    #: Wells the module needs named.
    required_wells: tuple[str, ...] = ()
    #: Defaults merged under the type's ``constants:``.
    default_constants: Mapping[str, Any] = {}
    #: Plot Spec ids the module puts first in the type's report.
    plots: tuple[str, ...] = ()
    #: Files a run of the module leaves in ``analysis/``.
    outputs: tuple[str, ...] = ()

    #: Facets the data defines (ADR-0013): the module owns the Facets, and
    #: these are their names.
    data_derived_facets: bool = False
    phase_labels: tuple[str, ...] = ()
    #: Facet labels the report figures show by default, or ``None``.
    report_facets: tuple[str, ...] | None = None

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AnalysisModule {self.id}>"

    # ---- can a type include it? ----------------------------------------

    def needs_problems(self, definition) -> list[str]:
        """Why a type defined by *definition* cannot include the module."""
        problems: list[str] = []
        label = f"module {self.id!r} ({self.title})"
        if self.needs_layout and definition.chamber_layout != self.needs_layout:
            problems.append(f"{label} needs chamber_layout {self.needs_layout}, "
                            f"and the type's is {definition.chamber_layout or 'either'}")
        if self.needs_light and not definition.expects_light:
            problems.append(f"{label} reads the light, and the type expects no light")
        if self.needs_paradigms and not set(self.needs_paradigms) & set(
                definition.paradigm_types):
            problems.append(f"{label} needs the type to expect "
                            f"{' or '.join(self.needs_paradigms)} in 'light'")
        return problems

    def constant_problems(self, constants: Mapping[str, Any] | None) -> list[str]:
        """Problems with the module's own ``constants:`` values."""
        return []

    # ---- the config ------------------------------------------------------

    def validate(self, global_cfg: Mapping | None) -> list[str]:
        """Problems with a config's ``global:`` under the module."""
        return self.constant_problems((global_cfg or {}).get("constants"))

    def validate_dfm(self, dfm_id: int, node: Mapping | None,
                     chamber_assignments: Mapping | None) -> list[str]:
        """Problems with one ``dfms:`` entry under the module."""
        return []

    def complete_dfm_node(self, dfm_id: int, node: dict, *, params=None,
                          dfm_program=None) -> tuple[dict, list[str]]:
        """``(node, notes)``: the entry with what the Opto Program implies
        filled in.  Never raises."""
        return node, []

    # ---- the report ------------------------------------------------------

    def project_results_blocks(self, experiment_type, project) -> list:
        """Pooled figures of the module's own for the Project Report."""
        return []
