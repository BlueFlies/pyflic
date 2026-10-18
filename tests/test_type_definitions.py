"""Experiment Types as definitions a lab builds (ADR-0019).

The definition's yaml, the Analysis Modules' needs, the shipped types, the
lab library and the copy beside the data, resolution, the light check
against the Opto Program, and the Treatment control's level.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from pyflic.base import experiment_types as et
from pyflic.base import opto_program as op
from pyflic.base.analysis_modules import get_module, module_ids
from pyflic.base.experiment_types import library
from pyflic.base.experiment_types.definition import (
    LIGHT_ANY, LIGHT_NONE, dump_definition, parse_definition, read_definition,
    write_definition)


@pytest.fixture
def lab(tmp_path, monkeypatch) -> Path:
    """An empty lab library, so the user's own never leaks into a test."""
    folder = tmp_path / "library"
    folder.mkdir()
    monkeypatch.setenv(library.ENV_LIBRARY, str(folder))
    return folder


def _definition(**fields):
    data = {"name": "HedonicClosedLoop", "display_name": "Hedonic Feeding, closed loop",
            "chamber_layout": "two_well", "light": ["ClosedLoop"],
            "required_wells": ["A", "B"], "modules": ["hedonic"]}
    data.update(fields)
    definition, problems = parse_definition(data)
    assert definition is not None
    return definition, problems


# ---------------------------------------------------------------------------
# The yaml
# ---------------------------------------------------------------------------

def test_a_definition_round_trips_through_its_yaml(tmp_path):
    definition, problems = _definition(
        factors=["Genotype"], control={"roles": ["Self", "Unlit"], "treatment": "Genotype"},
        plots=["faceted_pi", "faceted_licks"], facets={"cutoffs": [30], "labels": ["A", "B"]},
        constants={"max_events_cutoff": 500})
    assert problems == []
    path = write_definition(definition, tmp_path / "t.yaml")
    again = read_definition(path)
    assert dump_definition(again) == dump_definition(definition)
    assert again.roles == ("Self", "Unlit") and again.treatment_control == "Genotype"
    assert again.facet_cutoffs == (30.0,)


@pytest.mark.parametrize("raw,light", [
    (None, LIGHT_ANY), ("any", LIGHT_ANY), ("none", LIGHT_NONE), (False, LIGHT_NONE),
    (["closedloop", "OpenLoop"], ("OpenLoop", "ClosedLoop")),
    ("FixedRatio", ("FixedRatio",)),
])
def test_light_reads_none_any_or_paradigm_types_in_any_case(raw, light):
    definition, problems = _definition(light=raw)
    assert problems == [] and definition.light == light


def test_reading_lists_every_problem_and_keeps_the_rest():
    definition, problems = _definition(light=["ClosedLop"], colour="red",
                                       control={"roles": ["Paired"]})
    assert definition.name == "HedonicClosedLoop"
    assert any("ClosedLop" in p and "not a Paradigm type" in p for p in problems)
    assert any("unknown key 'colour'" in p for p in problems)
    assert any("must name two Roles" in p for p in problems)


def test_a_name_must_be_what_experiment_type_can_hold():
    _definition_, problems = _definition(name="Hedonic closed")
    assert any("must start with a letter" in p for p in problems)
    assert parse_definition({"display_name": "x"})[0] is None


# ---------------------------------------------------------------------------
# What the modules need
# ---------------------------------------------------------------------------

def test_the_four_modules():
    assert set(module_ids()) == {"ratio", "hedonic", "yoked", "light_dark"}
    assert get_module("ratio").experiment_class.endswith("ProgressiveRatioExperiment")


@pytest.mark.parametrize("fields,fragment", [
    ({"chamber_layout": "single_well"}, "needs chamber_layout two_well"),
    ({"modules": ["yoked"], "light": "none"}, "reads the light"),
    ({"modules": ["ratio"], "light": ["ClosedLoop"]}, "ProgressiveRatio or FixedRatio"),
    ({"modules": ["ratio", "yoked"], "light": ["ProgressiveRatio"]}, "cannot run together"),
    ({"modules": ["ratio", "hedonic"], "light": ["ProgressiveRatio"]},
     "analysis class of their own"),
    ({"modules": ["telepathy"]}, "not an Analysis Module"),
    ({"control": {"treatment": "Genotype"}}, "not one of the type's factors"),
    ({"light": "none", "control": {"roles": ["Paired", "Yoked"]}}, "needs light"),
    ({"control": {"roles": ["Yoked", "Paired"]}}, "include the 'yoked' module"),
])
def test_a_combination_that_cannot_run_is_refused(fields, fragment):
    definition, _ = _definition(**fields)
    assert any(fragment in p for p in et.definition_problems(definition))


