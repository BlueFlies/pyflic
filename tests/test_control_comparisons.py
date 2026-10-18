"""Control Comparisons: what an Experiment Type's report leads with (ADR-0019).

A Role comparison (two Roles from the Opto Program), a Treatment control
(each level of a factor against the Design's ``control_level``), or both;
Paired against Yoked is the paired − yoked comparison the reports already
make, moved to the front and not repeated.
"""

from __future__ import annotations

import contextlib
import io
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

import v4_fixtures as vf

from pyflic.base import control_comparisons as cc
from pyflic.base import report_layout as rl
from pyflic.base.experiment_types import library
from pyflic.base.experiment_types.definition import parse_definition
from pyflic.base.yaml_config import load_experiment_yaml

_PARAMS = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
           "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}
#: Chamber -> genotype on every DFM: each genotype has a Self chamber (1-3)
#: and an Unlit one (4-6) per DFM.
GENOTYPES = {1: "w1118", 2: "Gr5a", 3: "Gr64", 4: "w1118", 5: "Gr5a", 6: "Gr64"}


@pytest.fixture(autouse=True)
def lab(tmp_path, monkeypatch) -> Path:
    folder = tmp_path / "library"
    folder.mkdir()
    monkeypatch.setenv(library.ENV_LIBRARY, str(folder))
    return folder


# ---------------------------------------------------------------------------
# The statistics, on frames
# ---------------------------------------------------------------------------

def _frame(rows):
    return pd.DataFrame(rows, columns=["Treatment", "Role", "Genotype", "Diet", "Licks"])


def test_role_rows_compare_the_two_roles_within_each_treatment():
    frame = _frame([("T1", "Self", "", "", v) for v in (10, 12, 14)]
                   + [("T1", "Unlit", "", "", v) for v in (4, 5, 6)]
                   + [("T2", "Self", "", "", 9), ("T2", "Unlit", "", "", 3),
                      ("T2", "Open", "", "", 50)])
    rows = cc.role_rows([("Whole recording", frame)], ("Self", "Unlit"), ["Licks"])
    by = {r["treatment"]: r for r in rows}
    assert by["T1"]["n_a"] == 3 and by["T1"]["n_b"] == 3
    assert by["T1"]["diff"] == pytest.approx(7.0) and by["T1"]["p"] < 0.05
    ## One chamber a side: described, not tested; the Open chamber is not counted.
    assert by["T2"]["n_b"] == 1 and np.isnan(by["T2"]["p"])
    assert cc.role_rows([("Whole recording", frame.drop(columns="Role"))],
                        ("Self", "Unlit"), ["Licks"]) == []


def test_control_rows_hold_the_other_factors_and_use_dunnett():
    rows = []
    for diet, shift in (("low", 0.0), ("high", 100.0)):
        for genotype, mean in (("w1118", 10.0), ("Gr5a", 20.0), ("Gr64", 10.5)):
            rows += [(f"{genotype}_{diet}", "", genotype, diet, shift + mean + d)
                     for d in (-1.0, 0.0, 1.0)]
    out = cc.control_rows([("Whole recording", _frame(rows))], "Genotype", "w1118",
                          factors=["Genotype", "Diet"], metrics=["Licks"])
    assert {(r["stratum"], r["level"]) for r in out} == {
        ("Diet low", "Gr5a"), ("Diet low", "Gr64"), ("Diet high", "Gr5a"),
        ("Diet high", "Gr64")}
    gr5a = next(r for r in out if r["level"] == "Gr5a" and r["stratum"] == "Diet high")
    ## Held at the same diet: the 100-lick shift between diets is not a difference.
    assert gr5a["diff"] == pytest.approx(10.0) and gr5a["test"] == "Dunnett"
    assert gr5a["p"] < 0.05
    gr64 = next(r for r in out if r["level"] == "Gr64" and r["stratum"] == "Diet low")
    assert gr64["p"] > 0.05


def test_a_paired_yoked_role_pair_is_recognised_in_either_order():
    assert cc.is_paired_yoked(("Yoked", "Paired"))
    assert not cc.is_paired_yoked(("Self", "Unlit")) and not cc.is_paired_yoked(None)


