"""The Analysis Modules an Experiment Type combines (ADR-0019).

Each is one analysis pyflic provides — its Selection items, its Plot Specs,
its checks and its share of the report — and states what it needs of the
type.  A definition names them in ``modules:``; a Selection item names the
one it belongs to in ``requires``.  Adding a module takes code and a line in
:data:`MODULES`; including one in a type does not.
"""

from __future__ import annotations

from .base import AnalysisModule
from .hedonic import HEDONIC
from .light_dark import LIGHT_DARK
from .ratio import RATIO
from .yoked import YOKED

#: Every module, in the order the editor lists them and the report runs them.
MODULES: tuple[AnalysisModule, ...] = (RATIO, HEDONIC, YOKED, LIGHT_DARK)
_BY_ID: dict[str, AnalysisModule] = {m.id: m for m in MODULES}


def module_ids() -> tuple[str, ...]:
    return tuple(_BY_ID)


def get_module(module_id: str) -> AnalysisModule:
    """The module *module_id*; ``KeyError`` naming the known ones."""
    try:
        return _BY_ID[str(module_id).strip().lower()]
    except KeyError:
        raise KeyError(f"No Analysis Module {module_id!r}; known: "
                       f"{', '.join(_BY_ID)}") from None


__all__ = ["AnalysisModule", "MODULES", "module_ids", "get_module",
           "HEDONIC", "LIGHT_DARK", "RATIO", "YOKED"]
