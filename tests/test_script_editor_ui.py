"""The Script Editor's panes: what a step is given when it is added, and
which registry the palette and the inspector read.

Headless: the tests drive the widgets directly.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

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


# ---------------------------------------------------------------------------
# A project.yaml: the project registry (ADR-0005)
# ---------------------------------------------------------------------------

def _window(path: Path, payload: dict):
    from pyflic.base.script_editor.window import ScriptEditorWindow

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return ScriptEditorWindow(path)


def _close(window) -> None:
    window._dirty = False
    window.close()


def _palette_actions(window) -> set[str]:
    return {act.action for _tile, act in window._palette._tiles}


PROJECT = {"name": "P", "design": {"global": {"chamber_layout": "two_well"}},
           "scripts": [{"name": "batch", "steps": [
               {"action": "run_in_experiments", "script": "quick", "only": ["rep1"]},
               {"action": "project_report"}]}]}


def test_on_a_project_yaml_the_palette_offers_the_project_actions(app, tmp_path):
    from pyflic.base.script_editor.actions import ACTIONS
    from pyflic.base.script_editor.project_actions import PROJECT_ACTIONS

    window = _window(tmp_path / "project.yaml", PROJECT)
    try:
        assert _palette_actions(window) == {a.action for a in PROJECT_ACTIONS}
        ## Nothing is dimmed: a project action runs on any Project.
        assert window._experiment_type is None
    finally:
        _close(window)
    member = _window(tmp_path / "rep1" / "flic_config.yaml",
                     {"dfms": [{"id": 1, "chambers": {1: "Ctrl"}}]})
    try:
        assert _palette_actions(member) == {a.action for a in ACTIONS}
        assert "two_well" in member._experiment_type
    finally:
        _close(member)


def test_a_project_step_shows_its_parameters_and_no_warning(app, tmp_path):
    window = _window(tmp_path / "project.yaml", PROJECT)
    try:
        window._canvas._list.setCurrentRow(0)
        inspector = window._inspector
        assert inspector._current_action.action == "run_in_experiments"
        assert inspector._widgets["script"]["get"]() == "quick"
        assert inspector._widgets["only"]["get"]() == ["rep1"]
        for row in range(window._canvas._list.count()):
            card = window._canvas._list.itemWidget(window._canvas._list.item(row))
            assert card._warn_lbl.isHidden(), card._warn_lbl.toolTip()
    finally:
        _close(window)


def test_a_project_action_can_be_added_and_edited(app, tmp_path):
    window = _window(tmp_path / "project.yaml", PROJECT)
    try:
        window._on_palette_action("run_all_analyses")
        step = window._canvas.selected_step()
        assert step == {"action": "run_all_analyses", "skip_analyzed": False,
                        "reports": False}
        window._inspector._widgets["skip_analyzed"]["widget"].setChecked(True)
        assert window._canvas.selected_step()["skip_analyzed"] is True
        window._save_to_disk()
        saved = yaml.safe_load((tmp_path / "project.yaml").read_text(encoding="utf-8"))
        assert saved["scripts"][0]["steps"][-1] == {
            "action": "run_all_analyses", "skip_analyzed": True, "reports": False}
        assert saved["design"] == PROJECT["design"]
    finally:
        _close(window)