def test_no_control_level_is_a_callout_not_a_table():
    blocks = cc.control_blocks([("Whole recording", _frame([]))], "Genotype", None)
    assert isinstance(blocks[1], rl.Callout) and "control_level" in blocks[1].text


# ---------------------------------------------------------------------------
# The reports, on simulated firmware 4.0.0 recordings
# ---------------------------------------------------------------------------

def _self_unlit_spec(minutes: float = 8.0, dfm_ids=(1, 2)) -> vf.RecordingSpec:
    """ClosedLoop with chambers 1-3 triggering at their A wells, each lit by
    its own fly (Self), and chambers 4-6 all Off (Unlit)."""
    thresholds = (20, vf.OFF) * 3 + (vf.OFF, vf.OFF) * 3
    intervals = (vf.IntervalSpec("Closed", True, thresholds, minutes),)
    return vf.RecordingSpec(
        start=vf.START, duration_min=minutes, paradigms={"Closed": vf.CLOSED},
        dfms=tuple(vf._healthy_dfm(d, intervals, minutes, 7) for d in dfm_ids), seed=7)


@lru_cache(maxsize=None)
def _recording(name: str):
    spec = {"self_unlit": _self_unlit_spec,
            "yoked": lambda: vf.yoked_controls_spec(minutes=8.0)}[name]()
    return spec, vf.simulate(spec)


def _lab_type(name: str, **fields) -> None:
    data = {"name": name, "chamber_layout": "two_well", "light": ["ClosedLoop"],
            "required_wells": ["A", "B"], "modules": ["yoked"]}
    data.update(fields)
    definition, problems = parse_definition(data)
    assert problems == []
    library.save_to_library(definition)


def _experiment_dir(root: Path, name: str, type_name: str, *, factors: bool = True,
                    control: bool = True) -> Path:
    spec, results = _recording(name)
    root.mkdir(parents=True, exist_ok=True)
    vf.write_v4_recording(root / "data", spec, results=results)
    g = {"experiment_type": type_name, "transform_licks": False, "params": dict(_PARAMS),
         "well_names": {"A": "Sucrose", "B": "Yeast"}}
    if factors:
        g["experimental_design_factors"] = {"Genotype": ["w1118", "Gr5a", "Gr64"]}
        if control:
            g["control_level"] = "w1118"
    cfg = {"global": g, "dfms": [{"id": d.dfm_id, "chambers": dict(GENOTYPES)}
                                 for d in spec.dfms]}
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    library.write_copy(library.library_definition(type_name), root)
    return root


def _load(root: Path):
    with contextlib.redirect_stdout(io.StringIO()):
        return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


def _results_headings(doc) -> list[str]:
    """The level-2 headings after *Results*, in order."""
    blocks = doc.blocks
    start = next(i for i, b in enumerate(blocks)
                 if isinstance(b, rl.Heading) and b.text == "Results")
    return [b.text for b in blocks[start + 1:]
            if isinstance(b, rl.Heading) and b.level == 2]


def _report(e):
    from pyflic.base.pdf_report import build_experiment_report

    with contextlib.redirect_stdout(io.StringIO()):
        return build_experiment_report(e)


