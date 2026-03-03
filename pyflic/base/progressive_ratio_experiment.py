from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from .two_well_experiment import TwoWellExperiment


@dataclass(slots=True)
class ProgressiveRatioExperiment(TwoWellExperiment):
    """
    A progressive-ratio specialisation of :class:`TwoWellExperiment`.

    All DFMs in the config must use ``chamber_size=2``.
    Set ``experiment_type: progressive_ratio`` in ``flic_config.yaml`` under
    the ``global:`` section to have :func:`load_experiment_yaml` return this
    class automatically.
    """

    @classmethod
    def load(
        cls,
        project_dir: str | Path,
        *,
        range_minutes: Sequence[float] = (0, 0),
        parallel: bool = True,
        max_workers: int | None = None,
        executor: Literal["threads", "processes"] = "threads",
    ) -> ProgressiveRatioExperiment:
        """Load a progressive-ratio experiment, validating that every DFM uses ``chamber_size=2``."""
        from .yaml_config import load_experiment_yaml

        base = load_experiment_yaml(
            project_dir,
            range_minutes=range_minutes,
            parallel=parallel,
            max_workers=max_workers,
            executor=executor,
        )
        bad = [
            dfm_id
            for dfm_id, dfm in base.dfms.items()
            if dfm.params.chamber_size != 2
        ]
        if bad:
            raise ValueError(
                f"ProgressiveRatioExperiment requires chamber_size=2 for every DFM, "
                f"but DFM(s) {sorted(bad)} have chamber_size != 2.  "
                f"Set chamber_size: 2 in flic_config.yaml."
            )
        return cls(**{f.name: getattr(base, f.name) for f in dataclasses.fields(base)})
