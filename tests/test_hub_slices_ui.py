"""Slices in the Hub and the QC Viewer (ADR-0020).

The Hub shows one Slice at a time, chosen by the Slice picker: the members
table's status, what a double-click loads (and so the loaded member), the QC
Viewer's target and the figures Generate plots opens.  Which Slices *run* is
the Selection: a Slices group on the QC, Analyze and Plots panels, one
setting stored as ``global.omit.slices``.  The QC Viewer loads a Slice in
place of its time range, and its exclusions go to the Slice's own group.

Headless, on small synthetic recordings: a 30-minute member that covers every
Slice and a 20-minute one that stops short of ``mid``.
"""

from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import yaml

pytest.importorskip("PyQt6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import matplotlib  # noqa: E402

matplotlib.use("Agg")

from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from pyflic.base import qc_viewer  # noqa: E402
from pyflic.base import run_selection  # noqa: E402
from pyflic.base import selections as sel  # noqa: E402
from pyflic.base.hub import SLICES_GROUP, AnalysisHubWindow  # noqa: E402
from pyflic.base.project import Project  # noqa: E402
from pyflic.base.ui.widgets import CardGroup  # noqa: E402
from pyflic.base.yaml_config import load_experiment_yaml  # noqa: E402

PARAMS = {"feeding_threshold": 5, "feeding_minimum": 5, "tasting_minimum": 1,
          "tasting_maximum": 4, "feeding_event_link_gap": 2, "samples_per_second": 5,
          "correct_for_dual_feeding": False}
CHAMBERS = {1: "Ctrl", 2: "Ctrl", 3: "Exp", 4: "Exp", 5: "Ctrl", 6: "Exp"}
SLICES = {
    "early": {"start": 0, "end": 10},
    "late": {"start": 10, "end": "end"},
    "mid": {"start": 5, "end": 28},
}
LABELS = ["Whole recording", "early  (0, 10] min", "late  (10, end] min",
          "mid  (5, 28] min"]


def _global(**extra) -> dict:
    g = {"transform_licks": False, "params": dict(PARAMS), "exclusion_group": "general",
         "slices": SLICES}
    g.update(extra)
    return g


def _write_csv(directory: Path, *, minutes: float) -> None:
    """Five samples a second with a feeding bout on every well every minute."""
    n = int(minutes * 60 * 5)
    rng = np.random.default_rng(1)
    cols: dict[str, object] = {"Sample": np.arange(1, n + 1), "Seconds": np.arange(n) / 5.0}
    for w in range(1, 13):
        sig = rng.normal(0.0, 0.3, size=n)
        for k in range(int(minutes)):
            start = 300 * k + 40 + (w * 7) % 30
            sig[start:start + 8] += 10.0 + rng.normal(0, 0.5, size=8)
        cols[f"W{w}"] = np.round(sig, 3)
    directory.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(cols).to_csv(directory / "DFM1_0.csv", index=False)


def _project(tmp_path: Path, **extra) -> Path:
    """``proj``: ``long`` (30 min) covers every Slice, ``short`` (20 min)
    stops short of ``mid``."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": _global(**extra)}}, sort_keys=False))
    for name, minutes in (("long", 30.0), ("short", 20.0)):
        _write_csv(root / name / "data", minutes=minutes)
        (root / name / "flic_config.yaml").write_text(yaml.safe_dump(
            {"dfms": [{"id": 1, "chambers": dict(CHAMBERS)}]}, sort_keys=False))
    return root


def _standalone(root: Path, *, minutes: float = 30.0, **extra) -> Path:
    _write_csv(root / "data", minutes=minutes)
    cfg = {"global": _global(**extra), "dfms": [{"id": 1, "chambers": dict(CHAMBERS)}]}
    root.mkdir(parents=True, exist_ok=True)
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def _quiet(fn, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="module")
def ran_project(tmp_path_factory) -> Path:
    """A Project every Member of which has run the whole recording and every
    Slice — read-only for the tests that share it."""
    root = _project(tmp_path_factory.mktemp("ran"))
    assert _quiet(Project(root).run_all, make_reports=False) == []
    return root


@pytest.fixture
def told(monkeypatch) -> list[str]:
    """What the message boxes said, instead of a modal box."""
    said: list[str] = []
    for kind in ("information", "warning", "critical"):
        monkeypatch.setattr(QMessageBox, kind,
                            lambda *args, **_kw: said.append(str(args[2])))
    return said


def _hub(app, root: Path) -> AnalysisHubWindow:
    hub = AnalysisHubWindow(target=str(root))
    assert hub.project is not None
    return hub


@pytest.fixture
def hubs(app):
    made: list[AnalysisHubWindow] = []

    def make(root: Path) -> AnalysisHubWindow:
        made.append(_hub(app, root))
        return made[-1]

    yield make
    for hub in made:
        hub.close()


def _finish(hub) -> None:
    """Wait for the worker, then deliver the result it queued."""
    worker = hub._worker
    assert worker is not None and worker.wait(120000)
    for _ in range(20):
        QApplication.processEvents()


def _pick(hub, name: str | None) -> None:
    """Pick *name* in the Slice picker as a person would."""
    picker = hub.slice_picker
    index = next(i for i in range(picker.count()) if picker.itemData(i) == name)
    picker.setCurrentIndex(index)
    picker.activated.emit(index)


def _loaded(hub, name: str, slice_name: str | None = None):
    """Load *name* as *slice_name* in place, as a finished load leaves it."""
    exp = _quiet(hub.project.for_slice(slice_name).load_member, name, parallel=False)
    hub.experiment = exp
    hub.experiment_name = name
    hub.refresh()
    return exp


def _analyzed(hub) -> dict[str, str]:
    table = hub.project_table
    return {table.item(r, 0).text(): table.item(r, 3).text() for r in range(table.rowCount())}


def _slices_group(hub, kind: str) -> CardGroup | None:
    return hub._selection_groups[kind].get(SLICES_GROUP)


# ---------------------------------------------------------------------------
# The Slice picker
# ---------------------------------------------------------------------------

def test_without_slices_there_is_no_picker_and_no_slices_group(hubs, tmp_path):
    root = _project(tmp_path)
    meta = yaml.safe_load((root / "project.yaml").read_text())
    del meta["design"]["global"]["slices"]
    (root / "project.yaml").write_text(yaml.safe_dump(meta, sort_keys=False))
    hub = hubs(root)
    assert hub.slice_row.isHidden()
    _loaded(hub, "long")
    for kind in sel.OMIT_KINDS:
        assert _slices_group(hub, kind) is None and hub._slice_boxes[kind] == {}
    assert "Slice" not in hub.readout.status_text()


def test_the_picker_offers_the_whole_recording_then_each_slice(hubs, tmp_path):
    hub = hubs(_project(tmp_path))
    assert not hub.slice_row.isHidden()
    picker = hub.slice_picker
    assert [picker.itemText(i) for i in range(picker.count())] == LABELS
    assert [picker.itemData(i) for i in range(picker.count())] == [None, "early", "late", "mid"]
    assert picker.currentData() is None
    assert "3 Slice(s)" in hub.project_summary.text()


def test_the_table_shows_the_picked_slices_status(hubs, ran_project):
    hub = hubs(ran_project)
    assert _analyzed(hub) == {"long": "yes", "short": "yes"}
    _pick(hub, "mid")
    assert _analyzed(hub) == {"long": "yes", "short": "not covered"}
    tip = hub.project_table.item(1, 3).toolTip()
    assert tip.startswith("short does not cover Slice mid (5, 28] min: DFM 1 ends at minute")
    assert "short of the Slice's end at 28" in tip
    ## The tile's counts are mid's, and say so.
    assert hub.tiles["project"].summary_text().splitlines() == [
        "2 member(s) · mid", "1 analyzed"]
    ## Nothing is loaded, so a pick starts nothing.
    assert hub._worker is None
    _pick(hub, None)
    assert _analyzed(hub) == {"long": "yes", "short": "yes"}


def test_a_double_click_loads_the_member_as_the_picked_slice(hubs, ran_project):
    hub = hubs(ran_project)
    _pick(hub, "early")
    hub._project_row_activated(hub.project_table.item(0, 0))
    _finish(hub)
    assert hub.experiment_name == "long"
    assert hub.experiment.slice_name == "early"
    ## Its outputs and its exclusions are the Slice's own.
    assert hub.experiment.qc_dir == ran_project / "long" / "slices" / "early" / "qc"
    assert hub.experiment.exclusion_group == "early"
    assert "Loaded: long · Slice early  (0, 10] min" in hub.readout.status_text()
    assert "as Slice early (0, 10] min" in hub.log.toPlainText()


def test_a_member_that_does_not_cover_the_slice_is_not_loaded_and_the_hub_says_why(
        hubs, ran_project, told):
    hub = hubs(ran_project)
    _pick(hub, "mid")
    hub._project_row_activated(hub.project_table.item(1, 0))
    _finish(hub)
    assert hub.experiment is None
    assert len(told) == 1
    assert told[0].startswith("short's recording does not cover Slice mid (5, 28] min:")
    assert "short of the Slice's end at 28" in told[0]
    assert "[load] short does not cover Slice mid" in hub.log.toPlainText()
    ## The Hub still shows mid.
    assert hub.slice_picker.currentData() == "mid"


def test_picking_another_slice_reloads_the_loaded_member_as_it(hubs, ran_project):
    hub = hubs(ran_project)
    _loaded(hub, "long")
    assert hub.slice_picker.currentData() is None
    _pick(hub, "late")
    ## The table follows at once, while the member reloads.
    assert "shown: Slice late (10, end] min" in hub.project_summary.text()
    _finish(hub)
    assert hub.experiment_name == "long" and hub.experiment.slice_name == "late"
    assert hub.slice_picker.currentData() == "late"
    _pick(hub, None)
    _finish(hub)
    assert hub.experiment.slice_name is None
    assert hub.experiment.exclusion_group == "general"


def test_a_pick_the_loaded_member_does_not_cover_puts_the_picker_back(
        hubs, ran_project, told):
    hub = hubs(ran_project)
    whole = _loaded(hub, "short")
    _pick(hub, "mid")
    _finish(hub)
    assert hub.experiment is whole
    assert hub.slice_picker.currentData() is None
    assert len(told) == 1 and "short stays loaded as the whole recording." in told[0]
    assert _analyzed(hub) == {"long": "yes", "short": "yes"}


def test_view_reports_opens_the_picked_slices_reports(hubs, ran_project, monkeypatch):
    from pyflic.base.project_report import report_path

    hub = hubs(ran_project)
    opened: list[Path] = []
    monkeypatch.setattr(hub, "_open_externally", opened.append)
    early = hub.project.for_slice("early")
    expected = [Path(report_path(early)), Path(early.member_report_path("long"))]
    for path in expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"%PDF-1.4\n")
    try:
        _pick(hub, "early")
        hub._view_reports()
        assert opened == expected
    finally:
        for path in expected:
            path.unlink()


# ---------------------------------------------------------------------------
# The Slices group: which Slices a run covers
# ---------------------------------------------------------------------------

def test_each_panel_ends_with_one_slices_setting(hubs, tmp_path):
    root = _project(tmp_path)
    hub = hubs(root)
    _loaded(hub, "long")
    for kind in sel.OMIT_KINDS:
        group = _slices_group(hub, kind)
        layout = hub._selection_hosts[kind].layout()
        assert layout.itemAt(layout.count() - 1).widget() is group
        boxes = hub._slice_boxes[kind]
        assert [b.text() for b in boxes.values()] == LABELS[1:]
        assert all(b.isChecked() and group.isAncestorOf(b) for b in boxes.values())
        assert "The whole recording always runs." in group._notes[0].text()

    hub._slice_boxes[sel.QC]["mid"].setChecked(False)
    design = yaml.safe_load((root / "project.yaml").read_text())["design"]
    assert design["global"]["omit"] == {"slices": ["mid"]}
    assert sel.selected_slices(hub.experiment) == ["early", "late"]
    ## One setting on three panels.
    assert not hub._slice_boxes[sel.ANALYSES]["mid"].isChecked()
    assert not hub._slice_boxes[sel.PLOTS]["mid"].isChecked()
    assert hub.log.toPlainText().splitlines()[-1] == (
        "[selection] Slice mid: left out of every member's runs in Project proj, not "
        f"only long's (design.global.omit.slices in {root / 'project.yaml'})")

    hub._slice_boxes[sel.PLOTS]["mid"].setChecked(True)
    design = yaml.safe_load((root / "project.yaml").read_text())["design"]
    assert "omit" not in design["global"]
    assert all(hub._slice_boxes[k]["mid"].isChecked() for k in sel.OMIT_KINDS)

    ## Loaded again, the boxes are rebuilt from what was written.
    hub._slice_boxes[sel.ANALYSES]["early"].setChecked(False)
    _loaded(hub, "short")
    assert [n for n, b in hub._slice_boxes[sel.QC].items() if not b.isChecked()] == ["early"]


def test_a_standalone_experiments_slices_are_its_own_configs(app, tmp_path):
    root = _standalone(tmp_path / "alone")
    hub = AnalysisHubWindow()
    try:
        exp = _quiet(load_experiment_yaml, root, parallel=False)
        hub.experiment, hub.experiment_name = exp, "alone"
        hub.refresh()
        assert not hub.slice_row.isHidden()
        assert hub.slice_picker.count() == 4
        hub._slice_boxes[sel.QC]["late"].setChecked(False)
        written = yaml.safe_load((root / "flic_config.yaml").read_text())
        assert written["global"]["omit"] == {"slices": ["late"]}
        assert hub.log.toPlainText().splitlines()[-1] == (
            "[selection] Slice late: left out of every run of alone "
            f"(global.omit.slices in {root / 'flic_config.yaml'})")
    finally:
        hub.close()


def _figure():
    from matplotlib.figure import Figure

    fig = Figure(figsize=(2, 2))
    fig.add_subplot().plot([0, 1], [0, 1])
    return fig


def test_generate_plots_runs_the_step_and_opens_the_shown_slices_figures(
        hubs, tmp_path, monkeypatch, told):
    """The button runs the run_plots step, as Run QC and Run analysis run
    theirs (ADR-0018): every ticked Slice's files are the step's.  The step
    hands back each Slice's figures titled with its name, and the Hub opens
    the shown Slice's."""
    from pyflic.base.script_editor import runner

    hub = hubs(_project(tmp_path))
    _loaded(hub, "long", "early")
    hub._slice_boxes[sel.PLOTS]["mid"].setChecked(False)
    calls: list[str | None] = []
    steps: list = []

    def run_items(exp, run, todo, ctx):
        calls.append(exp.slice_name)
        ctx.figure("Feeding Summary", _figure())

    real = runner.run_experiment_script

    def run_script(exp, script, *, context=None):
        steps.append(script["steps"])
        return real(exp, script, context=context)

    monkeypatch.setattr(run_selection, "_run_items", run_items)
    monkeypatch.setattr(runner, "run_experiment_script", run_script)
    hub.generate_plots_btn.click()
    _finish(hub)
    assert told == []
    assert steps == [[{"action": "run_plots", "metric": hub.plot_metric.currentData(),
                       "binsize": hub.spin_binsize.value()}]]
    ## The whole recording, then each ticked Slice; only the shown one's
    ## figures are opened, under its name.
    assert calls == [None, "early", "late"]
    titles = [hub.dock.tabText(i) for i in range(hub.dock.count())]
    assert "Feeding Summary · Slice early" in titles
    assert "Feeding Summary" not in titles and "Feeding Summary · Slice late" not in titles

    ## Shown but unticked: nothing drawn for it, and the log says so.
    calls.clear()
    hub._slice_boxes[sel.PLOTS]["early"].setChecked(False)
    hub.generate_plots_btn.click()
    _finish(hub)
    assert calls == [None, "late"]
    assert "Slice early was not in this run, so no figure is shown" in hub.log.toPlainText()


def test_a_slices_figures_are_titled_with_its_name(tmp_path):
    """run_plots names the Slice in each figure's title, so a script run
    across Slices returns figures a reader can tell apart."""
    root = _standalone(tmp_path / "alone")
    early = _quiet(load_experiment_yaml, root, parallel=False, slice="early")
    omit = [item.id for item in sel.items(sel.PLOTS) if item.id != "feeding_summary_plot"]
    run = _quiet(run_selection.run_plots, early, omit=omit, log=lambda _m: None)
    assert [title for title, _fig in run.figures] == ["Feeding Summary · Slice early"]
    assert run_selection.title_slice(run.figures[0][0]) == "early"
    assert run_selection.title_slice("Feeding Summary") is None


def test_run_qc_writes_the_whole_recording_and_each_ticked_slice(hubs, tmp_path):
    """The button runs the run_qc step, so the files are the step's: the
    whole recording's qc/, then slices/<name>/qc/ for each ticked Slice."""
    root = _project(tmp_path, omit={"qc": ["raw_signal", "baselined_signal",
                                           "cumulative_licks"],
                                    "slices": ["mid"]})
    hub = hubs(root)
    _loaded(hub, "long", "late")
    hub.run_qc_btn.click()
    _finish(hub)
    member = root / "long"
    assert (member / "qc" / "integrity").is_dir()
    assert (member / "slices" / "early" / "qc" / "integrity").is_dir()
    assert (member / "slices" / "late" / "qc" / "integrity").is_dir()
    assert not (member / "slices" / "mid").exists()


def test_combine_and_create_report_build_every_slices_too(hubs, ran_project, monkeypatch):
    from pyflic.base import project_report

    hub = hubs(ran_project)
    called: list[str] = []
    monkeypatch.setattr(type(hub.project), "build_all_combined_analyses",
                        lambda self, log=print: called.append("combined") or {})
    monkeypatch.setattr(project_report, "write_all_project_reports",
                        lambda project, **kw: called.append("reports") or [])
    hub._build_combined()
    _finish(hub)
    hub._project_report()
    _finish(hub)
    assert called == ["combined", "reports"]


# ---------------------------------------------------------------------------
# The QC Viewer
# ---------------------------------------------------------------------------

def test_the_viewer_offers_the_designs_slices_and_a_slice_replaces_the_range(app, tmp_path):
    root = _standalone(tmp_path / "alone")
    win = qc_viewer.MainWindow(root)
    try:
        tab = win._load_tab
        combo = tab._slice_combo
        assert [combo.itemText(i) for i in range(combo.count())] == LABELS
        assert tab._form.isRowVisible(combo)
        assert tab.selected_slice() is None
        assert tab._start_spin.isEnabled() and tab._end_spin.isEnabled()
        combo.setCurrentIndex(combo.findData("early"))
        assert tab.selected_slice() == "early"
        assert not tab._start_spin.isEnabled() and not tab._end_spin.isEnabled()
    finally:
        win.close()


def test_the_viewer_hides_the_slice_menu_without_slices(app, tmp_path):
    root = _standalone(tmp_path / "alone")
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    del cfg["global"]["slices"]
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    win = qc_viewer.MainWindow(root)
    try:
        assert not win._load_tab._form.isRowVisible(win._load_tab._slice_combo)
        assert win._load_tab._start_spin.isEnabled()
    finally:
        win.close()


class _Stop(Exception):
    pass


@pytest.mark.parametrize("pick, expected", [
    (None, ((2.0, 5.0), None)),
    ("late", ((2.0, 5.0), "late")),
])
def test_load_hands_the_worker_the_slice_or_the_range(app, tmp_path, monkeypatch,
                                                      pick, expected):
    root = _standalone(tmp_path / "alone")
    win = qc_viewer.MainWindow(root)
    seen: list = []

    def worker(directory, range_minutes, parallel, parent=None, *, slice_name=None):
        seen.append((range_minutes, slice_name))
        raise _Stop

    monkeypatch.setattr(qc_viewer, "_LoadWorker", worker)
    try:
        tab = win._load_tab
        tab._start_spin.setValue(2.0)
        tab._end_spin.setValue(5.0)
        tab._slice_combo.setCurrentIndex(tab._slice_combo.findData(pick) if pick else 0)
        with pytest.raises(_Stop):
            tab._on_load_clicked()
        assert seen == [expected]
    finally:
        win.close()


def test_a_slice_load_passes_the_slice_not_the_range(app, tmp_path):
    root = _standalone(tmp_path / "alone")
    fake = mock.MagicMock()
    fake.qc_results = {}
    with mock.patch("pyflic.base.yaml_config.load_experiment_yaml",
                    return_value=fake) as loader:
        worker = qc_viewer._LoadWorker(root, (0.0, 0.0), True, slice_name="early")
        errors: list = []
        worker.errored.connect(errors.append)
        _quiet(worker.run)
    assert errors == []
    kwargs = loader.call_args.kwargs
    assert kwargs["slice"] == "early" and kwargs["exclusion_group"] is None
    assert "range_minutes" not in kwargs


def test_a_member_slice_loads_through_its_project(app, tmp_path):
    root = _project(tmp_path)
    fake = mock.MagicMock()
    fake.qc_results = {}
    with mock.patch("pyflic.base.project.Project") as FakeProject:
        FakeProject.return_value.load_member.return_value = fake
        worker = qc_viewer._LoadWorker(root / "long", (0.0, 0.0), True, slice_name="mid")
        _quiet(worker.run)
    call = FakeProject.return_value.load_member.call_args
    assert call.args[0] == "long"
    assert call.kwargs["slice"] == "mid" and call.kwargs["exclusion_group"] is None
    assert "range_minutes" not in call.kwargs


def test_a_slice_the_recording_does_not_cover_does_not_load(app, tmp_path):
    root = _standalone(tmp_path / "alone", minutes=20.0)
    worker = qc_viewer._LoadWorker(root, (0.0, 0.0), False, slice_name="mid")
    errors: list = []
    worker.errored.connect(errors.append)
    _quiet(worker.run)
    assert len(errors) == 1 and "short of the Slice's end at 28" in errors[0]


def test_a_loaded_slice_saves_exclusions_to_its_own_group(app, tmp_path):
    """Loaded as a Slice with nothing excluded, the viewer writes what you
    exclude to the Slice's own group, and leaves the whole recording's alone."""
    from pyflic.base.exclusions import read_exclusions, write_exclusions

    root = _standalone(tmp_path / "alone")
    write_exclusions(root, "early", {1: [2]})
    write_exclusions(root, "general", {1: [5]})
    exp = _quiet(load_experiment_yaml, root, parallel=False, use_disk_cache=False,
                 exclusion_group=None, slice="early")
    assert exp.excluded_chambers == {} and exp.exclusion_group == "early"
    win = qc_viewer.MainWindow(root, experiment=exp)
    try:
        assert win._load_tab.selected_slice() == "early"
        assert not win._load_tab._start_spin.isEnabled()
        assert "Slice early (0, 10] min" in win.windowTitle()
        assert "own group, 'early'" in win.statusBar().currentMessage()
        assert win._active_group() == "early"
        ## The Slice's group is what the tabs open ticked with.
        assert win._dfm_tab_widgets[1].get_excluded_wells() == [3, 4]
        win._dfm_tab_widgets[1].set_well_excluded(5, True)
        win._save_exclusions_to_file(group=win._active_group())
        saved = read_exclusions(root)
        assert saved["early"] == {1: [2, 3]}
        assert saved["general"] == {1: [5]}
    finally:
        win.close()


def test_a_standalone_configs_exclusion_group_is_read_by_every_load(app, tmp_path, told):
    """global.exclusion_group: main is the whole recording's group wherever
    it is loaded: the Hub, the QC Viewer's Load tab, and each_slice reloading
    the whole recording from a Slice — never general's rows (U1)."""
    from pyflic.base.exclusions import write_exclusions

    root = _standalone(tmp_path / "alone", exclusion_group="main")
    write_exclusions(root, "main", {1: [2]})
    write_exclusions(root, "general", {1: [5]})

    hub = AnalysisHubWindow()
    try:
        assert hub._load_standalone(str(root))
        _finish(hub)
        assert told == []
        assert hub.experiment.exclusion_group == "main"
        assert hub.experiment.excluded_chambers == {1: [2]}
    finally:
        hub.close()

    ## The Load tab's load excludes nothing, and saves to the design's group.
    exp = _quiet(load_experiment_yaml, root, parallel=False, exclusion_group=None)
    assert exp.excluded_chambers == {} and exp.exclusion_group == "main"
    viewer = qc_viewer.MainWindow(root, experiment=exp)
    try:
        assert viewer._active_group() == "main"
        ## Ticked from main's rows: chamber 2 is wells 3 and 4.
        assert viewer._dfm_tab_widgets[1].get_excluded_wells() == [3, 4]
    finally:
        viewer.close()

    early = _quiet(load_experiment_yaml, root, parallel=False, slice="early")
    whole = next(run_selection.each_slice(early, only=None, log=lambda _m: None))
    assert whole.slice_name is None and whole.exclusion_group == "main"
    assert whole.excluded_chambers == {1: [2]}


def test_the_hub_opens_the_viewer_on_the_slice_it_shows(hubs, ran_project):
    hub = hubs(ran_project)
    exp = _loaded(hub, "long", "late")
    hub._open_qc_viewer()
    try:
        assert hub._qc._exp is exp
        assert hub._qc._load_tab.selected_slice() == "late"
        assert hub._qc._active_group() == "late"
    finally:
        hub._qc.close()


def _wheel(widget, step: int):
    """Send *widget* a wheel event, as a pointer passing over it does."""
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    event = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, step),
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                        Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(widget, event)
    return event


