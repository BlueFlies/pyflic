"""``pyflic lint`` resolves the Chamber Layout as the loader does (ADR-0007).

The loader never reads ``params.chamber_size``: it derives it from the
Experiment Type's layout, else ``chamber_layout:``, else two-well, with a
Member's ``global:`` laid over its Project design's.  Lint once demanded a
``chamber_size`` on every DFM, so it called configs the loader accepts
broken.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from pyflic.base.yaml_lint import lint_flic_config

DFMS = [{"id": 1, "chambers": {1: "Ctrl", 2: "Exp"}}]


def _config(directory: Path, cfg: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "flic_config.yaml"
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return path


def _about_chamber_size(path: Path) -> list[str]:
    return [f"{i.severity}: {i.message}" for i in lint_flic_config(path)
            if "chamber_size" in i.message or "chamber_layout" in i.message]


def _errors(path: Path) -> list[str]:
    return [i.message for i in lint_flic_config(path) if i.severity == "error"]


def test_a_stated_chamber_layout_needs_no_chamber_size(tmp_path):
    path = _config(tmp_path, {"global": {"chamber_layout": "single_well",
                                         "params": {"feeding_threshold": 20}},
                              "dfms": DFMS})
    assert _about_chamber_size(path) == []
    assert _errors(path) == []


def test_a_typed_config_takes_its_layout_from_the_type(tmp_path):
    path = _config(tmp_path, {"global": {"experiment_type": "Hedonic",
                                         "well_names": {"A": "S5", "B": "S5Y5"},
                                         "params": {"feeding_threshold": 20}},
                              "dfms": DFMS})
    assert _about_chamber_size(path) == []
    assert _errors(path) == []


def test_a_member_takes_its_layout_from_the_project_design(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.yaml").write_text(yaml.safe_dump(
        {"name": "P", "design": {"global": {"chamber_layout": "single_well",
                                            "params": {"feeding_threshold": 20}}}}),
        encoding="utf-8")
    path = _config(project / "rep1", {"dfms": DFMS})
    assert _about_chamber_size(path) == []
    assert _errors(path) == []


def test_a_member_is_warned_when_its_chamber_size_is_overruled(tmp_path):
    """The design's layout is the one the loader uses, not the member's own
    leftover chamber_size."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "project.yaml").write_text(yaml.safe_dump(
        {"name": "P", "design": {"global": {"chamber_layout": "single_well"}}}),
        encoding="utf-8")
    path = _config(project / "rep1", {"dfms": [{"id": 1, "params": {"chamber_size": 2},
                                                "chambers": {1: "Ctrl"}}]})
    assert _about_chamber_size(path) == [
        "warning: DFM 1: chamber_size 2 is not read; the chamber layout is "
        "single_well (1 well(s) per chamber)"]


def test_a_layout_left_unstated_is_two_well_as_the_loader_reads_it(tmp_path):
    path = _config(tmp_path, {"global": {"params": {"feeding_threshold": 20}},
                              "dfms": DFMS})
    assert _about_chamber_size(path) == []
    agreeing = _config(tmp_path / "legacy", {"global": {"params": {"chamber_size": 2}},
                                             "dfms": DFMS})
    assert _about_chamber_size(agreeing) == []


def test_a_chamber_size_the_layout_overrules_is_warned(tmp_path):
    path = _config(tmp_path, {"global": {"params": {"chamber_size": 1}},
                              "dfms": DFMS})
    assert _about_chamber_size(path) == [
        "warning: DFM 1: chamber_size 1 is not read; the chamber layout is "
        "two_well (2 well(s) per chamber)"]


def test_an_unknown_chamber_layout_is_an_error_as_it_is_for_the_loader(tmp_path):
    path = _config(tmp_path, {"global": {"chamber_layout": "three_well",
                                         "params": {"feeding_threshold": 20}},
                              "dfms": DFMS})
    assert any("Unknown chamber_layout 'three_well'" in e for e in _errors(path))


def test_an_unknown_experiment_type_is_an_error_as_it_is_for_the_loader(tmp_path):
    path = _config(tmp_path, {"global": {"experiment_type": "Bogus",
                                         "params": {"feeding_threshold": 20}},
                              "dfms": DFMS})
    assert any("Bogus" in e for e in _errors(path))


def test_the_shipped_example_lints_clean():
    example = Path(__file__).resolve().parents[1] / "examples" / "flic_config.yaml"
    assert lint_flic_config(example) == []
