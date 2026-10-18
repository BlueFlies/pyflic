"""The paired and yoked module: a Paired chamber against its Yoked chambers.

Per Linkage Group with one Paired chamber and Yoked chambers lit with it,
the Paired chamber's metrics, its Yoked chambers' mean and the difference
(``analytics.yoked_comparison``).  The Ratio analysis keeps its own
Paired-Yoked Difference, so the two exclude each other.
"""

from __future__ import annotations

from .base import AnalysisModule


class YokedModule(AnalysisModule):
    id = "yoked"
    title = "Paired and yoked"
    summary = ("Per yoked linkage group: the Paired chamber's metrics, its Yoked "
               "chambers' mean and the difference, tested against zero.")

    needs_light = True
    conflicts = ("ratio",)
    conflict_reason = "the Ratio analysis keeps its own Paired-Yoked Difference"
    outputs = ("yoked_comparison.csv",)


YOKED = YokedModule()