def _value(widget):
    from PyQt6.QtWidgets import QComboBox

    return widget.currentIndex() if isinstance(widget, QComboBox) else widget.value()


def test_the_wheel_scrolls_past_every_slice_dropdown(hubs, tmp_path):
    """A wheel over a Slice picker leaves the Slice alone and passes the scroll
    on to the window: picking a Slice reloads what the window shows."""
    from pyflic.base.ui.widgets import NoWheelComboBox

    root = _project(tmp_path)
    hub = hubs(root)
    viewer = qc_viewer.MainWindow(root / "long")
    combos = [hub.slice_picker, viewer._load_tab._slice_combo]
    for combo in combos:
        assert isinstance(combo, NoWheelComboBox)
        before = combo.currentIndex()
        event = _wheel(combo, -120)
        assert combo.currentIndex() == before and not event.isAccepted()
    viewer.close()


def test_the_wheel_changes_nothing_on_any_hub_panel(app, tmp_path, told):
    """Every panel scrolls, so every combo and spin box on one ignores the
    wheel: the worker count, the Project and Batch scripts and the rest.  The
    Batch script above all, whose change is written to batch.yaml at once."""
    from PyQt6.QtWidgets import QAbstractSpinBox, QComboBox

    from pyflic.base.ui.widgets import NoWheelComboBox, NoWheelDoubleSpinBox, NoWheelSpinBox

    batch = tmp_path / "batch"
    batch.mkdir()
    _project(batch)
    hub = AnalysisHubWindow(target=str(batch))
    try:
        assert hub.batch_script.count() > 1
        hosted = [w for panel in hub.panels.values()
                  for w in panel.findChildren((QComboBox, QAbstractSpinBox))]
        for widget in (hub.spin_workers, hub.project_script, hub.batch_script,
                       hub.spin_binsize, hub.ai_provider):
            assert widget in hosted
        ## Placed on the Plots panel once a member is loaded.
        hosted.append(hub.plot_metric)
        for widget in hosted:
            assert isinstance(widget, (NoWheelComboBox, NoWheelSpinBox,
                                       NoWheelDoubleSpinBox)), widget
            before = _value(widget)
            for step in (-120, 120):
                _wheel(widget, step)
            assert _value(widget) == before, widget
        assert not (batch / "batch.yaml").exists()
    finally:
        hub.close()
