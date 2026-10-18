"""The Script Editor's panes: what a step is given when it is added, and
which registry the palette and the inspector read.

Headless: the tests drive the widgets directly.
"""

from __future__ import annotations

import os

import pytest

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from pyflic.base.script_editor.actions import capabilities_for  # noqa: E402
from pyflic.base.script_editor.canvas import Canvas  # noqa: E402
from pyflic.base.script_editor.inspector import Inspector  # noqa: E402


@pytest.fixture(scope="module")
def app():
    yield QApplication.instance() or QApplication([])


@pytest.mark.parametrize("layout, metric", [("single_well", "Licks"), ("two_well", "PI")])
def test_a_new_bootstrap_step_gets_a_metric_the_layout_has(app, layout, metric):
    canvas = Canvas()
    canvas.set_experiment_type(capabilities_for({"chamber_layout": layout}))
    canvas.append_step("bootstrap")
    assert canvas.current_script()["steps"][0]["metric"] == metric


def test_the_inspector_shows_the_layouts_default_for_an_unset_metric(app):
    inspector = Inspector()
    inspector.set_experiment_type(capabilities_for({"chamber_layout": "single_well"}))
    inspector.show_step({"action": "bootstrap"})
    assert inspector._widgets["metric"]["get"]() == "Licks"
