# Review of the Slices work and the surfaces around it (2026-10-29)

**For:** the agent implementing the fixes. **Range reviewed:** `git diff b496326...77bb5e8`
(the one commit `slices!`, 57 files, +4979/−353) plus, at the owner's request, the pre-existing
user-input surfaces and the core analysis pipeline. **Branch:** `v4_Dev`.

Four reviewers ran in parallel, each read-only: **Standards** and **Spec** over the diff (the
`/code-review` axes, kept separate below and not re-ranked against each other), then **UI input**
and **Core analysis** over the wider code. Each finding has file:line, a trigger, a consequence
and a one-line fix. **V** = the reviewer verified it by running a probe or reading an output;
**R** = from reading only. Line numbers are as of `77bb5e8`; confirm each with a grep before
editing.

The spec the Spec axis checked against is ADR-0020
(`docs/adr/0020-slices-are-separate-analyses-of-part-of-a-recording.md`), the Slice entries in
`CONTEXT.md`, the help topic `pyflic/help/content/concepts-slices.md`, and the 21 numbered
decisions ("D1"–"D21") the owner agreed in the design session. Where a finding cites D*n*, that
is the decision number. There is no issue tracker in this repo.

## Before you start

- Python: `.venv/Scripts/python.exe` (system Python lacks pandas). Run tests from the repo root
  so `tests/conftest.py` isolates the user's `~/.config/pyflic/ui.json`; never bypass it. Set
  `QT_QPA_PLATFORM=offscreen` and `PYTHONIOENCODING=utf-8`.
- The full suite takes ~12 min: 1555 passed, 16 failed at `77bb5e8`. The 16 are pre-existing
  and not yours: `test_parity_r.py` (missing R data), `test_v4_fixtures.py::test_program_text_*`
  and `*_pymcus_*` (missing PyMCU), `test_project.py::test_a_project_key_cannot_escape_its_batch`,
  `test_layout_and_exclusion_sheet.py::test_rows_are_scoped_to_the_projects_actually_running`,
  `test_hub_batch_ui.py::test_the_preflight_previews_the_sheet_without_writing_it`,
  `test_hub_ribbon_ui.py::test_the_analysis_card_appears_only_with_a_project`,
  `test_opto_editors_ui.py::test_the_constants_are_written_only_when_set` and
  `::test_a_hidden_section_keeps_what_the_file_says`.
- Bash heredocs on this machine fail on a line mixing a backtick and an apostrophe; write scripts
  with the Write tool. Python's piped stdout is cp1252: set `PYTHONIOENCODING=utf-8`.
- Vocabulary is `CONTEXT.md`'s. Code comments: `##` for rationale, in the voice of the file.
- Real data to check against, read-only: `test_data/MBabap` (closed-loop paired/yoked Project,
  Slices `0_360` and `360_1440`, outputs present), `test_data/Scott/MBON02` (Progressive Ratio).
- Record user-visible changes in `CHANGELOG.md` and keep the help topics (the only copy of user
  prose) in step; `tests/test_help_refs.py` validates help references.

## Decisions the owner must make first

Do not decide these yourself; ask, then implement the answer.

