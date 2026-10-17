"""The light table (docs/v4-data-plan.md, stream 5: decisions 6, 9, 16, 17,
24 and 31).

Generation 3 from the firmware 4.0.0 simulator (``v4_fixtures``), whose
truth the table must reproduce; generation 1 from the existing optogenetic
and Progressive Ratio fixtures; generation 2 from the simulator's
un-updated-firmware writer.  Then everything that shows the table: the
feeding summary's Role / LitSec / Activations, basic analysis and the
script action, the experiment report, the Combined Analysis and the
Project Report, and the per-chamber light-phase summary.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
import pytest
import yaml

from pyflic.base import light_summary as ls
from pyflic.base import report_layout as rl
from pyflic.base.yaml_config import load_experiment_yaml

from opto_fixtures import make_opto_dir
from pr_fixtures import make_pr_experiment_dir
from v4_fixtures import (
    choice_pr_spec,
    fixed_ratio_spec,
    one_of_each_spec,
    simulate,
    write_gen2_recording,
    write_v4_recording,
)

RECORD_S = 0.2


def _config(dfm_ids, **extra) -> dict:
    params = {"feeding_threshold": 20, "feeding_minimum": 10, "tasting_minimum": 5,
              "tasting_maximum": 20, "samples_per_second": 5, "pi_direction": "left"}
    return {"global": {"chamber_layout": "two_well", "transform_licks": False,
                       "params": params, **extra},
            "dfms": [{"id": int(i), "chambers": {c: ("Ctrl" if c % 2 else "Exp")
                                                 for c in range(1, 7)}}
                     for i in dfm_ids]}


def _recording(root: Path, spec, results=None, *, writer=write_v4_recording,
               config_extra: dict | None = None, **kw) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    writer(root / "data", spec, results=results, **kw)
    cfg = _config([d.dfm_id for d in spec.dfms], **(config_extra or {}))
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    return root


def _load(root: Path):
    return load_experiment_yaml(root, parallel=False, use_disk_cache=False)


@lru_cache(maxsize=None)
def _one_of_each():
    spec = one_of_each_spec()
    return spec, simulate(spec)


@lru_cache(maxsize=None)
def _choice():
    spec = choice_pr_spec()
    return spec, simulate(spec)


@pytest.fixture(scope="module")
def each(tmp_path_factory):
    spec, results = _one_of_each()
    return _load(_recording(tmp_path_factory.mktemp("each"), spec, results)), results


#: one_of_each_spec: DFM -> its Paradigm type over the whole run.
EACH_TYPES = {1: "OpenLoop", 2: "ClosedLoop", 3: "FixedInterval", 4: "NonFeeding",
              5: ls.MIXED, 6: "FixedRatio"}
ACCLIMATION = ("AcclimationActivations", "AcclimationEndMin", "AcclimationComplete")
RATIO = ("FirmwareEvents", "LastRequirementMet", "ProgressAtEnd", "EventsPerActivation")


# ---------------------------------------------------------------------------
# Generation 3: the firmware's own counts
# ---------------------------------------------------------------------------

def test_one_row_per_chamber_with_the_truths_light_and_activations(each):
    """The plan's acceptance on one_of_each_spec(): one row per chamber, the
    right ParadigmType, LitSec within one record of the simulator's OnMs
    total, Activations equal to the truth."""
    e, results = each
    table = ls.light_summary(e)
    assert list(table.columns) == list(ls.LIGHT_CHAMBER_COLUMNS)
    assert len(table) == 36 and not table.duplicated(["DFM", "Chamber"]).any()
    for row in table.itertuples(index=False):
        truth = results[row.DFM].truth
        a, b = 2 * row.Chamber - 1, 2 * row.Chamber
        assert row.ParadigmType == EACH_TYPES[row.DFM], row
        assert row.Generation == 3 and row.LitSource == ls.SOURCE_ON_MS
        ## Linked wells share one light: the chamber's is the larger total.
        lit = max(truth.on_ms_total[a], truth.on_ms_total[b]) / 1000.0
        assert abs(row.LitSec - lit) <= RECORD_S, row
        assert row.Activations == len(truth.activation_onset_ms[a]) + \
            len(truth.activation_onset_ms[b]), row
    assert table.loc[table.DFM == 5, "Paradigm"].eq(ls.MIXED).all()
    assert table.loc[table.DFM == 2, "Paradigm"].eq("Closed").all()


def test_the_type_specific_columns_are_na_off_type(each):
    e, _results = each
    table = ls.light_summary(e).set_index(["DFM", "Chamber"])
    na = table.isna() | table.apply(lambda c: c.map(lambda v: v is None))
    for dfm in range(1, 7):
        rows = na.xs(dfm, level="DFM")
        ratio = dfm in (5, 6)
        acclimation = dfm == 5                   # PR10 has Acclimation 10; FR5 none
        assert rows[list(RATIO)].any().any() == (not ratio), dfm
        assert rows[list(ACCLIMATION)].any().any() == (not acclimation), dfm
        assert rows["LockedOutContactSec"].all() == (dfm != 3), dfm
        assert rows["UnlitSec"].all() == (dfm != 4) and rows["Suppressions"].all() == (dfm != 4)
        ## Read for every type: Activations, light and pyflic's events.
        assert not rows[["Activations", "LitSec", "LightOnsets", "EventsA"]].any().any()


def test_each_well_matches_the_firmware(each):
    e, results = each
    wells = ls.light_wells(e)
    assert list(wells.columns) == list(ls.LIGHT_WELL_COLUMNS)
    assert len(wells) == 72
    for row in wells.itertuples(index=False):
        truth = results[row.DFM].truth
        assert row.LitSec == pytest.approx(truth.on_ms_total[row.Well] / 1000.0)
        assert row.Activations == len(truth.activation_onset_ms[row.Well])
        if row.DFM == 5 and row.Well % 2:
            ## PR10's trigger wells: Acclimation from the Phase, the last
            ## Requirement from the row before the Activation.
            end = truth.acclimation_end_ms[row.Well]
            assert end is not None and row.AcclimationComplete is True
            assert abs(row.AcclimationEndMin * 60000.0 - end) <= 2 * 200
            assert row.AcclimationActivations == 10
            met = [m for m in truth.requirement_met[row.Well] if m is not None]
            assert row.LastRequirementMet == met[-1]
            assert row.FirmwareEvents >= sum(met)
            assert row.EventsPerActivation == pytest.approx(row.FirmwareEvents / len(met))
        if row.DFM == 6 and row.Well % 2:
            assert row.LastRequirementMet == 5      # FR5: a constant Requirement


def test_without_a_program_the_type_dependent_columns_are_na(tmp_path):
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results, program=False))
    assert e.opto_program is None and e.is_optogenetic
    table = ls.light_summary(e)
    assert table["ParadigmType"].isna().all()
    for column in (*RATIO, *ACCLIMATION, "LockedOutContactSec", "UnlitSec", "Suppressions"):
        assert table[column].isna().all(), column
    ## The rows still name their Paradigm, and the firmware still counted.
    assert set(table["Paradigm"]) == {ls.MIXED}
    truth = results[1].truth
    first = table[(table.DFM == 1) & (table.Chamber == 1)].iloc[0]
    assert first.Activations == len(truth.activation_onset_ms[1])
    ## Roles from the data: the dead-LED chamber never lit.
    assert first.Role == "Self"
    assert table[(table.DFM == 1) & (table.Chamber == 4)].Role.item() == "Unlit"


def test_a_window_holds_its_own_paradigm(tmp_path):
    """choice_pr_spec runs Closed for five minutes, then PR10: a window
    inside PR10 names it alone, the whole run is mixed."""
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results))
    late = ls.light_summary(e, range_minutes=(10, 30))
    assert set(late["Paradigm"]) == {"PR10"} and set(late["ParadigmType"]) == {
        "ProgressiveRatio"}
    assert set(late["ProgramInterval"]) == {2}
    early = ls.light_summary(e, range_minutes=(1, 4))
    assert set(early["ParadigmType"]) == {"ClosedLoop"}
    assert early[list(RATIO)].isna().all().all()
    ## The never-training chamber stays in Acclimation: no end, not complete.
    never = late[(late.DFM == 1) & (late.Chamber == 5)].iloc[0]
    assert never.AcclimationComplete is False and pd.isna(never.AcclimationEndMin)


# ---------------------------------------------------------------------------
# Generations 1 and 2: OptoCol1 only
# ---------------------------------------------------------------------------

def test_generation_1_reads_optocol1(tmp_path):
    e = _load(make_opto_dir(tmp_path / "exp"))
    wells = ls.light_wells(e).set_index("Well")
    assert set(wells["LitSource"]) == {ls.SOURCE_OPTOCOL1}
    assert set(wells["Generation"]) == {1}
    for column in ("Activations", "ActivationsPerHour", *RATIO, *ACCLIMATION):
        assert wells[column].isna().all(), column
    lights = e.dfms[1].lights_df
    for well in range(1, 13):
        assert wells.loc[well, "LitSec"] == pytest.approx(lights[f"W{well}"].sum() / 5.0)
    ## Well 5 is lit throughout, well 6 the first half: one onset each.
    assert wells.loc[5, "LitFraction"] == pytest.approx(1.0, abs=1e-3)
    assert wells.loc[5, "LightOnsets"] == 1 and wells.loc[6, "LightOnsets"] == 1
    assert wells.loc[1, "LightOnsets"] == 20         # twenty closed-loop bouts
    assert wells.loc[8, "LitSec"] == 0 and wells.loc[8, "LightOnsets"] == 0
    ## The program's clock schedule names the Paradigm on generation 1.
    assert set(wells["ParadigmType"]) == {"ClosedLoop"}
    assert set(wells["ProgramInterval"]) == {1}


def test_generation_2_has_light_and_no_firmware_columns(tmp_path):
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results, writer=write_gen2_recording))
    table = ls.light_summary(e)
    assert set(table["Generation"]) == {2} and set(table["LitSource"]) == {"OptoCol1"}
    assert table["Activations"].isna().all() and table["FirmwareEvents"].isna().all()
    assert (table["LitSec"] > 0).any()
    assert ls.has_generation_2(table)
    assert ls.no_training_information(e)


# ---------------------------------------------------------------------------
# Facets
# ---------------------------------------------------------------------------

def test_the_facet_tables_partition_the_whole(tmp_path):
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results,
                         config_extra={"facet_cutoffs": [10]}))
    whole = ls.light_summary(e).set_index(["DFM", "Chamber"])
    facet = ls.light_summary_facet(e)
    assert list(facet.columns[:2]) == ["Facet", "FacetRange"]
    assert list(dict.fromkeys(facet["Facet"])) == e.facet_labels()
    summed = facet.groupby(["DFM", "Chamber"])[["LitSec", "Activations"]].sum()
    pd.testing.assert_frame_equal(summed, whole[["LitSec", "Activations"]],
                                  check_exact=False, atol=1e-9)
    wells = ls.light_wells_facet(e)
    assert len(wells) == 2 * len(ls.light_wells(e))
    ## Unfaceted: nothing, as feeding_summary_facet.
    e.facet_cutoffs = None
    e.config["global"].pop("facet_cutoffs", None)
    assert ls.light_summary_facet(e).empty


def test_per_dfm_windows_are_used_when_the_experiment_has_them(tmp_path, monkeypatch):
    """Program Facets (stream 5b) give each DFM its own windows through
    ``facet_windows_for``; the light table takes them when it exists."""
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results))
    seen: list[int] = []

    def facet_windows_for(self, dfm_id):
        seen.append(dfm_id)
        return [("Closed", (0.0, 5.0)), ("PR10", (5.0, float("inf")))]

    monkeypatch.setattr(type(e), "facet_windows_for", facet_windows_for, raising=False)
    table = ls.light_summary_facet(e)
    assert seen == [1, 2]
    assert list(dict.fromkeys(table["Facet"])) == ["Closed", "PR10"]
    assert set(table.loc[table.Facet == "Closed", "ParadigmType"]) == {"ClosedLoop"}
    assert set(table.loc[table.Facet == "PR10", "ParadigmType"]) == {"ProgressiveRatio"}


def test_a_facet_of_several_windows_pools_them(tmp_path, monkeypatch):
    """A Program Facet pooling a Repeating program's Cycles is a label with
    a list of (a, b] windows (stream 5b's ``facet_windows_for``); the light
    table takes the list as one window, as the feeding summary does."""
    spec, results = _choice()
    e = _load(_recording(tmp_path / "exp", spec, results))
    windows = [(1.0, 3.0), (6.0, 9.0), (20.0, float("inf"))]
    pooled = ls.light_summary(e, range_minutes=windows).set_index(["DFM", "Chamber"])
    parts = [ls.light_summary(e, range_minutes=(a, 0.0 if b == float("inf") else b))
             .set_index(["DFM", "Chamber"]) for a, b in windows]
    for column in ("LitSec", "Activations", "LightOnsets", "FirmwareEvents", "WindowMinutes",
                   "EventsA"):
        total = sum(p[column].fillna(0) for p in parts)
        assert (pooled[column].fillna(0) - total).abs().max() < 1e-9, column
    assert set(pooled["Paradigm"]) == {ls.MIXED}
    ## The feeding summary's light columns take the same list.
    fs = e.feeding_summary()
    redone = ls.with_light_columns(e, fs, windows).set_index(["DFM", "Chamber"])
    for column in ("LitSec", "Activations"):
        assert (redone[column] - pooled.loc[redone.index, column]).abs().max() < 1e-9

    def facet_windows_for(self, dfm_id):
        return [("Early", [(1.0, 3.0), (6.0, 9.0)]), ("Late", [(20.0, float("inf"))])]

    monkeypatch.setattr(type(e), "facet_windows_for", facet_windows_for, raising=False)
    facet = ls.light_summary_facet(e)
    assert list(dict.fromkeys(facet["Facet"])) == ["Early", "Late"]
    early = facet[facet.Facet == "Early"].set_index(["DFM", "Chamber"])
    assert early["FacetRange"].iloc[0].count("(") == 2
    expected = (parts[0]["LitSec"] + parts[1]["LitSec"])
    assert (early["LitSec"] - expected.loc[early.index]).abs().max() < 1e-9


def test_facet_windows_prefers_a_per_dfm_form():
    class Exp:
        dfms = {}

        def facet_windows_for(self, dfm_id):
            return [("A", (0, 5))]

        def facet_labels(self):
            raise AssertionError("the shared windows are not read")

    assert ls.facet_windows(Exp(), 1) == [("A", (0, 5), None)]


# ---------------------------------------------------------------------------
# Progressive Ratio keeps its own Role and windows
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def pr(tmp_path_factory):
    return _load(make_pr_experiment_dir(tmp_path_factory.mktemp("pr")))


def test_progressive_ratio_keeps_its_role_and_group_windows(pr):
    assert ls.type_owns_role(pr)
    table = ls.light_summary(pr)
    assert set(table["Role"]) == {"paired", "yoked"}
    for row in table.itertuples(index=False):
        assert row.Role == pr.role_of(row.DFM, row.Chamber).role
    facet = ls.light_summary_facet(pr)
    assert set(facet["Facet"]) == {"Training", "Test"}
    assert list(dict.fromkeys(facet["Facet"])) == ["Training", "Test"]
    ## Each Chamber Group splits at its own training end.
    for (dfm, chamber), rows in facet.groupby(["DFM", "Chamber"]):
        group = pr.role_of(dfm, chamber).group
        windows = dict(pr.group_windows(dfm, group))
        assert set(rows["Facet"]) == set(windows)
    fs = pr.feeding_summary()
    assert {"Group", "Role", "TrainingMinutes", "LitSec", "Activations"} <= set(fs.columns)
    assert set(fs["Role"]) == {"paired", "yoked"}
    assert fs["Activations"].isna().all()           # generation 1: no Activations
    ## For comparing light behaviour, a yoked fly's light is its partner's.
    kept = ls.behaviour_rows(table)
    assert set(kept["Role"]) == {"paired"} and len(kept) == len(table) // 2


# ---------------------------------------------------------------------------
# The feeding summary's light columns
# ---------------------------------------------------------------------------

def test_the_feeding_summary_carries_role_litsec_and_activations(each):
    e, results = each
    fs = e.feeding_summary()
    columns = list(fs.columns)
    assert columns.index("Role") == columns.index("Chamber") + 1
    assert columns.index("LitSec") == columns.index("OptoOn_sec_B") + 1
    assert columns.index("Activations") == columns.index("LitSec") + 1
    table = ls.light_summary(e).set_index(["DFM", "Chamber"])
    for row in fs.itertuples(index=False):
        assert row.Role == table.loc[(row.DFM, row.Chamber), "Role"]
        assert row.LitSec == pytest.approx(table.loc[(row.DFM, row.Chamber), "LitSec"])
        assert row.Activations == table.loc[(row.DFM, row.Chamber), "Activations"]
    ## A window computes its own.
    window = e.feeding_summary(range_minutes=(0, 10))
    assert (window["Activations"] <= fs["Activations"].to_numpy()).all()


def test_the_light_columns_are_redone_on_a_cache_hit(each):
    """A summary read back from the disk cache carries whatever its light
    columns said when it was written."""
    e, _results = each
    fresh = e.feeding_summary()
    key = ((0.0, 0.0), bool(e.transform_licks))
    stale = e._feeding_summary_cache[key].copy()
    stale["Role"] = "Stale"
    stale["LitSec"] = -1.0
    e._feeding_summary_cache[key] = stale
    try:
        again = e.feeding_summary()
    finally:
        e._feeding_summary_cache.pop(key)
    pd.testing.assert_frame_equal(again, fresh)


def test_a_dark_experiment_gains_nothing(tmp_path):
    e = _load(make_opto_dir(tmp_path / "dark", program=None, light_cases=False))
    assert not e.is_optogenetic
    assert not set(ls.FEEDING_COLUMNS) & set(e.feeding_summary().columns)
    assert ls.light_summary(e).empty


# ---------------------------------------------------------------------------
# Outputs: basic analysis, the script action, the experiment report
# ---------------------------------------------------------------------------

def test_basic_analysis_writes_the_four_tables(tmp_path):
    root = make_opto_dir(tmp_path / "exp")
    cfg = yaml.safe_load((root / "flic_config.yaml").read_text())
    cfg["global"]["facet_cutoffs"] = [30]
    (root / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    e = _load(root)
    result = e.execute_basic_analysis(skip_qc=True)
    analysis = root / "analysis"
    for key, name in ls.FILES.items():
        assert result[key] == (analysis / name).resolve(), key
    chambers = pd.read_csv(analysis / "light_summary.csv")
    assert list(chambers.columns) == list(ls.LIGHT_CHAMBER_COLUMNS)
    facet = pd.read_csv(analysis / "light_summary_facet.csv")
    assert set(facet["Facet"]) == set(e.facet_labels())
    fs = pd.read_csv(analysis / "feeding_summary.csv")
    assert {"Role", "LitSec", "Activations"} <= set(fs.columns)


def test_the_script_action_writes_and_is_gated(tmp_path):
    from pyflic.base.script_editor.actions import get_action
    from pyflic.base.script_editor.runner import run_experiment_script

    assert get_action("light_summary") is not None
    e = _load(make_opto_dir(tmp_path / "exp"))
    logs: list[str] = []
    run_experiment_script(e, {"name": "t", "steps": [{"action": "light_summary"}]},
                          log=logs.append)
    assert (Path(e.analysis_dir) / "light_summary.csv").is_file()
    assert (Path(e.analysis_dir) / "light_wells.csv").is_file()
    assert not (Path(e.analysis_dir) / "light_summary_facet.csv").exists()
    dark = _load(make_opto_dir(tmp_path / "dark", program=None, light_cases=False))
    logs.clear()
    run_experiment_script(dark, {"name": "t", "steps": [{"action": "light_summary"}]},
                          log=logs.append)
    assert any("[Skip] light_summary needs an optogenetic experiment" in m for m in logs)


def _headings(doc) -> list[str]:
    return [b.text for b in doc.blocks if isinstance(b, rl.Heading)]


def test_the_experiment_report_has_light_behaviour(each):
    from pyflic.base.pdf_report import build_experiment_report

    e, _results = each
    doc = build_experiment_report(e, metrics=())
    headings = _headings(doc)
    assert "Light behaviour" in headings
    assert headings.index("Light behaviour") > headings.index("Consumption")
    cover = next(b for b in doc.blocks if isinstance(b, rl.KeyValues))
    rows = dict(cover.rows)
    assert rows["Generation"].startswith("3 — 90 columns, firmware 4.0.0")
    assert rows["Lit time from"] == "OnMs, exact"


def test_a_dark_member_report_has_no_light_section(tmp_path):
    from pyflic.base.pdf_report import build_experiment_report

    e = _load(make_opto_dir(tmp_path / "dark", program=None, light_cases=False))
    doc = build_experiment_report(e, metrics=())
    assert "Light behaviour" not in _headings(doc)
    rows = dict(next(b for b in doc.blocks if isinstance(b, rl.KeyValues)).rows)
    assert rows["Generation"].startswith("1 — 27 columns")
    assert "Lit time from" not in rows


# ---------------------------------------------------------------------------
# Decision 24: the light-phase summary is per chamber
# ---------------------------------------------------------------------------

def test_the_light_phase_is_each_chambers_own(tmp_path):
    """Changed on purpose (decision 24): a chamber is in "light" when its own
    wells are lit, not whenever any LED of the DFM is.  In the generation-1
    opto fixture well 5 is lit throughout, so before this every chamber was
    in "light" for the whole hour."""
    from pyflic.base.analytics import light_phase_summary

    e = _load(make_opto_dir(tmp_path / "exp"))
    df = light_phase_summary(e)
    light = df[df.Phase == "light"].set_index("Chamber")["PhaseSeconds"]
    dark = df[df.Phase == "dark"].set_index("Chamber")["PhaseSeconds"]
    assert light.loc[5] == pytest.approx(3600.0)
    assert light.loc[6] == pytest.approx(1800.0)
    assert light.loc[8] == 0.0 and dark.loc[8] == pytest.approx(3600.0)
    assert light.loc[1] == pytest.approx(60.0)       # twenty bouts of 15 samples
    lights = e.dfms[1].lights_df
    for chamber in range(1, 13):
        assert light.loc[chamber] == pytest.approx(lights[f"W{chamber}"].sum() / 5.0)


def test_the_light_phase_reads_onms_on_generation_3(tmp_path):
    from pyflic.base.analytics import light_phase_summary

    spec = fixed_ratio_spec(minutes=10.0)
    e = _load(_recording(tmp_path / "exp", spec))
    df = light_phase_summary(e)
    on_ms = e.dfms[1].paradigm.on_ms
    light = df[df.Phase == "light"].set_index("Chamber")["PhaseSeconds"]
    for chamber in range(1, 7):
        wells = [2 * chamber - 2, 2 * chamber - 1]
        assert light.loc[chamber] == pytest.approx((on_ms[:, wells] > 0).any(axis=1).sum() / 5.0)


# ---------------------------------------------------------------------------
# The Project
# ---------------------------------------------------------------------------

def _project(root: Path, members: dict, *, design_extra: dict | None = None):
    """A Project of one-DFM members, each recorded by ``write(data_dir)``,
    every member's basic analysis run."""
    from pyflic.base.project import Project

    design = None
    for name, write in members.items():
        member = root / name
        member.mkdir(parents=True)
        write(member / "data")
        cfg = _config([1])
        design = cfg.pop("global")
        (member / "flic_config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    design.update(design_extra or {})
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": design}}, sort_keys=False))
    project = Project(root)
    for name in project.member_names:
        project.load_member(name, parallel=False,
                            use_disk_cache=False).execute_basic_analysis(skip_qc=True)
    return project


@pytest.fixture(scope="module")
def gen3_project(tmp_path_factory):
    root = tmp_path_factory.mktemp("proj") / "proj"
    return _project(root, {
        "rep1": lambda data: write_v4_recording(data, fixed_ratio_spec(minutes=10.0, seed=7)),
        "rep2": lambda data: write_v4_recording(data, fixed_ratio_spec(minutes=10.0, seed=8)),
    }, design_extra={"facet_cutoffs": [5]})


def test_the_combined_analysis_stacks_the_light_tables(gen3_project):
    project = gen3_project
    written = {Path(p).name for p in project.build_combined_analysis()["written"]}
    assert {"proj_LightSummary.csv", "proj_LightWells.csv", "proj_LightSummary_Facet.csv",
            "proj_LightWells_Facet.csv"} <= written
    stacked = pd.read_csv(Path(project.analysis_path) / "proj_LightSummary.csv")
    assert stacked.columns[0] == "Experiment"
    assert set(stacked["Experiment"]) == {"rep1", "rep2"} and len(stacked) == 12
    text = (Path(project.analysis_path) / "proj_Stats.txt").read_text(encoding="utf-8")
    assert "Light behaviour (optogenetic members; one observation per chamber)" in text
    block = text[text.index("Light behaviour"):]
    for metric in ("Activations", "LitSec", "FirmwareEvents"):
        assert metric in block
    rows = project.light_comparison_rows()
    assert {r["phase"] for r in rows} == {"0-5 min", "5+ min"}
    assert {"Activations", "LitSec", "FirmwareEvents"} <= {r["metric"] for r in rows}
    assert {r["n_a"] + r["n_b"] for r in rows} == {12}


def test_the_project_report_has_light_behaviour(gen3_project):
    from pyflic.base.project_report import build_project_report, member_table

    project = gen3_project
    project.build_combined_analysis()
    doc = build_project_report(project)
    headings = _headings(doc)
    assert "Light behaviour" in headings
    assert headings.index("Light behaviour") > headings.index("Statistics")
    members = member_table(project)
    assert list(members["Generation"]) == ["3", "3"] and "Note" not in members.columns


def test_a_generation_2_member_is_named(tmp_path):
    from pyflic.base.project_report import member_table

    project = _project(tmp_path / "proj", {
        "new": lambda data: write_v4_recording(data, fixed_ratio_spec(minutes=6.0)),
        "old": lambda data: write_gen2_recording(data, fixed_ratio_spec(minutes=6.0)),
    })
    assert project.generation_2_members() == ["old"]
    assert project.member_generations("new") == [3]
    project.build_combined_analysis()
    text = (Path(project.analysis_path) / "proj_Stats.txt").read_text(encoding="utf-8")
    flagged = text[text.index("Flagged Chamber Groups"):text.index("Metric")]
    assert f"old [generation 2]: {ls.NO_TRAINING_INFORMATION}" in flagged
    assert "new [generation 2]" not in flagged
    members = member_table(project).set_index("Member")
    assert members.loc["old", "Generation"] == "2"
    assert members.loc["old", "Note"] == ls.NO_TRAINING_INFORMATION
    assert members.loc["new", "Note"] == ""


def test_a_progressive_ratio_member_on_old_firmware_is_named_by_its_facet(tmp_path):
    """A generation-2 Progressive Ratio member has one Facet, Recording
    (decision 15), whether or not it wrote a light table."""
    from pyflic.base.project import Project

    root = tmp_path / "proj"
    for name in ("a", "b"):
        (root / name / "analysis").mkdir(parents=True)
        (root / name / "flic_config.yaml").write_text(
            yaml.safe_dump({"dfms": [{"id": 1, "chambers": {1: "Ctrl"}}]}))
    pd.DataFrame({"Facet": ["Recording"], "DFM": [1]}).to_csv(
        root / "b" / "analysis" / "feeding_summary_facet.csv", index=False)
    (root / "project.yaml").write_text(yaml.safe_dump(
        {"name": "proj", "design": {"global": {"chamber_layout": "two_well"}}}))
    assert Project(root).generation_2_members() == ["b"]


def test_no_training_information_asks_the_type_first():
    class Asks:
        dfms: dict = {}

        def __init__(self, answer):
            self.answer = answer

        def training_information(self):
            return self.answer

    assert ls.no_training_information(Asks("none"))
    assert ls.no_training_information(Asks("no training information: recorded with ..."))
    assert not ls.no_training_information(Asks("phase"))

    class Dfm:
        training_info = "none"

    class Plain:
        dfms = {1: Dfm()}

    assert ls.no_training_information(Plain())


def test_the_light_figures_draw_from_the_stacked_table(gen3_project):
    from pyflic.base import pubfigures

    project = gen3_project
    project.build_combined_analysis()
    assert pubfigures.has_light_table(project)
    offered = pubfigures.plots_for_layout("two_well", None, light=True)
    for plot_id in ("faceted_activations", "faceted_litsec", "faceted_firmwareevents",
                    "faceted_acclimationendmin"):
        assert plot_id in offered and plot_id not in pubfigures.plots_for_layout("two_well")
        assert pubfigures.source_of(plot_id) == pubfigures.SOURCE_LIGHT
    source = pubfigures.frame_for("faceted_activations", None, None, project)
    data = pubfigures.faceted_data(source, "Activations", pubfigures.facet_order(source))
    assert set(data["Phase"].astype(str)) == {"0-5 min", "5+ min"}
    ## The general Role is a filter, never a panel.
    assert "Role" not in data.columns
    spec = pubfigures.default_spec("faceted_activations")
    pubfigures.build_figure("faceted_activations", data, spec, pubfigures.PlotStyle())
