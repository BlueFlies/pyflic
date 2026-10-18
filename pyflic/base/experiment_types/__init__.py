"""Experiment Types: the definitions a lab builds above Chamber Layout
(ADR-0007, ADR-0019)."""

from .base import CONTROL_LEVEL_KEY, LAYOUT_CHAMBER_SIZE, LAYOUTS, ExperimentType
from .definition import TypeDefinition, definition_problems, parse_definition
from .library import COPY_NAME
from .registry import (
    RETIRED_AS_LAYOUT,
    available_experiment_types,
    get_experiment_type,
)

__all__ = [
    "ExperimentType",
    "TypeDefinition",
    "parse_definition",
    "definition_problems",
    "get_experiment_type",
    "available_experiment_types",
    "RETIRED_AS_LAYOUT",
    "CONTROL_LEVEL_KEY",
    "COPY_NAME",
    "LAYOUT_CHAMBER_SIZE",
    "LAYOUTS",
]