1. **The fourth-root transform in differences and sums** (Core #2). With `transform_licks: true`,
   `dLicksA`, the yoked comparison's `dLicksA` and the two-well "total" Licks are built from
   transformed per-well values. Options: difference/sum raw counts and transform afterwards; or
   keep as is and label every such column as transformed. This changes numbers in existing
   outputs (MBON02, MBabap).
2. **`MeanTimeBtw` / `MedTimeBtw` sentinels** (Core #6): return NaN when no interval starts in the
   window, and whether the lead-in and tail gaps count as intervals. Both touch R parity.
3. **Generation-1 Progressive Ratio Test boundary** (Core #10): whether an onset on the first
   unflagged row is Training. Every Gen-1 breaking point may shift by one.
4. **Which constants a Slice may override** (Spec D12): keep the three, or add the
   `opto_*_fail_fraction` keys that decide the FAIL verdict `exclude_failed_opto_chambers` acts on.
5. **Defaults chosen during the build and never confirmed**: Analyze all / Batch runs cover every
   Slice; two analyses may not share an own exclusion group; the Config Editor refuses to save a
   config with invalid Slices (elsewhere it only warns); the Hub's Slice picker reloads the loaded
   member; `Experiment.load_slice` re-reads `project.yaml`.

---

## Standards

(`tests/test_help_refs.py` passes, 59/59.)

**Hard: documented standards**

- **S1. CONTEXT.md retires "replicate"** (Flagged ambiguities). `docs/slices-user-guide.md:18,
  237, 242, 246, 251, 253, 261` say "replicate(s)". Fix: "member" / "recording"; the guide itself
  turns those folders into Members.
- **S2. CONTEXT.md's Slice entry lists "range" under _Avoid_.** `docs/slices-user-guide.md:190`
  "with the range `(0, 360)`". Fix: "minutes `(0, 360]`". Judgement call:
  `pyflic/base/slices.py:110` `Slice.range_minutes` mirrors the loader kwarg; consider
  `clip_minutes`.
- **S3. ADR-0018, "a click and a script's step produce the same files".**
  `pyflic/base/hub.py:~1374` `_generate_plots_by_slice` re-implements the `run_plots` step's loop
  (`script_editor/runner.py:224-233`) instead of dispatching through `_run_experiment_action`.
  The Hub agent did this because the step's returned figures carry no Slice name, so the Hub
  cannot pick out the shown Slice's figures. Fix: have the runner (or `run_selection.run_plots`)
  put the Slice name in each figure title, then route the button through the step like Run QC
  and Run analysis.

**Judgement calls: baseline smells**

- **S4. Duplicated Code, not-covered handling**: `except SliceNotCovered → write_record(...,
  tolerance(exp.global_config)); log` at `run_selection.py:63`, `script_editor/runner.py:144`,
  `project.py:1005`. Fix: one `slices.record_not_covered(exp_dir, err, tol)`.
- **S5. Duplicated Code, "Whole recording"**: `slices.py:380`, `hub.py:133`, `qc_viewer.py:427`,
  `plot_editor.py:542` (and pre-existing `analytics.py:872`). Fix: import
  `slices.WHOLE_RECORDING_LABEL`.
- **S6. Duplicated Code, picker label**: `hub.py:138`, `qc_viewer.py:~632`, `plot_editor.py:544`
  (one vs two spaces). Fix: `Slice.label()`.
- **S7. Duplicated Code, group ordering/label**: `(own,) + also` in `slices.py:120`,
  `project.py:~655`, `yaml_config.py:~468`; `" + ".join(f"'{g}'")` in `yaml_config.py:201` and
  `experiment.py:131`. Fix: one `slices.exclusion_groups()` and `slices.groups_label()`.
- **S8. Duplicated Code, int-if-integer**: `slices.py:142, 419`, `migration_lint.py:144`,
  `config_editor.py:600`. Fix: one `slices.tidy_minute()`.
- **S9. Duplicated Code, try/except around `usable_slices`**: `hub.py:~2131`,
  `qc_viewer.py:~452`. `_parse` never raises; delete both wrappers.
- **S10. Speculative Generality, distrusting its own API**: `getattr(project, "slice")`,
  `hasattr(project, "not_covered")`, `getattr(project, "member_output_dir")` at
  `pubfigures.py:1083, 1090`, `project_report.py:250, 267, 307`. Every Project has these; call them.
- **S11. Data Clump**: `experiment.py:85` `load_options: dict` (nine loader kwargs rebuilt at
  `yaml_config.py:~686`); `experiment.py:78` `slice: Any`. Fix: a `LoadOptions` dataclass;
  `Slice | None` under `TYPE_CHECKING`.
- **S12. Feature Envy / layering**: `experiment.py:359` `load_slice` imports
  `project.read_design` and walks `experiment_dir.parent`: Experiment reaches up to Project.
  Fix: the Project supplies the reload (it owns the design). Note this exists to fix a real bug
  (a Selection tick after loading must reach the Slices a run loads next;
  `tests/test_slices.py::test_a_members_slice_reads_the_selection_ticked_since_it_loaded`), so
  keep that behaviour whichever layer owns it.
- **S13. Redundant mechanism**: `dfm.py:111` `EmptyRangeError.__reduce__` (so it pickles across
  the pool) *and* `yaml_config.py:~225` returning the error as a value to avoid raising. Keep one.
- **S14. Silent fallback vs "never silently"**: `slices.py:179` `also_exclude()` swallows
  `SliceError` → `()`; `:187` `tolerance()` defaults on garbage. Fix: surface both through
  `slice_problems`.
- **S15. Builtin shadowing**: the parameter `slice` (`yaml_config.py:246`, `experiment.py:78`;
  locals already use `the_slice`). No ruff config in the repo, so not enforced; rename or leave.

Clean: help/UI/test text (no _Avoid_ words), ADR-0005/0010/0019 consistency, `##` rationale
comments, `flush=True` prints, no new dependencies.

---

## Spec

(`tests/test_slices.py`: 38 passed.)

**(a) Missing or partial**

- **P1. D8 (every output records the definition).** Only `execute_basic_analysis` calls
  `write_slice_record` (`experiment.py:3157`). A QC-only run (`run_selection.run_qc`,
  `Experiment.write_qc_reports`) writes `slices/<name>/qc/` with no `slice.json`, so a later
  bound edit cannot be detected as stale for the QC, and `member_status` reads `covered=None`.
  Fix: call `exp.write_slice_record()` at the end of `run_qc` (`run_selection.py:417`). The
  Project level `<project>/slices/<name>/` records no definition either (`_SliceCoverage.csv`
  has none); partial by design, worth a line in the ADR.
- **P2. D16 (both stale conditions).** `project.py:954-960`: a record with `covered: false`
  sets `analyzed=False` and the `elif` skips `definition_changed`. Input: a 400-min Member
  recorded "not covered" for `end: 1440`; the Design is edited to `end: 360`; the Hub and the
  Project Report still say "not covered", and `not_covered()` / `combined_frames` keep trusting
  the old reason. Fix: check `definition_changed` before the `covered` branch in `member_status`
  and in `not_covered()`.
- **P3. D15 (writes only to the own group), QC Viewer whole-recording path.**
  `qc_viewer.py:2298-2301` `_active_group()` falls back to `"general"`, not the Design's
  `exclusion_group` (the viewer loads with `exclusion_group=None`). Pre-existing, sharpened by
  D15. Fix: `slices.whole_recording_group(self._exp.global_config)`. The Slice path is correct:
  the loader sets `exp.exclusion_group` to the Slice's own group even with no exclusions applied
  (`yaml_config.py:594`). See UI #1 for the loader-side fix that covers this too.

**(b) Not asked for**

- `docs/qc-user-guide.pdf` and `docs/slices-user-guide.pdf` committed as binaries. The owner
  prints these himself; leave them, but do not add more.
- `slices.py:59, 70, 223`: extra open-end spellings (`open`, `inf`, `""`), reserved names
  `whole/all/none`, and a list form of `slices:`. The spec says `end: end` and a mapping. Harmless;
  trim if the owner prefers one spelling.
- `dfm.py:244`: `(a, b]` clipping now applies to **every** range load (the QC Viewer time range,
  the `range_minutes` API), and an empty range now raises (`yaml_config.py:679`). ADR-justified
  (Facets use `(a, b]`), but a behaviour change beyond Slices; it is in the CHANGELOG.
- `experiment.py:255-263` `load_slice` re-reads `project.yaml`; the Hub picker reloads the loaded
  member (`hub.py:_on_slice_picked`). Implementation choices (owner decision 5).
- Chosen-not-confirmed defaults present: `Project.run_all(all_slices=True)` (`project.py:983`),
  own-group uniqueness (`slices.py:294`), Config Editor refuses invalid Slices
  (`config_editor.py` `_refuse_slices`). Owner decision 5.

**(c) Looks wrong or questionable**

- **P4. D12.** `AUTO_REMOVAL_CONSTANTS` (`slices.py:63`) is `min_untransformed_licks_cutoff`,
  `exclude_failed_opto_chambers`, `opto_unexplained_min_sec`. `auto_remove_chambers` reads
  `self.global_constants` (overrides layered correctly at `yaml_config.py:596`) and
  `opto_light.py:244` reads the same. But the FAIL verdict `exclude_failed_opto_chambers` acts on
  is decided by `opto_unexplained_fail_fraction` and the other `*_fail_fraction` keys
  (`opto_qc.py:85, 102-103`), which a Slice may not override, so the set is narrower than its own
  docstring ("the ones that decide which chambers auto-removal takes out"). Owner decision 4;
  then either add the keys or fix the docstring and help.
- **P5. D18.** `runner.py:511-517` `window_for` reads `step.get(key, script.get(key))`: a step
  with an explicit `start: 0, end: 0` under a windowed script now runs on the whole recording
  instead of being flagged. `ScriptContext.on_range` (`runner.py:55`) is dead. Fix: flag when
  the script states a window even if the step zeroes it; delete `on_range`.

Verified OK: D9/D10 (Hub "not covered" with the reason as tooltip; Project Report callouts and
the unequal-span warning), D11 (cutoff and Program Facets intersected, dropped ones listed in
`summary.txt`; the Ratio module refused), D13/D14, D17 (Selection boxes write `omit.slices`,
`_sync_in_memory` keeps the loaded member current, `each_slice` honours it), D18
(`run_in_experiments` loads the whole recording then `load_slice`), D19 (specs name `slice`; the
report draws from the view's frames), D21.

---

## UI input surfaces (beyond the diff)

Ranked by severity.

- **U1. WRONG RESULTS SILENTLY: a standalone `global.exclusion_group` is ignored by the Hub and
  QC Viewer loads but honoured by `Experiment.load_slice(None)`.** (V)
  `hub.py:2083-2094` `_load_standalone` passes no `exclusion_group` → `yaml_config.py:242`
  default `"general"`. `qc_viewer.py:373, 380` pass `exclusion_group=None` → `yaml_config.py:764`
  `exp.exclusion_group = None` → `qc_viewer.py:2301` `_active_group()` = `"general"`. But
  `experiment.py:364` resolves `whole_recording_group(global_config)`.
  Trigger: a config with `exclusion_group: main` and rows under both `main` and `general`. Hub
  load → group `general`; `exp.load_slice(None)` → `main`. So with the Hub showing a Slice, Run
  QC / Run analysis (`run_selection.py:56-62`) analyse the whole recording under `main`; showing
  the whole recording, under `general`. The QC Viewer seeds its ticks from, and Save Exclusions…
  defaults to, `general`, which a Slice-driven run never reads. A Member loaded through the
  viewer's Load tab (`Project.load_member(..., exclusion_group=None)`) likewise reads `general`,
  not the Design's group. The Config Editor now offers this field for standalone configs
  (`config_editor.py:2073-2082`) while the help (`config-structure.md:280`) says standalone is
  always `general`.
  Fix: in `load_experiment_yaml`, set `exp.exclusion_group = slices.whole_recording_group
  (global_cfg)` whenever the caller passes the default or `None` (as the Slice path does at
  `:372`), applying exclusions only when asked; `_active_group()` then follows. Have the Hub pass
  the group explicitly. Update the help line. This also closes Spec P3.
- **U2. DATA LOSS: the Config Editor's save drops `facet_cutoffs`, `facet_labels`, single-well
  `well_names`, per-DFM `well_names`, and any other global key it has no widget for.** (V)
  `config_editor.py:2802-2942` `_global_section` rebuilds from widgets; only the `constants`
  extras (`:2908`) and `omit` (`:2933`) are carried over; `well_names` is written only for two-well
  (`:2846`). `DFMWidget.get_dict` (`:1524-1561`) rebuilds entries and keeps nothing unknown.
  Round-trip fine: `facet_source`, `optogenetics`, `control_level`, `also_exclude`,
  `slice_tolerance_min`, `slices`, `paired_chambers`/`chamber_groups`, per-DFM physical `params`;
  `'0_360'` is quoted on dump.
  Fix: keep a `_MANAGED_GLOBAL_KEYS` set and `setdefault` every other loaded key at the end of
  `_global_section`; same in `get_dict` from the node it loaded.
  `test_keys_the_editor_knows_nothing_about_survive_a_save` covers top-level keys only; add
  global and per-DFM cases.
- **U3. DATA LOSS: QC Viewer "Save Exclusions…" accepts any group name and replaces that
  group's rows.** (R) `qc_viewer.py:2310-2339`; `exclusions.py:99` replaces all rows of the
  group. Loaded as Slice `early`, typing `general` overwrites the whole recording's declarations
  with `early`'s ticks (seeded from `early`, `:1964/:2308`).
  Fix: if the typed group is another analysis's own group (`slices.parse_slices(exp.global_config)`
  plus `whole_recording_group`), confirm with the count of rows that will be replaced; or offer
  only the active group and "new group".
- **U4. SILENT FILE WRITE and the scroll-wheel report: the wheel over `batch_script` rewrites
  `batch.yaml`, and every other Hub combo and spin box in a scrolling panel still reacts to the
  wheel.** (V: all change under a wheel event)
  `hub.py:524-533` → `_on_batch_script_changed` (`:2902`) → `save_batch_designation`. In the
  Project panel (the owner's report): `spin_workers` (`:798`), `project_script` (`:904`). Also
  `spin_binsize` (`:977`), `plot_metric` (`:1080`), `experiment_script` (`:1433`), `ai_provider`
  (`:1462`, which clears the model list via `_refresh_ai_models`), `ai_model` (`:1471`). The QC
  Viewer's `_start_spin`/`_end_spin` (`:541-551`) and Params spins (`:1790`), and the Plot
  Editor's spins (`:238-408`), sit in scroll areas too.
  Fix: add `NoWheelSpinBox` / `NoWheelDoubleSpinBox` beside `NoWheelComboBox` in
  `ui/widgets.py:518` and use them, plus `NoWheelComboBox`, for every control hosted in a
  `TilePanel` or `QScrollArea`. Extend
  `tests/test_hub_slices_ui.py::test_the_wheel_scrolls_past_every_slice_dropdown` to cover them.
- **U5. CONFUSING / LATENT: renaming a Slice keeps its old own group.** (V)
  `config_editor.py:732` fills Own group with the name; after editing Name, `get_values`
  (`:811`) writes `exclusion_group: <old name>` and no problem is reported. Removals keep going to
  the old group; a later Slice with the old name is refused.
  Fix: on `itemChanged` of column 0, if column 3 equals the previous name (keep it in
  `UserRole+1`), rename it too. Also rename the entry in `omit.slices`, which `validate_omit`
  otherwise flags as stale.
- **U6. Exclusion sheet: a blank or misspelt `group` is "applied" to a group nothing reads.** (R)
  `exclusion_sheet.py:45, 196` defaults to `general` regardless of the design's
  `exclusion_group`; `_evaluate_sheet` never compares the group with the member's analyses. The
  path-escape guard (`_inside`, `:215-223, :276, :292`) holds for absolute and `..` cells; type
  names are regex-guarded (`definition.py:76`).
  Fix: default a blank group to `whole_recording_group(design_for_member(member_dir))`; report
  rows whose group is in no analysis's `exclusion_groups` with a distinct status in the preflight.
- **U7. Plot Editor: a stale `spec.slice` previews the whole recording and is skipped on
  render.** (R) `plot_editor.py:626-629` falls back to index 0 but leaves `spec.slice`;
  `pubfigures.py:1235-1238` skips the figure with a log line.
  Fix: when `findData(spec.slice) < 0`, set `spec.slice = None` and say so in the preview.
- **U8. Lint gaps.** (V for a, b) (a) a Slice whose own group is another analysis's
  `also_exclude` group passes (`slices.py:294` checks own groups only); its QC Viewer saves then
  silently remove chambers from that analysis. (b) `slice_tolerance_min: five` or `-2` silently
  becomes 5.0 (`slices.py:187-194`), no lint (same as Standards S14). (c) `remove_chambers.csv`
  groups are never linted against the design. (d) `yaml_lint.py:480` resolves the design's type
  from the member dir, not the project dir. Already covered: unquoted numeric names,
  `end <= start`, duplicate own groups, a stale `omit.slices` name (`validate_omit`), a Member's
  own `slices:` (design match and the migration warning).
- **U9. Design dialog: `dir_edit.textChanged` → `_prefill_from_dir`** (`design_editor.py:225,
  843-881`) reloads the whole form when an intermediate typed path is an existing Project,
  discarding edits; `_loaded_constants` is never reset. Fix: use `editingFinished` and the Browse
  button.

Sound (no fix): `_on_slice_picked` (`hub.py:2199-2222`): a busy worker is refused and the picker
reset; an uncovered pick → `_say_not_covered` → refresh; a failed load → refresh; the open panel
is disabled during the load so no second pick; `done` discards after a Project change.
`SlicesWidget` refuses a negative start, `end <= start`, non-ASCII and case-duplicate names and an
own group equal to the whole recording's; tolerates trailing commas. `_write_yaml`'s badge and
refusal are correct. `_set_slice_included` syncs the three panels.

---

## Core analysis pipeline (beyond the diff)

Paths under `pyflic/base/`. The reviewer's probe scripts are in the session scratchpad
(`core_probe.py`, `probe_slice_baseline.py`, `light_cmp.py`, `pr_probe_*.py`); rebuild the
probes from `tests/test_slices.py::_write_csv`, `tests/v4_fixtures.py`, `tests/pr_fixtures.py`
when needed. Single test files run: `test_opto_qc_v4.py` (39 pass), `test_pr_v4.py` (40 pass).

- **C1. WRONG (data discarded): the Progressive Ratio Breaking Point is lost when only the Yoked
  chamber is excluded.** (V) `progressive_ratio_experiment.py:2587` skips a pair if *any* chamber
  lacks a treatment. Trigger: the Yoked chamber removed by the lick cutoff or
  `remove_chambers.csv`. Consequence: the Paired fly's row vanishes from `pr_breaking_point.csv`,
  the still-responding curve and the log-rank test, although the BP is defined from the Paired
  chamber alone. Fix: require only `treatment_for(dfm_id, layout.paired_chamber)`.
- **C2. WRONG SCALE: the fourth-root transform leaks into differences and sums.** (V) (a)
  `progressive_ratio_experiment.py:1489-1492` `paired_yoked_diff` differences the transformed
  facet summary: `dLicksA` = ¼-root(P) − ¼-root(Y) (MBON02: LicksA ≤ 9.5, dLicksA ±3.5), labelled
  "Δ Sucrose licks" (`report_content.py:33`); `zero_tests` and the mixed model run on it. (b)
  `analytics.py:943-1013` `yoked_comparison`, same (MBabap: dLicksA 1.02 on a 5.37 scale with
  `transform_licks: true`). (c) `analytics.py:612` `_resolve_metric_col` and `experiment.py:1470`
  'total' mode: pooled two-well "Licks" = LicksA^¼ + LicksB^¼. **Owner decision 1 first.** Fix
  per the decision: build diffs and sums from `transform_licks=False` summaries (e.g.
  `write_paired_yoked_diff(transform_licks=False)` at `:3176`) and transform afterwards, or label
  every such column as transformed.
- **C3. WRONG (silent diagnostics): the Emulated Trigger baseline is taken from the Slice's
  first 10 s.** (V) `opto_qc.py:966-988`: `start_idx = searchsorted(minutes, program_start)` is 0
  in any Slice with start > 0 and `approximate` stays False (the lag is computed from
  `recording_origin`). Consequence: `ContactSec`, `ContactWithoutActivitySec`,
  `UnexplainedWithContactSec` and `LikelyCause` change with no note (fixture: whole = 2003 s
  "drifting baseline", Slice (30, 0) = 794 s "hardware/linkage mismatch"; MBabap DFM 1 G2 4542 vs
  4447 summed). Fix: hand the pre-clip first-10-s raw mean to the DFM at load (as `recording_end`
  is), or set `approximate=True` with a note when the first loaded row is past the baseline window.
- **C4. WRONG (bounded): light already on at a Slice or window start is judged Unexplained.** (R)
  Gen 1 `opto_qc.py:1072` (`grace = ... if k > 0 else 0`); gen 3 `:1833-1861, 1884, 1930` (a
  clipped onset → the Activation is not in `owner`, judged `free`). Up to one Hold /
  ActivationMs per group of unexplained light at the Slice start; can cross
  `opto_unexplained_min_sec` on a quiet group. Fix: do not judge rows `[0, decay + tol)` of the
  first window, or light lit at row 0, until it first goes out.
- **C5. WRONG REMOVAL: Progressive Ratio training is read from the clipped frame.** (V)
  `dfm.py:421-463` detects the flag on the loaded rows; `progressive_ratio_experiment.py:393-397`
  then says "never carried the training flag" and `:1737` auto-removes the whole group. Trigger:
  any `range_minutes` start after a group's training end (Hub QC Viewer range or the API; PR has
  no Slices). Fix: detect the flag before clipping (as `recording_end` is), or refuse a non-zero
  start under the Ratio module.
- **C6. WRONG SENTINELS: `MeanTimeBtw` / `MedTimeBtw`.** (V) `dfm.py:1257-1271` returns 0.0 when
  no interval *starts* in the window; `algorithms/feeding.py:68-83` (`get_intervals`) counts the
  lead-in and tail gaps, so a well that never licks gets MeanTimeBtw = recording length (1800 s
  on a 30-min probe) while a well that licked only outside the window gets 0.0;
  `_duration_summary` returns NaN for the same case. These 0 s / full-length values enter
  treatment means and Welch/Tukey. **Owner decision 2 first.** Fix: return NaN when `tmp.empty`
  (and settle whether edge gaps are intervals; note R parity).
- **C7. WRONG ROWS: a Slice's `binned_feeding_summary.csv` starts at minute 0.** (V)
  `experiment.py:2380-2384` (`m_min = 0.0` when `range_minutes=(0, 0)`; `run_selection.py:197`
  passes `WHOLE_RECORDING`), same at `dfm.py:1449`. Slice "late" (10, end): bins `(0, 5]`,
  `(5, 10]` are emitted with Licks 0 and MeanTimeBtw 0. The plots are fine
  (`experiment.py:1319-1324` use the load range). Fix: default `m_min` to
  `self.range_minutes[0]` / the first loaded minute.
- **C8. WRONG LABELS: tidy exports assume the default `chamber_sets`.** (V) `dfm.py:1229-1243`
  `_chamber_from_well` / `_tcwell_from_well` use well parity; with `chamber_sets [[1,3],[2,4],…]`
  `duration_data()` labels well 3 as Chamber 2 / WellA (it is chamber 1's well B). Fix: map
  through `self.chambers`.
- **C9. PR light-QC warnings skewed.** (R) `progressive_ratio_experiment.py:896, 1071`:
  `lick_trend` / `estimate_increment` take every post-training event (post-restart Acclimation,
  past `pr_test_window_min`) while `_test_ledger_rows` (`:1039-1046`) is window-bounded →
  NO_TREND and increment skew. Fix: trend over Test-window events.
- **C10. Gen-1 Progressive Ratio boundary (owner decision 3).** (V, observation) `:772 / :792`
  file an onset as Test when `on_min > training_end`; in MBON02, 46 of 48 groups' first Test
  event is +1 sample, credited with 1-3 Training licks, `TrainingLightEvents` 8-9 for Training10,
  so every Gen-1 BreakingPoint may be +1. Fix if the owner agrees: classify an onset on the first
  unflagged row as Training (`> end + period`) when that pairing is Training's.
- **C11. Slice row-0 counts.** (R) `light_summary.py:276-278` `lit_before[0] = False` → a light
  already on counts as an onset (+1 `LightOnsets`); `ParadigmState.activation_onsets` never
  returns row 0 (−1 Activation). Fix: carry the pre-clip previous row's state (pairs with C3's
  "hand pre-clip state to the DFM" and C4).
- **C12. Moving windows overrun the recording.** (V) `dfm.py:1513-1526, 1618-1623`: starts
  `arange(m_min, m_max)` → the last window `(25, 35]` on a 30-min recording, labelled 35 with half
  the data. Fix: stop when `a + window_min > m_max`, or flag the partial window.
- **C13. Crash (edge).** (R) `dfm.py:1450-1463`: `m_min == m_max` → empty bins →
  `pd.concat([])` raises. Fix: guard as `experiment.py:2392` does.
- **C14. Cosmetic and inconsistencies.** (R unless noted) `windowing.py:208-216`
  `StartMin/EndMin` = (0, 0) for a Slice's whole summary and `EndMin = 0` on the tail Facet (V);
  `analytics.py:975-976` whole-recording `FacetRange "(0, 0)"` (V); `utils.py:34-35`
  `range_is_specified((-5, 5))` is False while `windowing.is_full_range` says otherwise (V);
  `project.py:1331-1341` Slice views lose phase labels (intersected windows ≠ design windows);
  `project.py:1052-1057` a Member with `feeding_summary.csv` but no `_facet.csv` is silently
  absent from the Facet stats (not in `missing`); `opto_qc.py:868-879` linkage inferred from the
  Slice's rows only; `:1233-1248` minute timelines start at 0; PR `:1409` training end rounded for
  Facets but exact elsewhere; PR `:1346` cache key crashes on a window list; PR `:1365 / :1420`
  recomputes the six-chamber summary three times per window.

Checked and fine: `(a, b]` consistent in the clip, `range_mask`, Facets and bins; `recording_end`
taken after the repeated-row drop and before the clip; a NaN `Seconds` row loads and summarises;
coverage / `EmptyRangeError` → `SliceNotCovered`; PI from raw counts, no double transform; the
clock schedule anchored at true minute 0 via `recording_origin`; LitFraction and unexplained
denominators per window, NaN on 0 min; the snapshot keeps removed chambers' treatment; the
first-gap rule and MBON02 ledger ↔ BP consistent; `_mixed_p` nests DFM in Experiment and returns
None for one Member; one treatment, an all-NaN metric and no covered Member are handled.

---

## Suggested order of work

A suggestion, grouped by consequence; the axes above are not re-ranked against each other.

1. **Numbers that are wrong today, no owner decision needed:** C1, C3, C4, C5, C7, C8, U1 (with
   Spec P3), P2, P1, C11, C12, C13.
2. **Data loss on save:** U2, U3, U5.
3. **Owner decisions, then:** C2, C6, C10, P4.
4. **The scroll wheel (the owner's open report):** U4.
5. **Spec gaps and lint:** P5, U6, U7, U8, U9, S14.
6. **Standards and tidying:** S1–S3 first (vocabulary in the guide; one code path for Generate
   plots), then S4–S13, S15 as judgement allows.

## What to test (add to `tests/`)

- A standalone config with `exclusion_group: main` and rows in both `main` and `general`: the Hub
  load, the QC Viewer Load tab, and `each_slice` from a Slice-loaded experiment all exclude
  `main`'s rows; `_active_group()` == `main` (U1, P3).
- Config Editor round-trip of a config with `facet_cutoffs`, `facet_labels`, single-well
  `well_names` and per-DFM `well_names` (U2).
- Wheel events on `spin_workers`, `project_script`, `batch_script` leave them unchanged and write
  no `batch.yaml` (U4).
- Rename a Slice row: `exclusion_group` and `omit.slices` follow when they equalled the name (U5).
- Save Exclusions… typing another analysis's own group asks first; a sheet row with a blank group
  under `exclusion_group: main` lands in `main` (U3, U6).
- A QC-only run of a Slice writes `slice.json`; a "not covered" record is re-judged after the
  Slice's bounds change (P1, P2).
- A PR pair with only the Yoked chamber excluded keeps its BP row (C1); diff tables built per the
  owner's transform decision and compared (C2).
- A Slice starting after 10 s: `ContactSec` / `LikelyCause` equal the whole-recording values over
  the same minutes; no unexplained light in the first Hold (C3, C4).
- A chamber with zero licks and one with licks only outside a Facet → `MeanTimeBtw` per the
  owner's decision, the same in both (C6).
- Slice "late"'s `binned_feeding_summary.csv` first `Interval` ≥ the Slice start; moving windows
  end ≤ the recording end (C7, C12).
- `chamber_sets [[1,3],…]` → `duration_data` Chamber / TCWell match `dfm.chambers` (C8).