def test_a_type_expecting_closed_loop_training_may_run_the_ratio_module():
    """Scenario 1 of the design session: ClosedLoop Training before PR10 is
    a lab type's to expect, and the Ratio module only needs a ratio type
    among those it expects."""
    definition, _ = _definition(name="TrainedRatio", modules=["ratio"],
                                light=["ClosedLoop", "ProgressiveRatio"])
    assert et.definition_problems(definition) == []


# ---------------------------------------------------------------------------
# The shipped types
# ---------------------------------------------------------------------------

def test_the_shipped_types_keep_what_their_classes_did(lab):
    custom, hedonic, pr = (et.get_experiment_type(n) for n in
                           (None, "Hedonic", "ProgressiveRatio"))
    assert custom.is_custom and custom.layout_free and custom.light == "any"
    assert custom.module_ids == ("yoked", "light_dark")
    assert hedonic.chamber_layout == "two_well" and hedonic.light == "none"
    assert hedonic.experiment_class.endswith("HedonicFeedingExperiment")
    assert hedonic.default_constants["max_events_cutoff"] == 150000.0
    assert pr.light == ("ProgressiveRatio", "FixedRatio")
    assert pr.data_derived_facets and pr.phase_labels == ("Training", "Test")
    assert pr.report_facets() == ["Test"]
    assert pr.report_set("two_well")[:3] == ["timecourse_pr_diff",
                                              "scatter_pr_breaking_point",
                                              "dot_pr_breaking_point"]
    assert pr.default_constants["require_training_complete"] is True
    assert all(t.is_shipped for t in (custom, hedonic, pr))


# ---------------------------------------------------------------------------
# The lab library and the copy
# ---------------------------------------------------------------------------

def test_a_lab_type_is_saved_listed_and_resolved(lab):
    definition, _ = _definition()
    library.save_to_library(definition)
    assert (lab / "HedonicClosedLoop.yaml").is_file()
    names = [t.name for t in et.available_experiment_types()]
    assert names[:3] == ["Custom", "Hedonic", "ProgressiveRatio"]
    assert "HedonicClosedLoop" in names
    etype = et.get_experiment_type("hedonic_closed_loop")
    assert etype.name == "HedonicClosedLoop" and etype.resolved_from == "library"
    assert not etype.is_shipped and etype.has_module("hedonic")


def test_a_lab_type_cannot_take_a_shipped_name(lab):
    definition, _ = _definition(name="Progressive_Ratio")
    with pytest.raises(ValueError, match="shipped"):
        library.save_to_library(definition)
    (lab / "Hedonic.yaml").write_text(yaml.safe_dump({"name": "Hedonic"}))
    _found, problems = library.library_definitions()
    assert any("shipped type's name" in p for p in problems)


def test_the_copy_beside_the_data_wins_and_travels(lab, tmp_path):
    project = tmp_path / "proj"
    member = project / "rep1"
    member.mkdir(parents=True)
    (project / "project.yaml").write_text("design: {}\n")
    definition, _ = _definition()
    path = library.write_copy(definition, member)
    assert path == project / library.COPY_NAME
    ## No library master: the copy alone resolves it, from the Member or the Project.
    for where in (member, project):
        etype = et.get_experiment_type("HedonicClosedLoop", where)
        assert etype.resolved_from == "copy"
    with pytest.raises(ValueError, match="Unknown experiment_type"):
        et.get_experiment_type("HedonicClosedLoop")
    assert library.copy_drift(member) is None


def test_a_copy_that_differs_from_its_master_is_flagged(lab, tmp_path):
    definition, _ = _definition()
    library.save_to_library(definition)
    changed, _ = _definition(description="A newer wording.")
    library.write_copy(changed, tmp_path)
    assert "differs from the library's" in library.copy_drift(tmp_path)
    ## The copy still decides the analysis until it is updated.
    assert et.get_experiment_type("HedonicClosedLoop", tmp_path).report_intro() == \
        "A newer wording."


def test_a_shipped_type_needs_no_copy(tmp_path):
    with pytest.raises(ValueError, match="needs no copy"):
        library.write_copy(library.shipped_definition("Hedonic"), tmp_path)


# ---------------------------------------------------------------------------
# The light the type expects
# ---------------------------------------------------------------------------

