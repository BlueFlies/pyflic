"""The Experiment Type Editor and the copy a lab type leaves beside the data
(ADR-0019).

Headless — the widgets are driven directly.  What is asserted is the
contract: what the editor refuses, what saving writes to the library, that
a shipped type is read-only, that *New from…* starts an independent type,
that the Design and Config editors copy a lab type beside the data they save
(and a new Project starts with its Plot Specs), and that a copy differing
from the library's master is said and can be updated.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pyflic.base import project as project_mod  # noqa: E402
from pyflic.base import pubfigures  # noqa: E402
from pyflic.base.config_editor import FLICConfigEditor  # noqa: E402
from pyflic.base.design_editor import ProjectDesignDialog  # noqa: E402
from pyflic.base.experiment_types import library  # noqa: E402
from pyflic.base.experiment_types.definition import (  # noqa: E402
    parse_definition, read_definition)
from pyflic.base.hub import AnalysisHubWindow  # noqa: E402
from pyflic.base.type_editor import ExperimentTypeEditor  # noqa: E402

SPEC = {"title": "Licks, our way", "y_label": "Licks (lab style)"}
TYPE = {"name": "HedonicClosedLoop", "display_name": "Hedonic Feeding, closed loop",
        "chamber_layout": "two_well", "light": ["ClosedLoop"],
        "required_wells": ["A", "B"], "modules": ["hedonic"],
        "plots": ["faceted_pi", "faceted_licks"],
        "plot_specs": {"faceted_licks": SPEC}}


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def lab(tmp_path, monkeypatch) -> Path:
    """An empty lab library, so the user's own never leaks into a test, and
    the settings folder kept in the test's own directory."""
    folder = tmp_path / "library"
    folder.mkdir()
    monkeypatch.setenv(library.ENV_LIBRARY, str(folder))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    ## A save confirms with a modal box; headless it would block.
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    return folder


def _saved_type(**fields):
    data = {**TYPE, **fields}
    definition, problems = parse_definition(data)
    assert problems == []
    library.save_to_library(definition)
    return definition


def _editor(warned: list | None = None, **kwargs) -> ExperimentTypeEditor:
    editor = ExperimentTypeEditor(**kwargs)
    if warned is not None:
        editor._warn = warned.append
    return editor


def _close(editor: ExperimentTypeEditor) -> None:
    editor._dirty = False
    editor.close()


# ---------------------------------------------------------------------------
# The editor
# ---------------------------------------------------------------------------

def test_a_lab_type_is_built_and_saved_to_the_library(app, lab):
    editor = _editor()
    saved: list[str] = []
    editor.typesChanged.connect(saved.append)
    assert any("'name' is required" in p for p in editor.current()[1])
    editor.name_edit.setText("HedonicClosedLoop")
    editor.display_edit.setText("Hedonic Feeding, closed loop")
    editor.layout_combo.setCurrentIndex(editor.layout_combo.findData("two_well"))
    editor.light_buttons["set"].setChecked(True)
    editor.paradigm_checks["ClosedLoop"].setChecked(True)
    editor.well_a_check.setChecked(True)
    editor.well_b_check.setChecked(True)
    editor.module_checks["hedonic"].setChecked(True)
    editor.factors_edit.setText("Genotype")
    editor.treatment_check.setChecked(True)
    assert editor.treatment_combo.currentText() == "Genotype"
    assert editor.current()[1] == []
    assert editor.save_btn.isEnabled()

    assert editor.save_to_library()
    assert saved == ["HedonicClosedLoop"]
    written = read_definition(lab / "HedonicClosedLoop.yaml")
    assert written.light == ("ClosedLoop",) and written.modules == ("hedonic",)
    assert written.treatment_control == "Genotype" and written.factors == ("Genotype",)
    assert "HedonicClosedLoop" in editor.list_names()
    assert editor.delete_btn.isEnabled()
    _close(editor)


