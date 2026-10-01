"""Step 4 -- the two transformations.

1. **Per-day adjustment** (flows only, ``calendar_adj = per_day`` in the
   inventory): ``x_cal = value / days_in_month``.  Flows are monthly totals, so
   a 31-day month carries about 10% more activity than February for no
   economic reason.  Stocks and prices keep ``x_cal = value``.
2. **Log** (every series): ``x = ln(x_cal)``.  A change of 0.05 in ``x`` is
   about 5% in any series, so prices, IDR amounts and counts share one scale.

Missing or masked values stay missing.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

OBSERVATION_COLUMNS = (
    "series_id", "frequency", "unit", "ref_date", "week_ending", "iso_year", "iso_week", "days_in_month",
    "source_date", "source_file", "raw_value", "value", "quality_flag", "is_provisional", "x_cal", "x",
)


def transform(validated: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    frame = validated.copy()
    per_day = frame["series_id"].map(inventory["calendar_adj"]).eq("per_day")
    days = frame["days_in_month"].astype("float")
    frame["x_cal"] = frame["value"].where(~per_day, frame["value"] / days)
    with np.errstate(divide="ignore", invalid="ignore"):
        frame["x"] = np.log(frame["x_cal"].where(frame["x_cal"] > 0))
    return frame[list(OBSERVATION_COLUMNS)]
