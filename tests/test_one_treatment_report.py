"""A report for an experiment with one treatment, or with nothing to plot.

A design with one factor of one level (every chamber Canton-S) is a design,
not a failure, and a recording in which no fly fed has undefined bout
durations: neither may fill a report with red "could not be drawn" boxes,
"no comparison was possible" lines or plots of values that do not exist.
These tests pin what the first real firmware 4.0.0 recording (a quiet,
single-well, all-Canton-S run) showed the report doing wrong.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from pyflic.base import pubfigures
from pyflic.base import report_content as rc
from pyflic.base import report_layout as rl
from pyflic.base.yaml_config import load_experiment_yaml
from v4_fixtures import OFF, DFMSpec, IntervalSpec, ParadigmSpec, RecordingSpec, write_v4_recording

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _texts(doc: rl.ReportDocument) -> list[str]:
    return [t.get_text() for fig in doc._render_pages() for t in fig.texts]


def _doc(*blocks) -> rl.ReportDocument:
    doc = rl.ReportDocument("Experiment report", "quiet", generated="2026-01-01 12:00",
                            version="test")
    doc.add(rl.Cover("Experiment report", "quiet", ["Custom · single-well"]), *blocks)
    return doc


# ---------------------------------------------------------------------------
# The layout: a figure with nothing to draw is a note, not an error
# ---------------------------------------------------------------------------

def test_nothing_to_draw_is_a_neutral_note_without_its_caption():
    def empty():
        raise rl.NothingToDraw("No chamber has a value for Median duration (s).")

    texts = " ".join(_texts(_doc(rl.Plot(empty, title="Median duration",
                                         caption="Mean ± SEM in 30-minute bins."))))
    assert "No chamber has a value for Median duration (s)." in texts
    assert "could not be drawn" not in texts
    assert "Mean ± SEM in 30-minute bins." not in texts


def test_a_real_failure_still_says_so():
    texts = " ".join(_texts(_doc(rl.Plot(lambda: 1 / 0, title="broken"))))
    assert "This figure could not be drawn" in texts


# ---------------------------------------------------------------------------
# The dot plot
# ---------------------------------------------------------------------------

def _frame(values) -> pd.DataFrame:
    return pd.DataFrame({"Treatment": ["Canton-S"] * len(values), "DFM": 1,
                         "Chamber": range(1, len(values) + 1), "V": values})


def test_a_metric_no_chamber_defines_has_nothing_to_draw():
    with pytest.raises(rl.NothingToDraw, match="no bout"):
        rc.dot_plot(_frame([np.nan] * 12), "V", y_label="Median duration (s)",
                    empty_reason="No feeding event was detected, so there is no bout.")


def test_equal_values_are_drawn_at_their_value():
    """Points are jittered across the treatment, never up or down: twelve
    chambers that all scored zero sit on zero."""
    fig = rc.dot_plot(_frame([0.0] * 12), "V", y_label="Licks").draw()
    ys = np.concatenate([np.asarray(c.get_offsets())[:, 1]
                         for ax in fig.axes for c in ax.collections
                         if np.asarray(c.get_offsets()).size])
    assert ys.size >= 12 and np.allclose(ys, 0.0)


# ---------------------------------------------------------------------------
# A quiet one-treatment recording, end to end
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def quiet(tmp_path_factory) -> Path:
    """Twelve single-well chambers, all Canton-S, every well Off and no fly
    feeding: what the first real firmware 4.0.0 recording was."""
    root = tmp_path_factory.mktemp("quiet") / "quiet"
    spec = RecordingSpec(datetime(2026, 10, 17, 0, 17), 30.0,
                         {"Quiet": ParadigmSpec("Quiet", "ClosedLoop")},
                         (DFMSpec(1, (IntervalSpec("Quiet", False, (OFF,) * 12, 30.0),),
                                  {}, linkage=tuple(range(1, 13))),))
    write_v4_recording(root / "data", spec, program=False, messages=False)
    cfg = {"global": {"chamber_layout": "single_well",
                      "params": {"feeding_threshold": 20, "feeding_minimum": 10,
                                 "samples_per_second": 5},
                      "experimental_design_factors": {"Genotype": ["Canton-S"]}},
           "dfms": [{"id": 1, "chambers": {c: "Canton-S" for c in range(1, 13)}}]}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False),
                                           encoding="utf-8")
    return root


def _load(root: Path):
    return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


def test_the_report_of_a_quiet_one_treatment_run_has_no_error(quiet):
    from pyflic.base.pdf_report import build_experiment_report

    exp = _load(quiet)
    assert not exp.is_optogenetic and set(exp.design.treatments) == {"Canton-S"}
    doc = build_experiment_report(exp, metrics=("Licks", "Events", "MedDuration"))
    texts = " ".join(_texts(doc))
    assert "could not be drawn" not in texts
    assert "No treatment comparison was possible" not in texts
    assert texts.count("One treatment, Canton-S, so nothing is compared") == 1
    assert "no bout to measure" in texts
    assert "Not drawn, because no chamber has a value" in texts
    ## A recording whose light never came on has no Program timeline.
    assert "Program timeline" not in texts


def test_the_all_metrics_figure_leaves_out_what_no_chamber_has(quiet):
    exp = _load(quiet)
    missing = exp.feeding_plot_metrics_without_values()
    assert "Median Duration (s)" in missing and "Licks" not in missing
    panels = set(exp.plot_feeding_summary().data["Metric"].astype(str))
    assert "Licks" in panels and not panels & set(missing)


def test_compare_says_there_is_one_treatment(quiet):
    from pyflic.base.analytics import compare_treatments

    with pytest.raises(ValueError, match="Only one treatment \\(Canton-S\\)"):
        compare_treatments(_load(quiet), metric="Licks")


def test_a_report_step_with_its_default_text_reads_the_metrics(quiet, monkeypatch):
    """The Script Editor saves an unedited list parameter as its default
    text; the runner splits it rather than reading it letter by letter."""
    from pyflic.base import pdf_report
    from pyflic.base.script_editor.actions import get_action
    from pyflic.base.script_editor.runner import _as_list, run_experiment_script

    seen: list = []
    monkeypatch.setattr(pdf_report, "write_experiment_report",
                        lambda exp, **kw: seen.append(kw["metrics"]) or "report.pdf")
    default = get_action("pdf_report").params[0].default
    assert isinstance(default, str)
    run_experiment_script(_load(quiet), {"steps": [{"action": "pdf_report",
                                                    "metrics": default}]})
    assert seen == [("Licks", "Events", "MedDuration")]
    assert _as_list("1, 3, 5") == ["1", "3", "5"] and _as_list([2.0, 4.0]) == [2.0, 4.0]
    assert _as_list(None) == [] and _as_list(" , ") == []


def test_the_program_timeline_is_for_optogenetic_experiments(quiet):
    from pyflic.base import program_timeline

    exp = _load(quiet)
    assert exp.dfms[1].paradigm is not None          # generation 3
    assert program_timeline.timeline_dfms(exp) == []


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

def test_only_fonts_this_machine_has_are_asked_for(monkeypatch):
    """matplotlib logs "Font family … not found" for every listed face it
    lacks, on every text: a missing fallback flooded the console."""
    monkeypatch.setattr(pubfigures, "_installed_fonts", lambda: frozenset({"Arial",
                                                                           "DejaVu Sans"}))
    assert pubfigures.resolve_font_family("Arial") == ["Arial", "DejaVu Sans", "sans-serif"]
    assert pubfigures.resolve_font_family("Helvetica Neue") == ["DejaVu Sans", "sans-serif"]
    assert pubfigures.resolve_font_family("serif")[0] == "serif"
    assert "Liberation Sans" not in pubfigures.resolve_font_family("")


@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication

    ## Held for the module: a QApplication nobody references is destroyed
    ## at once, under the widgets still using it.
    yield QApplication.instance() or QApplication([])


def test_the_script_editor_saves_a_list_default_as_a_list(app):
    """A "Write PDF report" step added and never edited is saved with its
    metrics as a list, not as the text the runner used to read letter by
    letter."""
    from pyflic.base.script_editor.canvas import Canvas

    canvas = Canvas()
    canvas.append_step("pdf_report")
    canvas.append_step("param_sensitivity")
    steps = canvas.current_script()["steps"]
    assert steps[0]["metrics"] == ["Licks", "Events", "MedDuration"]
    assert "values" not in steps[1] or isinstance(steps[1]["values"], list)
