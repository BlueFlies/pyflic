"""The Output log's line colouring (``ui/textformat.py``)."""

from __future__ import annotations

import pytest

from pyflic.base.ui.textformat import log_line_to_html

RED = "#d9534f"


@pytest.mark.parametrize("line", [
    ## The integrity report on a clean DFM: the firmware's column is named
    ## Error, and nothing in these lines is a failure.
    "## Error column details",
    "Found error-like column(s): Error",
    "Column: Error",
    "  Error-type counts (among flagged rows):",
])
def test_the_error_column_is_not_an_error(line):
    assert RED not in log_line_to_html(line)


@pytest.mark.parametrize("line", [
    "ERROR: config.yaml could not be read",
    "[load] ERROR loading member 'Rep1'",
    "FAILED to load: no data/ folder",
    "Error: not a directory: C:/data",
    "ValueError: Unknown experiment_type 'X'",
])
def test_a_failure_is_still_red(line):
    assert RED in log_line_to_html(line)
