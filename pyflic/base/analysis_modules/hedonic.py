"""The Hedonic durations module: bout duration at each well of a choice.

What made the Hedonic type hedonic: the weighted duration summary and the
hedonic feeding plot (``HedonicFeedingExperiment``), on a two-well choice
whose wells are both named.  The MedDuration and Events cutoffs it used to
apply belong to every two-well experiment now (``TwoWellExperiment``).
"""

from __future__ import annotations

from .base import AnalysisModule


class HedonicModule(AnalysisModule):
    id = "hedonic"
    title = "Hedonic"
    summary = ("Median bout duration at each well, plain and weighted by each "
               "chamber's events, and the hedonic feeding plot.")

    needs_layout = "two_well"
    experiment_class = "pyflic.base.hedonic_experiment:HedonicFeedingExperiment"
    required_wells = ("A", "B")
    outputs = ("weighted_duration.csv",)


HEDONIC = HedonicModule()