_SETTINGS = {
    "ClosedLoop": "HoldMs 500 ms, MaxOnMs 0 ms, EventGapMs 100 ms",
    "OpenLoop": "Frequency 40 Hz",
    "ProgressiveRatio": ("ActivationMs 500 ms, Series Arithmetic, FirstRequirement 1, "
                         "Step 10, Cap 200, EventGapMs 100 ms, Acclimation 0"),
    "FixedRatio": "ActivationMs 500 ms, Ratio 5, EventGapMs 100 ms, Acclimation 0",
    "NonFeeding": "OnDelayMs 100 ms, MaxOnMs 0 ms",
}


def _program(*intervals) -> op.OptoProgram:
    """A one-DFM 4.0.0 export (the shape of ``tests/fixtures/Program_v4.txt``):
    each interval is ``(Paradigm type, twelve thresholds)``, 30 minutes."""
    lines = ["Start Time: 10/12/2026 20:00:00", "End Time: 10/13/2026 02:00:00",
             f"Duration: {30 * len(intervals)} min",
             "Default Linkage: 1,1,2,2,3,3,4,4,5,5,6,6", "Default Program Type: Linear",
             "Baseline: Yes", "", "Paradigms:"]
    for index, (kind, _wells) in enumerate(intervals, start=1):
        lines.append(f"P{index} ({kind}): Frequency 40 Hz, PulseWidth 8 ms, "
                     f"{_SETTINGS[kind]}")
    lines += ["", "***DFM 1***", "Linkage: 1,1,2,2,3,3,4,4,5,5,6,6", "Program Type: Linear"]
    for index, (_kind, wells) in enumerate(intervals, start=1):
        minute = 30 * (index - 1)
        lines.append(f"(10/12/2026 {20 + minute // 60:02d}:{minute % 60:02d}:00) Lit, "
                     f"P{index}, {','.join(wells)}, 30 min")
    program = op.parse_program("\n".join(lines) + "\n")
    assert program.section(1) is not None and len(program.section(1).intervals) == \
        len(intervals), program.warnings
    return program


def _levels(*values):
    return [str(v) for v in values] + ["Off"] * (12 - len(values))


def test_light_problems_name_each_unexpected_paradigm_type():
    pr = et.get_experiment_type("ProgressiveRatio")
    program = _program(("ClosedLoop", _levels(20)), ("ProgressiveRatio", _levels(20)))
    problems = pr.light_problems(program)
    assert len(problems) == 1 and "runs ClosedLoop (DFM 1 interval 1)" in problems[0]
    ## OpenLoop wells and dark intervals sit beside any expected set.
    beside = _program(("ProgressiveRatio", _levels(20, "On")), ("ClosedLoop", _levels()))
    assert pr.light_problems(beside) == []


def test_a_type_that_expects_no_light_takes_none():
    hedonic = et.get_experiment_type("Hedonic")
    assert "expects no light" in hedonic.light_problems(
        _program(("OpenLoop", _levels("On"))))[0]
    assert hedonic.light_problems(_program(("ClosedLoop", _levels()))) == []
    assert et.get_experiment_type(None).light_problems(
        _program(("NonFeeding", _levels(20)))) == []


# ---------------------------------------------------------------------------
# Factors and the Treatment control's level
# ---------------------------------------------------------------------------

def test_the_design_declares_the_types_factors_and_names_the_control(lab):
    definition, _ = _definition(factors=["Genotype"], control={"treatment": "Genotype"})
    library.save_to_library(definition)
    etype = et.get_experiment_type("HedonicClosedLoop")
    wells = {"A": "S", "B": "Y"}
    problems = etype.validate({"well_names": wells})
    assert any("factor Genotype declared" in p for p in problems)
    assert any("name it with 'control_level'" in p for p in problems)
    factors = {"Genotype": ["w1118", "Gr5a"], "Diet": ["low", "high"]}
    assert etype.validate({"well_names": wells, "experimental_design_factors": factors,
                           "control_level": "w1118"}) == []
    assert any("not a level of Genotype" in p for p in etype.validate(
        {"well_names": wells, "experimental_design_factors": factors,
         "control_level": "CS"}))
    assert etype.control_level({"control_level": "w1118"}) == "w1118"
    assert any("has no Treatment control" in p for p in
               et.get_experiment_type(None).validate({"control_level": "w1118"}))


# ---------------------------------------------------------------------------
# At load: the light check, the copy, the two-well cutoffs, and lint
# ---------------------------------------------------------------------------

import contextlib  # noqa: E402
import io  # noqa: E402
from functools import lru_cache  # noqa: E402