def test_a_type_that_cannot_run_is_not_saved(app, lab):
    warned: list[str] = []
    editor = _editor(warned)
    editor.name_edit.setText("RatioWithoutLight")
    editor.layout_combo.setCurrentIndex(editor.layout_combo.findData("two_well"))
    editor.light_buttons["none"].setChecked(True)
    editor.module_checks["ratio"].setChecked(True)
    problems = editor.current()[1]
    assert any("reads the light" in p for p in problems)
    assert "problem" in editor.problems_label.text()
    assert not editor.save_btn.isEnabled()
    assert not editor.save_to_library()
    assert warned and "cannot be saved" in warned[0]
    assert not list(lab.glob("*.yaml"))
    ## A shipped type's name is not a lab type's to take.
    editor.module_checks["ratio"].setChecked(False)
    editor.name_edit.setText("Hedonic")
    assert any("shipped type's name" in p for p in editor.current()[1])
    _close(editor)


def test_a_shipped_type_opens_read_only_and_new_from_copies_it(app, lab):
    editor = _editor(name="Hedonic")
    assert editor._read_only and editor.read_only_note.isVisibleTo(editor)
    assert not editor.save_btn.isEnabled() and not editor.delete_btn.isEnabled()
    assert not editor.save_to_library()
    assert editor.light_buttons["none"].isChecked()

    assert editor.new_from("HedonicOpenLoop")
    assert not editor._read_only and editor._original_name is None
    assert editor.name_edit.text() == "HedonicOpenLoop"
    assert editor.module_checks["hedonic"].isChecked()
    editor.light_buttons["set"].setChecked(True)
    editor.paradigm_checks["OpenLoop"].setChecked(True)
    assert editor.save_to_library()
    copy = read_definition(lab / "HedonicOpenLoop.yaml")
    assert copy.light == ("OpenLoop",)
    ## The shipped type it came from is untouched.
    assert library.shipped_definition("Hedonic").light == "none"
    _close(editor)


def test_the_types_own_plot_specs_come_from_a_projects_plot_specs(app, lab, tmp_path):
    project = tmp_path / "styled"
    project.mkdir()
    specs = pubfigures.ProjectSpecs()
    specs.plots = {"faceted_licks": pubfigures.PlotSpec.from_dict(SPEC)}
    pubfigures.save_project_specs(str(project), specs)

    editor = _editor()
    editor.name_edit.setText("Styled")
    assert editor.import_plot_specs(project) == ["faceted_licks"]
    assert editor.spec_list.count() == 1
    assert editor.save_to_library()
    saved = read_definition(lab / "Styled.yaml")
    assert saved.plot_specs["faceted_licks"]["title"] == SPEC["title"]
    _close(editor)


def test_the_library_folder_can_be_moved(app, lab, tmp_path, monkeypatch):
    """The folder is a setting (ui.json), so a shared drive can hold it."""
    _saved_type()
    monkeypatch.delenv(library.ENV_LIBRARY)
    editor = _editor()
    assert "HedonicClosedLoop" not in editor.list_names()
    editor.set_library_folder(lab)
    assert library.library_dir() == lab
    assert "HedonicClosedLoop" in editor.list_names()
    assert editor.library_label.text() == str(lab)
    other = tmp_path / "shared"
    other.mkdir()
    editor.set_library_folder(other)
    assert "HedonicClosedLoop" not in editor.list_names()
    _close(editor)


# ---------------------------------------------------------------------------
# The copy beside the data
# ---------------------------------------------------------------------------

def test_the_design_editor_copies_a_lab_type_and_seeds_its_plot_specs(app, lab, tmp_path):
    _saved_type()
    root = tmp_path / "Proj"
    root.mkdir()
    dialog = ProjectDesignDialog(start_dir=str(root))
    index = dialog.type_combo.findData("HedonicClosedLoop")
    assert index >= 0 and "(lab)" in dialog.type_combo.itemText(index)
    dialog.type_combo.setCurrentIndex(index)
    assert not dialog.layout_combo.isEnabled()          # the type fixes two_well
    dialog.well_a_edit.setText("Sucrose")
    dialog.well_b_edit.setText("Yeast")
    dialog._save()

    assert dialog.saved_dir == str(root)
    copy = read_definition(root / library.COPY_NAME)
    assert copy.name == "HedonicClosedLoop"
    specs = pubfigures.load_project_specs(str(root))
    assert specs.plots["faceted_licks"].title == SPEC["title"]
    ## The Project resolves its type from the copy, even with no library.
    library.delete_from_library("HedonicClosedLoop")
    assert project_mod.Project(root).experiment_type.name == "HedonicClosedLoop"

    ## A shipped type leaves no copy behind.
    _saved_type()
    again = ProjectDesignDialog(start_dir=str(root))
    assert again.type_combo.currentData() == "HedonicClosedLoop"
    again.type_combo.setCurrentIndex(again.type_combo.findData("Hedonic"))
    again._save()
    assert not (root / library.COPY_NAME).exists()


