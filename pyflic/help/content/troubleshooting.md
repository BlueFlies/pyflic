# Troubleshooting

## Loading

### "flic_config.yaml not found in experiment directory"

The folder you chose is not an Experiment Directory. It needs a `flic_config.yaml` at its
top level — not inside `data/`. The Hub says "is not a Batch, a Project, or an Experiment
Directory" for the same reason. See
[Setting up an experiment directory](getting-started-project.md).

### A DFM in my config has no data

CSV filenames must match the DFM numbers in your configuration. A DFM keyed `3` needs
`DFM3_0.csv` (v3) or `DFM_3.csv` (v2) in `data/`. Check for a leading zero, a different
separator, or a file left in the folder's root instead of `data/` — inside a Project the Hub
shows that as a blocked member, **unfiled recording**, and offers to file it.

### "'params.chamber_size' is owned by experiment_type"

A typed config states `chamber_size` (or `chamber_layout`), which the Experiment Type now
owns. Delete the key; the value is derived. An old `experiment_type: two_well` or
`single_well` fails the same way and names its replacement, `chamber_layout:`. Run
`pyflic lint` on the folder to list every config that needs this. See
[Experiment types](concepts-experiment-types.md#migrating).

### "requires well_names for A, B"

Hedonic and Progressive Ratio experiments must name both wells under `global.well_names`.

### A member fails to load inside its Project

The Project's design owns every `global:` key. A member whose own `global:` block
disagrees with it — a different threshold, different `well_names` — is refused. Delete the
member's `global:` block so it inherits; the Project Design dialog offers to do it for
every member at once. See [Projects and members](concepts-project.md).

### Only part of my recording loaded

Check the start and end minute controls. `end: 0` means through the end of the recording;
any other value truncates. Multi-segment experiments stitch in filename order, so a
misnamed segment can land out of sequence.

### "DFM 99 is the Environmental Monitor, not a DFM"

The config has an entry for DFM 99. That id is the Environmental Monitor's, which records
the rig's temperature, humidity and light, and pyflic never reads it as a DFM. Delete the
entry. See [DFMs and chambers](config-dfms-chambers.md#dfm-99-is-the-environmental-monitor).

### "facet_source: program takes the Facets from data/Program.txt"

The design asks for [Program Facets](concepts-facets.md#program-facets), and a DFM has no
program to take them from: `data/` has no `Program.txt`, or its `Program.txt` has no section
for that DFM. Copy in the `Program.txt` the MCU exported for this recording, or go back to
`facet_source: cutoffs`.

## Results that look wrong

### My exclusions are not being applied

Three common causes, in the order worth checking:

1. **`excluded_chambers` in the YAML.** This key is ignored at load time. pyflic prints a
   warning telling you to migrate to `remove_chambers.csv` — look for it in the load
   output. See [exclusions](config-dfms-chambers.md#excluding-chambers).
2. **A group-name mismatch.** Inside a Project, the design's `exclusion_group:` names the
   group every member is read under. In a script, a bare `remove_chambers` step uses the
   **script's name** as the group. If no group of that name exists in the CSV, nothing is
   excluded and nothing complains.
3. **Results that predate the declaration.** Declaring a chamber changes nothing already on
   disk. The Hub's Analyzed column reads **re-run needed** until you re-run the member.

### Lick counts look far too small

They are probably fourth-root transformed — that is the default. A `Licks` value of `6.2`
means about 1478 licks. Set `global.transform_licks: false` to turn it off, and note that
`summary.txt` reports untransformed counts while `feeding_summary.csv` reports transformed
ones. See [the lick transform](concepts-metrics.md#the-lick-transform).

### Far too many, or too few, events

Look at the baselined QC plot with thresholds drawn. Events where the trace is flat means
thresholds are too low; obvious feeding unmarked means too high. If instead single meals
are split into many events — or separate visits merged into one — the culprit is the
[link gap](reference-parameters.md#feeding_event_link_gap), not the thresholds.

Run a [parameter sensitivity sweep](scripts-actions.md#analyse-actions) rather than
guessing.

### Every preference index is near zero

Check that `correct_for_dual_feeding` is on — it defaults to `true` for two-well
experiments. Uncorrected crosstalk between the two wells of a chamber pushes every PI
toward zero, which reads as indifference. The **Sim. Feeding** tab in the
[QC Viewer](app-qc-viewer.md) shows how much simultaneous feeding was detected.

### The preference is backwards

`pi_direction` maps physical side to Well A. If you counterbalanced food position across
DFMs but left `pi_direction` at its default everywhere, half your plate has Well A meaning
the opposite substance. See
[Two-well choice and the preference index](concepts-two-well-pi.md).

### Durations changed and I did not change the thresholds

Check `samples_per_second`. Durations are samples ÷ sampling rate, so a wrong rate scales
every duration and interval by a constant while leaving counts untouched — which is why it
is easy to miss.

## Progressive Ratio

### Every chamber group was removed

Look at the training table in `summary.txt` or the report. "no training flag on any well"
means the recording carries no training flag — a version-2 file, or firmware that did not
mark training — so no group ever finished training and `require_training_complete`
removed them all. A recording from older firmware needs version-3 files with light data
(`OptoCol1`). See [Progressive Ratio experiments](concepts-progressive-ratio.md#requirements).

### "no training information: recorded with DFM firmware older than 4.0.0"

The recording was made by PyMCU 4.0.0 from a DFM whose firmware is older than 4.0.0. Such a
file has the new columns, all empty, and no training flag either: there is no record of
Training at all. Nothing is removed. Each chamber group gets one `Recording` Facet, with no
Test phase, no breaking point and no sucrose persistence, and the member says so on the
Hub's Loaded line, in the report and in the Project Report. Update the DFM's firmware for
the next recording; this one cannot gain what it did not record. See
[No training information](concepts-progressive-ratio.md#no-training-information).

### A group I expected to keep was excluded

Check its light QC verdict in `pr_light_qc.csv`. **Self-triggered light** (a run of
lick-free light events) and **implausible training** fail a group, and with
`exclude_failed_pr_groups` on, both its chambers leave the analysis. The licks-per-event and
resting-level figures on the QC panel show why. See
[Light QC](concepts-progressive-ratio.md#light-qc).

### "the firmware counted rising Events per light event; pyflic's licks did not follow"

A note on a firmware 4.0.0 recording: the firmware counted more feeding bouts for each light
event as the requirement rose, as a working progressive ratio should, while pyflic's licks
per light event did not rise. The fly worked to the schedule and pyflic's detection missed
some of it. Look at the baselined trace of the paired sucrose well, and the detection
parameters, before trusting the *no increasing trend* warning beside it.

### Most breaking points are censored

`n+` means the group never paused longer than `pr_break_gap_min` before its Test window
ended — it was still responding. A long recording with a short gap censors few groups; a
short one, or a large gap, censors many. Check the sensitivity table in `summary.txt`
before changing the gap. See [Breaking point](concepts-progressive-ratio.md#breaking-point).

### The breaking point stopped overnight

The rule does not know the time of day: a pause at night longer than `pr_break_gap_min`
ends the count. Raise the gap in the design if your flies routinely pause that long and then
resume — the sensitivity table shows what each choice gives.

### The Project Report says a member has no breaking point table

That member was analysed before the breaking point existed. Re-run its basic analysis.

## Optogenetic recordings

### The optogenetic light QC failed a group I trust

Open `qc/opto/opto_light_qc.csv` and the **Light explained by licks (QC)** figure. Red light
beside orange in the panel to its right is a trigger well the firmware read as touched while
pyflic saw nothing: a drifting or leaking well, whose light is not evidence of feeding. Red
light with no orange is light the firmware had no reason to switch on — check the lid and
the linkage. A failed
group is flagged, not excluded, unless `exclude_failed_opto_chambers` is on. Without
`data/Program.txt` the check cannot tell an open-loop schedule from a stuck light, so it
only warns. See [Optogenetic experiments](concepts-optogenetics.md).

### "holds more than one Program.txt"

`data/` may hold one `Program.txt`, the one the MCU exported for this recording. Remove the
others; which one describes the run is not a guess pyflic will make.

### "firmware 4.0.0 recording without Program.txt"

The full warning reads *DFM n: firmware 4.0.0 recording without Program.txt: Paradigm types
and settings unknown*. The data rows name each Paradigm but not its type, its settings or
the thresholds, so everything that depends on the type is `NA` and the light QC cannot
fail a group. The light QC flags it as *no Program.txt for firmware 4.0.0*. Copy the
`Program.txt` PyMCU exported for this recording into `data/` and run again.

A `Program.txt` that starts `***ALL DFM***` is not missing: it is the export of a recording
started without a Program, and every well was `Off`. Any light then fails the group.

### "paradigm not in program"

A row of the data names a Paradigm that `Program.txt` does not define. The file belongs to
another recording: every group of that DFM fails, and those rows are not judged. Find the
`Program.txt` exported with this recording. Names are matched ignoring case, as PyMCU
matches them.

A row naming a *defined* Paradigm other than the one `Program.txt` prints for its interval
is a **program mismatch** warning instead: the rows are judged by their own Paradigm.

### "broken yoking"

Linked wells share one light, so their `OnMs` should match to the millisecond, and a well set
`Off` should count no Activations of its own. The group fails when its linked wells' light
differs in more than `opto_yoking_fail_fraction` (1%) of its lit records, or when an `Off`
well linked to a trigger well counted Activations. The yoked fly did not get its partner's
light, so the comparison between them does not hold. Check the lid's wiring and the
program's `Linkage:` line. The [Program timeline](plots-catalog.md#program-timeline) shows
which well differs.

### Lost, repeated, late and unknown-instruction records

The integrity report and the light QC read the DFM's own bookkeeping:

| Finding | What happened | What to do |
|---|---|---|
| **lost records**: gaps in `Index` | the DFM could not keep records while the MCU was not reading them, and they are gone; PyMCU logs *Skipped index* in `Messages.csv` | a short gap changes little; more than `opto_lost_records_warn` (25 records, 5 s) warns. Treat results across a long gap with care, as for a data break |
| **repeated records** | PyMCU wrote a block of records twice after a failed file write | nothing: the second copy is dropped at load, matched on `Index` and time, and `summary.txt` and the integrity report say how many |
| **late records**: `OnMs` above 200 ms | a record came later than its 200 ms | more than `opto_late_records_warn` (10) warns. Look at the `Error` column's interrupt flags in the integrity report |
| **unknown-instruction rows**: `Interval` `NA` after the start | the DFM ran an instruction outside the program, for example outputs switched by hand during the recording | those rows are not judged. More than `opto_unknown_rows_warn_fraction` (1%) of the rows warns |

### "acclimation count mismatch"

A trigger well's completed Acclimation counted a different number of Activations than its
Paradigm's `Acclimation` setting. Firmware 4.0.0 gives exactly that many, so first check
that `Program.txt` is this recording's. If it is, the DFM did not do what its Paradigm says:
look at the well's lane in the [Program timeline](plots-catalog.md#program-timeline). An
Acclimation cut short by the end of the recording or by a new Paradigm is never counted.

### "firmware events disagree"

Under a ratio Paradigm the firmware counts its own feeding bouts, Firmware Events, and
pyflic counts its feeding events from the same signal. They are different detectors and
differ at the edges. A trigger well whose two counts differ by more than
`opto_event_disagreement_warn_fraction` (25%) of the Firmware Events warns, once either count
reaches 5. Far more Firmware Events than pyflic events is a drifting well or thresholds that
miss real feeding; far fewer is pyflic splitting bouts the firmware joins. Compare the
firmware's `EventGapMs` with your `feeding_event_link_gap`, and look at the baselined trace.

### No Role, or every Role blank

A chamber's Role comes from `Program.txt`, or on a firmware 4.0.0 recording from the data. A
recording from older firmware without `Program.txt` cannot tell a trigger well from a yoked
one, so its Roles are blank. See [Roles](concepts-optogenetics.md#roles).

## Batch runs

### A Project did not run

The scan reports every folder it skipped — a `project.yaml` with no member directory, an
unreadable folder, a symlink — in the Output tab at the start of the run. A Project with
nothing usable starts unchecked in the review window. See
[Running many projects at once](scripts-batch.md).

### An old folder is not treated as a batch

Subdir-batch mode, keyed on a script named `batch`, is retired. A Batch is now any folder
with Projects beneath it; `pyflic lint` reports the old constructs.

## Performance

### Loading is slow

Keep **parallel** loading on (the Project panel's load options, or `parallel: true` on the
`load` step). Loading is the expensive operation; everything after it reuses the result.

### Do I need to clear the cache?

Almost never. `.pyflic_cache/` is keyed by input, so a stale entry cannot be served for
changed inputs. Clear it to reclaim disk space, not to fix results.

## Getting more detail

- `pyflic lint <folder>` validates every configuration and reports line numbers.
- **Validate every YAML here** on the Hub's Tools panel parses every `project.yaml`,
  `batch.yaml` and `flic_config.yaml` under the selection.
- The Hub's Output tab carries the full message from any failure, and the Errors tab
  collects the warnings and failures on their own.
