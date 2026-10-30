# Slices: analysing part of a recording on its own

This guide is for researchers who used an earlier pyflic: the version that wrote ranged runs
into `flic_config_results/analysis_0_360/` and similar folders. It explains how to get the
same analyses now, with **Slices**. It covers setting them up in the app, giving each one the
right excluded chambers, running them, and finding their results.

You can do everything here in the app. Appendix A shows the same settings as they are
written in the configuration files, and Appendix B covers scripts, the command line and
Python. For a short reference, see the help topic *Slices* (`pyflic help`, or **F1**).

---

## 1. What changed

Earlier pyflic analysed a time range by loading only those minutes, from a script step with
a start and an end time, and applied an exclusion group to it. Each range got its own
results folder, and the recordings were pooled afterwards, by hand or in R.

A **Slice** is the same analysis, set up once for the whole Project:

| Before | Now |
|---|---|
| A script step loading minutes 0 to 360 | A Slice `0_360`, set up in the Project's design |
| A script step applying the group `Remove_6hr` | The Slice's **Own group**, `Remove_6hr` |
| `flic_config_results/analysis/` | `analysis/`: the whole recording, unchanged |
| `flic_config_results/analysis_0_360/` | `slices/0_360/analysis/` and `slices/0_360/qc/` |
| Pooling the ranges in R | One Combined Analysis and one Project Report per Slice |

The whole recording is always analysed as well; you do not set it up.

---

## 2. Setting up Slices

Slices belong to the Project's design, so every member runs every Slice.

1. In the Hub's **Project** panel, open the Project and click **Project design…**. For a
   new Project, use **Create project…** or **Initialize existing directory…** instead.
2. In the **Slices** card, click **Add Slice** and fill in the row:

   | Column | What to enter |
   |---|---|
   | **Name** | Names the Slice and its folder: letters, digits, `_` and `-`, for example `0_360` or `first_6h` |
   | **Start (min)** | The first minute. Blank is 0 |
   | **End (min)** | The last minute, or `end` (or blank) for the end of each recording |
   | **Own group** | The exclusion group this Slice uses and saves to (section 3). It shows the Slice's name until you change it |
   | **Also exclude** | Other exclusion groups this Slice also leaves out, separated by commas (section 3) |
   | **Min licks** | This Slice's own lick cutoff for automatic removal; blank keeps the design's, `off` turns it off |
   | **Opto failed**, **Unexplained (s)** | Optogenetic experiments only: whether chambers that fail the light QC are removed in this Slice, and its unexplained-light threshold. Blank keeps the design's |

3. Below the table, **Coverage tolerance (min)** says how far short of a Slice's end a
   recording may stop and still be included. The default is 5 minutes (section 7).
4. Click **Save**. If a row cannot be used, the window says why and does not save.

A few points:

- A Slice holds the minutes after its start, up to and including its end. So `0_360` and
  `360_1440` share no sample and lose none.
- Only the automatic-removal cutoffs can differ between Slices. Every other setting is the
  design's, so a Slice is the same analysis of fewer minutes. A 6-hour Slice may need a lower
  **Min licks** than the whole day.
- **Progressive Ratio and Fixed Ratio experiments have no Slices**, and the card is greyed
  out for them. Their Training and Test are split at each chamber group's own training end,
  which a Slice could cut through.
- **A standalone experiment** (not in a Project) has the same table in the Config Editor:
  **Experiment** tab, **Exclusion Groups and Slices** card.

---

## 3. Giving each Slice the right excluded chambers

Excluded chambers are still recorded in each member's `remove_chambers.csv`, under named
groups such as `Remove_6hr`. Each analysis — the whole recording, and each Slice — names the
groups it uses, in two ways:

| Field | That group's chambers are excluded | Excluding a chamber while viewing this analysis saves it here |
|---|---|---|
| **Own group** | yes | yes |
| **Also exclude** | yes | never |

The whole recording's are the **Exclusion group** and **Also exclude** fields in the Project
design window's Design card. Each Slice's are the **Own group** and **Also exclude** columns
of its row.

Three rules:

1. **Nothing is inherited.** A Slice leaves out only the groups in its own row. It does not
   pick up the whole recording's exclusions unless you list them. This is what lets a
   chamber that failed at hour 10 stay in a 6-hour Slice.
2. **No two analyses share an own group.** Otherwise excluding a chamber while viewing one
   Slice would also remove it from another. To use the same chambers in two places, put the
   group under **Also exclude**.
3. **A Slice's own group is its name** unless you type another.

### Recording exclusions in the QC Viewer

1. In the Hub, pick the Slice in the **Slice** menu above the members table, then load the
   member and open the QC Viewer. It opens on that Slice. In the QC Viewer itself, you can
   instead choose the Slice in the **Slice** menu on the Load tab and click **Load**.
