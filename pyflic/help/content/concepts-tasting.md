# Tasting

Not every contact with the food is feeding. A fly may touch the liquid briefly without
ingesting — sampling it rather than consuming it. pyflic separates these as **tasting**
events.

## How tasting is identified

A sample is a **tasting lick** when both of these hold:

- its baselined signal falls **between `tasting_minimum` and `tasting_maximum`**, and
- it was **not already classified as a feeding lick**.

The second condition is what keeps the two categories disjoint. Feeding detection runs
first and takes precedence; tasting is identified from what remains. A sample can never be
counted as both. The feeding licks it checks against are those before
[event linking](concepts-licks-events.md#event-linking-the-link-gap), so a sample in a gap
that linking bridged can still be a tasting lick.

Contiguous runs of tasting licks are grouped into **tasting events**, and runs shorter
than `tasting_minevents` samples are discarded — the same minimum-length rule that applies
to feeding, with its own parameter.

## The default thresholds

For both single-well and two-well experiments the defaults are:

| Parameter | Default |
|---|---|
| `tasting_minimum` | `5` |
| `tasting_maximum` | `20` |
| `tasting_minevents` | `1` |

Note that `tasting_maximum` (20) equals the default `feeding_threshold` (20). That is
deliberate: the tasting band sits *below* the level at which a contact is confirmed as
feeding, so the two categories meet without overlapping.

## Choosing the band

The tasting window is the region of signal that is clearly a contact but not clearly a
meal. Its lower edge, `tasting_minimum`, is a noise floor — set it too low and electrical
noise is recorded as tasting. Its upper edge, `tasting_maximum`, is where you consider a
contact substantial enough to be feeding instead.

Because tasting is defined as *what feeding did not claim*, changing your feeding
parameters changes your tasting counts even if you leave the tasting parameters alone. If
you raise `feeding_threshold`, contacts that used to be confirmed as feeding may fall into
the tasting band. Always report which detection parameters produced a tasting result.

## Where tasting appears

Tasting is **not** in the feeding summary: its `Licks`, `Events` and durations are feeding
only. Tasting appears in:

- **The event statistics export** with `kind: tasting` — the
  [script action](scripts-actions.md#analyse-actions) `tidy_export` writes
  `analysis/tidy_tasting_events.csv`, one row per tasting event with its time, duration,
  licks and intensity. In two-well experiments each row names its well, so you can ask
  whether a fly sampled one option and fed on the other — a distinction that lick counts
  alone would hide. The Hub's *Event statistics* item writes feeding events only.
- **The optogenetic light QC**, which counts a tasting sample, like a feeding lick, as the
  fly's contact with the well. See [Optogenetic experiments](concepts-optogenetics.md).

---

Related: [How feeding is detected](concepts-licks-events.md) ·
[Parameter reference](reference-parameters.md)
