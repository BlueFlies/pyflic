# Reports

pyflic writes two PDF reports: one per member, and one per Project. Both are laid out the
same way — US Letter pages of one size, a running header, "Page n of N" in the footer, a
contents list on the first pages, tables that continue across pages with their header
repeated, and figures drawn to fit their box under the report's own heading.

## The experiment report

Written to the member's `analysis/experiment_report.pdf` by the Hub's **PDF report**
button, by **Analyze all**, by the `pdf_report` script action and by
`write_experiment_report(exp)`.

The report describes the analysis the pipeline runs, so it first applies the design's
auto-removal — once, exactly as basic analysis does — and every result after the Quality
control section stands on the chambers that remain.

| Section | What is in it |
|---|---|
| **Cover** | What was recorded (DFMs, dates, hours), the **Generation** of each DFM's data file, and for an optogenetic member where its **Lit time** came from; the treatments with their chamber counts, design factors, wells, Facets, whether licks are transformed; **At a glance** — data integrity, exclusions and the type's own QC verdicts as coloured callouts; the contents |
| **1 Quality control** | Data integrity per DFM; for two-well layouts, simultaneous feeding per chamber and the largest bleeding response between wells; the Program timeline of each DFM that has one; every excluded chamber and why; for an optogenetic experiment, the optogenetic light QC — the program as read, the verdict per linkage group and the figure per DFM; then the Experiment Type's own checks |
| **2 Results** | The figures the assay is read by, each with its treatment statistics; for an optogenetic member, **Light behaviour** after them |
| **Appendix A** | Every feeding-summary metric by treatment, for reference |
| **Appendix B** | The detection parameters and the `constants:` block the analysis used |

**The cover.** The **Generation** line says what shape of file each DFM wrote: 1 for 27
columns from older firmware, 2 for 90 columns with the firmware 4.0.0 columns empty, 3 for
firmware 4.0.0 data (see [Generations](concepts-optogenetics.md#generations)). DFMs that
differ are listed separately. **Lit time from** reads *OnMs, exact* for a firmware 4.0.0 DFM
and *OptoCol1, sampled at 5 Hz* otherwise. *At a glance* warns about a firmware 4.0.0
recording whose `Program.txt` is missing, and about a recording with no training
information.

**Quality control.**

- **Data integrity** gives each DFM its samples, start, hours, whether the sample index is
  continuous, the **Lost records** its index skipped, its data breaks and its firmware error
  flags. A DFM is *ok* with none of these, otherwise *warning*.
- **Simultaneous feeding** shows each chamber's samples licked on both wells at once
  *before* the dual-feeding correction — the crosstalk found — beside the count *after* it,
  which the correction drives to zero. With the correction off the two agree.
- **Program timeline**: in an optogenetic experiment, one figure per DFM with a
  `Program.txt` section or firmware 4.0.0 data. See
  [Program timeline](plots-catalog.md#program-timeline).

**Results by type.** A two-well experiment gets **Preference** — the preference index and
event PI by treatment, per Facet, and PI over time — then **Consumption** (licks, events and
median bout duration at each well). A single-well experiment gets Consumption only. A
Hedonic experiment adds its duration plot and the event-weighted duration table. A
Progressive Ratio experiment replaces the per-chamber figures, which would pool each paired
fly with its own yoked control, with the **cumulative difference curve**, the **paired −
yoked difference** in the Test phase, tested between treatments and against zero within each
treatment, and the **breaking point**: the lick-backed Test light events each paired fly
completed before its first pause longer than `pr_break_gap_min`, with the still-responding
curve, its per-group table and the per-DFM licks-per-light-period plots. On firmware 4.0.0
data the table shows `BreakRequirement`, the Requirement the last counted event met, beside
it. When every group's Test Paradigm is a FixedRatio the section is titled **Fixed ratio:
activations earned**. Its Quality control section adds the training table and the
[light QC](concepts-progressive-ratio.md#light-qc) with its three figures per DFM.

**Light behaviour.** An optogenetic member of any type gets this section after the feeding
results, from its [light table](concepts-optogenetics.md#the-light-table): a dot plot per
headline metric — Activations, lit time, Firmware Events and the end of Acclimation — by
treatment, per Facet when there are Facets, with the treatment comparisons. A metric no
Paradigm of the recording defines is left out and named. A Progressive Ratio member compares
its paired chambers only.

**Statistics.** Under each figure: two treatments, Welch's t-test; more, Tukey HSD on every
pair; p < 0.05 highlighted. One observation per chamber (per chamber group for a
Progressive Ratio difference or breaking point). *Mean* and *n* read as the first treatment
named / the second, and *Difference* is the first minus the second. The breaking point adds
**p (log-rank)**, which treats a censored count as the lower bound it is. The paired −
yoked difference adds a table testing it against zero in each treatment: the paired t-test,
which is a one-sample t-test on the differences, with the Wilcoxon signed-rank test beside
it.

**One treatment, or nothing to draw.** A design with a single treatment, such as one factor
with one level, is reported as one: Results open with a sentence saying nothing is compared
between treatments, and no comparison table follows. A figure whose metric no chamber has a
value for, such as a bout duration when no feeding event was detected, becomes a grey note
saying so and why, without its caption; Appendix A leaves such metrics out of its grid and
names them. A red note is kept for a figure that failed. Dot plots spread points only across
a treatment, never up or down, so chambers with equal values sit on that value.

## The Project Report

Written to `<project>/<name>_report.pdf` by **Create report** and the `project_report`
script action. It reads the members' saved results only — it never analyses a member — and
builds the Combined Analysis first when there is none.

| Section | What is in it |
|---|---|
| **Cover** | The Project, its members, pooled chambers and treatments, factors and Facets; **At a glance** — missing members, exclusions, the type's QC flags; the contents |
| **1 Members** | One row per member: DFMs, the **Generation** of its recordings, chambers analysed and excluded, whether its analysis is current, whether it has a report, and a **Note** for a member with no training information |
| **2 Quality control** | Every excluded chamber across members with its reason; every group a light QC flagged — Progressive Ratio chamber groups and optogenetic linkage groups, marked by source — and whether the pooled numbers include it |
| **3 Results** | The type's pooled figures (the Plot Editor's styles), the type's own pooled figures (Progressive Ratio: the breaking point, led by its still-responding curve, and the paired − yoked difference), and the statistics as tables — pooled test and linear mixed model (DFM nested within experiment) side by side, with the log-rank test for the breaking point and the paired − yoked difference tested against zero; then **Light behaviour** for a Project with optogenetic members |
| **Appendix** | The Design's detection parameters and constants |

The **Generation** column is read from each member's saved outputs, so it needs no load. The
**Note** column appears only when some member needs one: *no training information*, for a
member recorded with DFM firmware older than 4.0.0.

**Light behaviour** pools every optogenetic member's light table
(`<project>_LightSummary.csv`) the way the feeding metrics are pooled: a faceted figure per
headline metric and the treatment comparisons, per chamber. Members recorded before firmware
4.0.0 contribute lit time only.

For a Progressive Ratio Project the breaking point section adds the median
`BreakRequirement` per treatment beside the median breaking point, when any member recorded
one. When every pooled group ran a FixedRatio Test, the section is titled **Fixed ratio:
activations earned**.

An optional AI summary follows the results when one has been written; it is marked as
written by a language model.

See [Plot catalogue](plots-catalog.md) for the figures themselves and
[Excluding chambers](concepts-exclusions.md) for what leaves the analysis and how.