2. On the **Feeding Summary** tab, tick the chambers to exclude.
3. Click **Save Exclusions…**. It offers the Slice's own group, so the chambers leave that
   Slice and nothing else.

To exclude many chambers across many members at once, use **Apply exclusion sheet…** in the
Hub's Analysis card. Its `group` column says which group each row goes into.

### Common set-ups

**Different chambers for different ranges.** This is the old `Remove_6hr` / `Remove_24hr`
pattern: give each analysis the group the old script applied to that range.

| Analysis | Old script applied | Own group | Also exclude |
|---|---|---|---|
| Whole recording | `Remove_24hr` | `Remove_24hr` | — |
| `0_360` | `Remove_6hr` | `Remove_6hr` | — |
| `360_1440` | `Remove_24hr` | `360_1440` (empty) | `Remove_24hr` |

`360_1440` cannot also own `Remove_24hr`, because the whole recording already does. So it
uses that group through **Also exclude**, and keeps an empty group of its own for anything
you exclude later while viewing it.

**A chamber that is bad throughout**, such as a fly dead from the start. Save it once, into
a group such as `dead`, and add `dead` to **Also exclude** for the whole recording and for
every Slice.

**A chamber that fails part-way.** Put it in the groups of the analyses that include the
failure: the whole recording's, and any Slice that runs past it. Leave it out of Slices that
end before it.

**Checking.** Each analysis's `summary.txt` names the groups it applied, for example
`Chambers excluded (group 'Remove_6hr')`. The Project Report lists every excluded chamber
for its Slice, by hand or automatic.

---

## 4. Running Slices from the Hub

- **The Slice menu**, above the members table, chooses which Slice the Hub *shows*:
  - the members table's **Analyzed** and **Report** columns;
  - what a double-click loads;
  - what the QC Viewer and the plots show;
  - which reports **View reports** opens.

  Picking another Slice reloads the loaded member as that Slice. The scroll wheel does not
  change it, so scrolling the panel never switches Slice by accident.
- **The Slices group** at the bottom of the QC, Analyze and Plots panels has one box per
  Slice, all ticked to begin with. **Run QC**, **Run analysis** and **Generate plots** run
  the whole recording and every ticked Slice. A tick on one panel applies to all three.
- **Analyze all**, **Combine** and **Create report**, in the Analysis card, always cover the
  whole recording and every Slice.
- **not covered**, in the Analyzed column, means the member's recording stops short of the
  Slice and is left out of it; hover for the reason. **re-run needed** means exclusions or
  the Slice's settings changed after it was analysed.

---

## 5. Where the results appear

**In each member:**

```
Rep1_.../
  analysis/  qc/          the whole recording, as before
  slices/
    0_360/
      analysis/           feeding summary, summary.txt, removed chambers,
                          experiment report, light tables, paired–yoked comparison
      qc/
      slice.json          the Slice as run, whether the recording covered it,
                          and where each DFM's data ended
```

**In the Project:**

```
MyProject/
  analysis/  MyProject_report.pdf      the whole recording
  slices/
    0_360/
      analysis/                         Combined Analysis: MyProject_Summary.csv,
                                        MyProject_Stats.txt, MyProject_Excluded.csv,
                                        MyProject_SliceCoverage.csv, ...
      MyProject_0_360_report.pdf
      figures/                          publication figures drawn from this Slice
```

**How a Slice is labelled:**

- Tables label its rows `Slice 0_360`, with `FacetRange` `(0, 360)` for its minutes, where the
  whole recording's say `Whole recording`.
- The experiment report's cover and `summary.txt` name the Slice and its minutes.
- The Project Report's title reads `MyProject · Slice 0_360`. It also names any member left
  out of the Slice, and warns when pooled members cover spans of different lengths.

**Figures.** In the Plot Editor, the **Slice** menu under *This plot* chooses which Slice a
figure is drawn from. **Render figures** saves it into that Slice's `figures/` folder.

---

## 6. What a Slice does to the analysis

The minutes outside the Slice are dropped when the data loads, before the baseline, the
thresholds, event detection and automatic removal. That is what the old ranged runs did, so
a Slice reproduces an old `analysis_<start>_<end>` run with the same settings and exclusions.
On the MBa'b'ap closed-loop data (`test_data/MBabap`), every chamber and every metric of
`0_360` and `360_1440` matched the old runs exactly.

- **Slices do not add up to the whole recording.** A feeding bout that crosses a boundary is
  split, and the baseline is computed within each Slice.
- **Phases (Facets) still apply inside a Slice.** Each phase is cut to the Slice and keeps
  its name. A phase with no minutes in the Slice is dropped, and `summary.txt` says so.
- **Slices may overlap, and are never compared with each other.** Each has its own set of
  chambers. To compare phases within one set of chambers, use Facets.