import v4_fixtures as vf  # noqa: E402
from pr_fixtures import pr_config  # noqa: E402

from pyflic.base.yaml_config import load_experiment_yaml  # noqa: E402
from pyflic.base.yaml_lint import lint_flic_config  # noqa: E402

_PARAMS = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
           "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}


@lru_cache(maxsize=None)
def _recording(name: str):
    spec = {"choice": lambda: vf.choice_pr_spec(dfm_ids=(1,)),
            "fixed": lambda: vf.fixed_ratio_spec(minutes=6.0)}[name]()
    return spec, vf.simulate(spec)


def _write(root: Path, name: str, global_cfg: dict) -> Path:
    spec, results = _recording(name)
    root.mkdir(parents=True, exist_ok=True)
    vf.write_v4_recording(root / "data", spec, results=results)
    chambers = {c: ("Ctrl" if c % 2 else "Exp") for c in range(1, 7)}
    cfg = {"global": {"transform_licks": False, "params": dict(_PARAMS), **global_cfg},
           "dfms": [{"id": d.dfm_id, "chambers": dict(chambers)} for d in spec.dfms]}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def _load(root: Path):
    with contextlib.redirect_stdout(io.StringIO()):
        return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


def test_the_shipped_progressive_ratio_refuses_a_closed_loop_training_interval(lab, tmp_path):
    """Scenario 1 under the shipped type fails to load, naming what ran;
    lint says the same."""
    spec, _results = _recording("choice")
    cfg = pr_config([{"id": d.dfm_id, "paired_chambers": [1, 3, 5],
                      "chambers": {1: "C", 2: "C", 3: "E", 4: "E", 5: "T", 6: "T"}}
                     for d in spec.dfms])
    root = tmp_path / "pr"
    _write(root, "choice", {})
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    with pytest.raises(ValueError, match="runs ClosedLoop"):
        _load(root)
    errors = [i.message for i in lint_flic_config(root / "flic_config.yaml")
              if i.severity == "error"]
    assert any("runs ClosedLoop" in m and "'ProgressiveRatio'" in m for m in errors)


def test_hedonic_refuses_a_lit_recording_and_lint_points_to_a_type_for_it(lab, tmp_path):
    root = _write(tmp_path / "hed", "fixed",
                  {"experiment_type": "Hedonic", "well_names": {"A": "S", "B": "Y"}})
    with pytest.raises(ValueError, match="expects no light"):
        _load(root)
    errors = [i.message for i in lint_flic_config(root / "flic_config.yaml")
              if i.severity == "error"]
    assert any("Experiment Type Editor" in m for m in errors)
    ## optogenetics: no keeps the program unread, so nothing is checked.
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"]["optogenetics"] = False
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    assert _load(root).experiment_type.name == "Hedonic"


def test_a_lab_type_loads_from_its_copy_and_lint_says_when_it_has_none(lab, tmp_path):
    definition, _ = _definition(name="HedonicFixedRatio", light=["FixedRatio"])
    root = _write(tmp_path / "lab", "fixed", {"experiment_type": "HedonicFixedRatio",
                                              "well_names": {"A": "S", "B": "Y"}})
    library.save_to_library(definition)
    warnings = [i.message for i in lint_flic_config(root / "flic_config.yaml")
                if i.severity == "warning"]
    assert any("data carries no copy" in m for m in warnings)
    library.write_copy(definition, root)
    e = _load(root)
    assert e.experiment_type.name == "HedonicFixedRatio"
    assert e.experiment_type.resolved_from == "copy"
    assert type(e).__name__ == "HedonicFeedingExperiment"
    assert not any("data carries no copy" in i.message
                   for i in lint_flic_config(root / "flic_config.yaml"))


def test_every_two_well_type_applies_the_duration_and_events_cutoffs(lab, tmp_path):
    """Custom two-well used to ignore the cutoffs the Config Editor showed."""
    plain = _load(_write(tmp_path / "plain", "fixed", {"chamber_layout": "two_well",
                                                        "optogenetics": False}))
    plain.auto_remove_chambers()
    assert "Two-well filter" not in plain.filter_criteria_summary
    cut = _load(_write(tmp_path / "cut", "fixed", {
        "chamber_layout": "two_well", "optogenetics": False,
        "constants": {"max_events_cutoff": 0}}))
    removed = cut.auto_remove_chambers()
    assert "Two-well filter" in cut.filter_criteria_summary
    assert removed["Reason"].str.contains("> max_events_cutoff=0").any()
