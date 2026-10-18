"""The light and dark module: feeding while the light is on against off.

Under open-loop light, each chamber's licks per minute lit and dark and its
light feeding index (``light_summary``), shown in the reports' open-loop
subsection.  The light table carries the columns whatever the type; the
module decides whether the reports show them.
"""

from __future__ import annotations

from .base import AnalysisModule


class LightDarkModule(AnalysisModule):
    id = "light_dark"
    title = "Light and dark"
    summary = ("Under open-loop light: each chamber's licks per minute lit and dark, "
               "and the light feeding index, in the reports.")

    needs_light = True


LIGHT_DARK = LightDarkModule()