---

## 7. Which members a Slice includes

A member is included in a Slice when every DFM's recording reaches the Slice's end, within
the coverage tolerance. A 24-hour run often ends at minute 1439.8, which is why the default
tolerance is 5 minutes.

A member that stops short is **not covered**. It is left out of that Slice, never pooled with
part of a Slice, and not counted as a failure. The Hub, the Slice's Project Report and its
`SliceCoverage` table name it and say why.

A Slice whose end is `end` includes every recording that reaches its start. Members of
different lengths then pool different spans under one name, and the Project Report warns
when their ends are more than the tolerance apart.

---

## 8. Converting an older experiment

1. **Arrange the folders.**
   - Put the recording folders together in one folder. Each becomes a member.
   - In each, rename `Data/` to `data/`, and move `Program.txt` and `Messages.csv` into it.
   - Move old outputs and R files (`flic_config_results/`, `ExpDesign.csv`, ...) into an
     `extra_files/` folder, which pyflic ignores.
2. **Make it a Project.** In the Hub's Project panel, click **Initialize existing
   directory…** and choose that folder. The design is filled in from the first member's
   old settings, so review every field:
   - **Experiment type:** an old `two_well` type is now the **Custom** type with a two-well
     layout.
   - **Design factors:** they must suit every member. Drop a factor that only numbers the
     pairs; for an optogenetic experiment, `Program.txt` already says which chambers are
     paired.
   - **Exclusion group and Slices:** set them as in sections 2 and 3, one Slice per range the
     old script ran.
3. **Save.** When asked, let the window remove each member's own copy of the old
   settings, so they all follow the design. If you changed the design factors, update each
   member's chamber assignments in the Config Editor.
4. **Check and run.**
   - Run `pyflic lint` on the Project. It lists what is left to fix, including old script
     time ranges and old `analysis_<start>_<end>` folders, each with the Slice that replaces
     it.
   - Then click **Analyze all**, **Combine** and **Create report**.
   - Compare a Slice's `feeding_summary.csv` with the old range's in `extra_files/`.

`test_data/MBabap` was converted this way. Its original settings are kept in each member's
`extra_files/flic_config.yaml.orig`.

---

## Appendix A. Slices in the configuration file

The Project design window writes the design into `project.yaml`, under `design: global:`.
For a standalone experiment it goes under `global:` in `flic_config.yaml`. Here is the
MBa'b'ap Project's, with a shared `dead` group and a lower lick cutoff added for
illustration:

```yaml
design:
  global:
    exclusion_group: Remove_24hr      # the whole recording's own group
    also_exclude: [dead]              # optional; groups the whole recording also leaves out
    slice_tolerance_min: 5            # optional; 5 is the default
    slices:
      '0_360':
        start: 0
        end: 360
        exclusion_group: Remove_6hr
        also_exclude: [dead]
        constants: {min_untransformed_licks_cutoff: 10}   # optional override
      '360_1440':
        start: 360
        end: 1440                     # or: end: end, to the end of each recording
        exclusion_group: '360_1440'
        also_exclude: [Remove_24hr, dead]
```

- **Quote a Slice name that starts with a digit.** Unquoted, YAML reads `0_360` as the number
  240. pyflic refuses that rather than run a Slice called "240".
- `whole`, `all` and `none` are reserved and cannot be Slice names.
- `constants:` accepts only `min_untransformed_licks_cutoff`, `exclude_failed_opto_chambers`,
  `opto_unexplained_fail_fraction` and `opto_unexplained_min_sec`.
- The Hub's Slice boxes are saved as `omit: slices: [...]`, listing the Slices left out.

`remove_chambers.csv`, in each member, holds one row per chamber and group:

```csv
group,dfm_id,chamber,note
Remove_24hr,1,1,well A dried after 8 h
Remove_6hr,7,5,no feeding in the first hours
dead,3,2,dead at the start
```

---

## Appendix B. Scripts, the command line and Python

- **Scripts.** A step takes `slice: 0_360`, or the script does, to work on that Slice;
  without one, it works on the whole recording. `run_qc`, `run_analysis` and `run_plots`
  without a `slice` run the whole recording and every ticked Slice, as the Hub's buttons do.
  **A step's old `start` and `end` are retired.** A step that still states them is skipped,
  with a message naming the Slice to set up instead.
- **Command line.** `pyflic batch <folder>` runs every Project *below* the folder, so point it
  at the folder that contains your Project. `pyflic lint <project>` checks the design and
  its Slices.
- **Python.**
  - `load_experiment_yaml(path, slice="0_360")` loads a Slice.
  - `exp.load_slice("0_360")` does the same from an experiment already loaded.
  - `Project(path).for_slice("0_360")` is the Project seen through that Slice: its members,
    Combined Analysis and report.