def test_the_experiment_report_leads_with_both_comparisons(tmp_path):
    _lab_type("SelfControl", factors=["Genotype"],
              control={"roles": ["Self", "Unlit"], "treatment": "Genotype"})
    e = _load(_experiment_dir(tmp_path / "exp", "self_unlit", "SelfControl"))
    summary = e.feeding_summary()
    assert set(summary["Role"]) == {"Self", "Unlit"}
    doc = _report(e)
    headings = _results_headings(doc)
    assert headings[:2] == ["Role comparison: Self against Unlit",
                            "Treatment control: Genotype against w1118"]
    ## The two lead figures draw.
    start = next(i for i, b in enumerate(doc.blocks)
                 if isinstance(b, rl.Heading) and b.text == "Results")
    end = next(i for i, b in enumerate(doc.blocks) if i > start + 1
               and isinstance(b, rl.Heading) and b.level == 2
               and not b.text.startswith(("Role comparison", "Treatment control")))
    plots = [b for b in doc.blocks[start:end] if isinstance(b, rl.Plot)]
    assert len(plots) == 2
    for plot in plots:
        assert plot.plot() is not None
    rows = cc.role_rows([("Whole recording", summary)], ("Self", "Unlit"))
    assert {r["treatment"] for r in rows} == {"w1118", "Gr5a", "Gr64"}
    assert all(r["n_a"] == 2 and r["n_b"] == 2 for r in rows)
    control = cc.control_rows([("Whole recording", summary)], "Genotype", "w1118",
                              factors=["Genotype"])
    assert {r["level"] for r in control} == {"Gr5a", "Gr64"}
    assert all(r["n"] == 4 and r["n_control"] == 4 for r in control)


def test_a_role_comparison_alone_and_a_treatment_control_alone(tmp_path):
    _lab_type("RoleOnly", control={"roles": ["Self", "Unlit"]})
    _lab_type("ControlOnly", factors=["Genotype"], control={"treatment": "Genotype"})
    roles = _results_headings(_report(_load(_experiment_dir(
        tmp_path / "r", "self_unlit", "RoleOnly", control=False))))
    assert roles[0] == "Role comparison: Self against Unlit"
    assert not any(h.startswith("Treatment control") for h in roles)
    control = _results_headings(_report(_load(_experiment_dir(
        tmp_path / "c", "self_unlit", "ControlOnly"))))
    assert control[0] == "Treatment control: Genotype against w1118"
    assert not any(h.startswith("Role comparison") for h in control)


def test_paired_against_yoked_leads_and_is_not_repeated(tmp_path):
    _lab_type("YokedLead", control={"roles": ["Paired", "Yoked"]})
    _lab_type("YokedPlain")
    lead = _results_headings(_report(_load(_experiment_dir(
        tmp_path / "lead", "yoked", "YokedLead", factors=False))))
    assert lead[0] == "Paired and yoked" and lead.count("Paired and yoked") == 1
    plain = _results_headings(_report(_load(_experiment_dir(
        tmp_path / "plain", "yoked", "YokedPlain", factors=False))))
    ## Without a control: block the report is as before, the yoked
    ## comparison after the light results.
    assert plain[0] != "Paired and yoked" and plain[-1] == "Paired and yoked"
    assert plain.count("Paired and yoked") == 1


def test_the_project_report_leads_with_the_pooled_comparisons(tmp_path):
    from pyflic.base.project import Project
    from pyflic.base.project_report import _results_blocks

    _lab_type("SelfControl", factors=["Genotype"],
              control={"roles": ["Self", "Unlit"], "treatment": "Genotype"})
    root = tmp_path / "proj"
    design = None
    for name in ("rep1", "rep2"):
        member = _experiment_dir(root / name, "self_unlit", "SelfControl")
        cfg = yaml.safe_load((member / "flic_config.yaml").read_text())
        design = design or cfg.pop("global")
        cfg.pop("global", None)
        (member / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
        (member / library.COPY_NAME).unlink()
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": design}}, sort_keys=False))
    library.write_copy(library.library_definition("SelfControl"), root)
    with contextlib.redirect_stdout(io.StringIO()):
        project = Project(root)
        for name in project.member_names:
            project.load_member(name, parallel=False,
                                use_disk_cache=False).execute_basic_analysis(skip_qc=True)
        summary, facet, _missing = project.combined_frames()
        blocks = _results_blocks(project, summary, facet)
    assert "Role" in summary.columns
    headings = [b.text for b in blocks if isinstance(b, rl.Heading) and b.level == 2]
    assert headings[:3] == ["Role comparison: Self against Unlit",
                            "Treatment control: Genotype against w1118", "Pooled figures"]
    rows = cc.role_rows(project._facet_frames(summary, facet), ("Self", "Unlit"))
    assert all(r["n_a"] == 4 and r["n_b"] == 4 for r in rows)
