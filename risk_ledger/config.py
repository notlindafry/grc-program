"""Run configuration for the ledger.

Everything here has a sensible default so the tool runs on a bare corpus. A
corpus may ship an optional ``config.yaml`` to pin the Monte Carlo choices and
the calibration refresh window; CLI flags override the file.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import yaml

# Default iteration count and seed. Fixed and documented so reports are
# reproducible from the same corpus (see docs/methodology.md).
DEFAULT_ITERATIONS = 10_000
DEFAULT_SEED = 20260617

# Calibration is treated as stale once it is older than this many days. The SPEC
# calls this "the configured refresh window"; a year is the common cadence.
DEFAULT_REFRESH_WINDOW_DAYS = 365

# How long before a deadline counts as the "final stretch" for drift trajectory.
DEFAULT_FINAL_STRETCH_WEEKS = 8


@dataclass
class Config:
    iterations: int = DEFAULT_ITERATIONS
    seed: int = DEFAULT_SEED
    refresh_window_days: int = DEFAULT_REFRESH_WINDOW_DAYS
    final_stretch_weeks: int = DEFAULT_FINAL_STRETCH_WEEKS
    # The reference "today" used for staleness and expiry checks. Defaults to the
    # real today; pinned in tests and for reproducing a historical report.
    as_of: dt.date = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.as_of is None:
            self.as_of = dt.date.today()

    @classmethod
    def load(cls, data_dir: Path) -> "Config":
        """Load ``config.yaml`` from the corpus if present, else defaults."""
        cfg = cls()
        path = data_dir / "config.yaml"
        if not path.exists():
            return cfg
        raw = yaml.safe_load(path.read_text()) or {}
        mc = raw.get("monte_carlo", {}) or {}
        if "iterations" in mc:
            cfg.iterations = int(mc["iterations"])
        if "seed" in mc:
            cfg.seed = int(mc["seed"])
        calib = raw.get("calibration", {}) or {}
        if "refresh_window_days" in calib:
            cfg.refresh_window_days = int(calib["refresh_window_days"])
        drift = raw.get("drift", {}) or {}
        if "final_stretch_weeks" in drift:
            cfg.final_stretch_weeks = int(drift["final_stretch_weeks"])
        return cfg