def test_a_copy_that_differs_from_the_library_is_said_and_updated(app, lab, tmp_path):
    root = tmp_path / "Proj"
    root.mkdir()
    old = _saved_type()
    (root / "project.yaml").write_text(yaml.safe_dump({
        "name": "Proj", "design": {"global": {
            "experiment_type": "HedonicClosedLoop",
            "well_names": {"A": "Sucrose", "B": "Yeast"}}}}), encoding="utf-8")
    library.write_copy(old, root)
    _saved_type(description="A newer wording.")

    dialog = ProjectDesignDialog(start_dir=str(root))
    assert not dialog.type_drift_holder.isHidden()
    assert "differs from the library's" in dialog.type_drift_label.text()
    assert dialog.update_type_copy()
    assert dialog.type_drift_holder.isHidden()
    assert read_definition(root / library.COPY_NAME).description == "A newer wording."

    ## The Hub's Project panel says the same, and updates the same way.
    library.write_copy(old, root)
    hub = AnalysisHubWindow(target=str(root))
    try:
        assert not hub.type_drift_btn.isHidden()
        hub._update_type_copy()
        assert hub.type_drift_btn.isHidden()
        assert library.copy_drift(root) is None
    finally:
        hub.close()


def test_the_config_editor_copies_a_standalone_lab_type(app, lab, tmp_path):
    _saved_type(factors=["Genotype"], control={"treatment": "Genotype"})
    root = tmp_path / "exp"
    path = root / "flic_config.yaml"
    root.mkdir()
    path.write_text(yaml.safe_dump({
        "global": {"experiment_type": "HedonicClosedLoop",
                   "well_names": {"A": "Sucrose", "B": "Yeast"},
                   "experimental_design_factors": {"Genotype": ["w1118", "Gr5a"]},
                   "control_level": "w1118"},
        "dfms": [{"id": 1, "chambers": {1: "w1118", 2: "Gr5a"}}]}), encoding="utf-8")
    editor = FLICConfigEditor(path)
    assert editor._experiment_type_combo.currentData() == "HedonicClosedLoop"
    assert editor._new_type_btn.isEnabled()
    assert editor._control_level_edit.text() == "w1118"
    assert editor._exp_form.isRowVisible(editor._control_level_row)
    editor._confirm_save_with_problems = lambda problems: True
    editor._write_yaml(path)
    assert yaml.safe_load(path.read_text())["global"]["control_level"] == "w1118"
    assert read_definition(root / library.COPY_NAME).name == "HedonicClosedLoop"

    ## Switching to a shipped type removes the copy.
    editor._experiment_type_combo.setCurrentIndex(
        editor._experiment_type_combo.findData("Hedonic"))
    assert not editor._exp_form.isRowVisible(editor._control_level_row)
    editor._write_yaml(path)
    assert not (root / library.COPY_NAME).exists()
    editor.close()


def test_the_editor_opens_from_the_hub_and_the_design_editor(app, lab, tmp_path):
    hub = AnalysisHubWindow()
    try:
        labels = [b.text() for card in hub.panels["tools"].cards()
                  for b in card.findChildren(type(hub.type_drift_btn))]
        assert "Experiment type editor" in labels
    finally:
        hub.close()
    dialog = ProjectDesignDialog(start_dir=str(tmp_path))
    editor = dialog._open_type_editor()
    try:
        editor.name_edit.setText("Plain")
        assert editor.save_to_library()
        ## The new type is listed in the design editor and chosen.
        assert dialog.type_combo.currentData() == "Plain"
    finally:
        _close(editor)
