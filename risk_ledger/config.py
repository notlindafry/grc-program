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

# Breach classification. A breach is "single-acceptance" rather than
# "accumulation" when the leading contributor accounts for at least this share of
# the contributed exposure (it also counts as single-acceptance if it breaches
# appetite by itself, which is a structural rule, not a tunable). At 0.5 the lead
# must be the majority of the added exposure; raise it to demand a more dominant
# culprit, lower it to call more breaches single-acceptance.
DEFAULT_SINGLE_ACCEPTANCE_SHARE = 0.5

# Persistence. An active exception renewed at least this many times whose
# justification was never revisited is "temporary forever" -- a temporary
# acceptance that has quietly become the rule.
DEFAULT_RENEWAL_ALERT_COUNT = 3

# Fiscal-year boundary, used by the exposure arc (exceptions filed before this
# date are the book entering the year).
DEFAULT_YEAR_START = dt.date(2026, 1, 1)


@dataclass
class Config:
    iterations: int = DEFAULT_ITERATIONS
    seed: int = DEFAULT_SEED
    refresh_window_days: int = DEFAULT_REFRESH_WINDOW_DAYS
    final_stretch_weeks: int = DEFAULT_FINAL_STRETCH_WEEKS
    single_acceptance_share: float = DEFAULT_SINGLE_ACCEPTANCE_SHARE
    renewal_alert_count: int = DEFAULT_RENEWAL_ALERT_COUNT
    year_start: dt.date = DEFAULT_YEAR_START
    # The reference "today" used for staleness and expiry checks. Defaults to the
    # real today; pinned in tests and for reproducing a historical report.
    as_of: dt.date = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.as_of is None:
            self.as_of = dt.date.today()
        if not 0.0 < self.single_acceptance_share <= 1.0:
            raise ValueError("single_acceptance_share must be in (0, 1]")
        if self.renewal_alert_count < 1:
            raise ValueError("renewal_alert_count must be a positive integer")

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
        breach = raw.get("breach", {}) or {}
        if "single_acceptance_share" in breach:
            cfg.single_acceptance_share = float(breach["single_acceptance_share"])
        renew = raw.get("renewals", {}) or {}
        if "alert_count" in renew:
            cfg.renewal_alert_count = int(renew["alert_count"])
        if raw.get("year_start"):
            ys = raw["year_start"]
            cfg.year_start = ys if isinstance(ys, dt.date) else dt.date.fromisoformat(str(ys))
        cfg.__post_init__()  # re-validate after applying overrides
        return cfg
