"""Light Monte Carlo engine for the Exception Risk Ledger.

Everything quantitative in the tool flows through this module. The design goals,
straight from the SPEC, are:

* **Bands, never points.** Every quantity is a 90% confidence interval. A result
  is reported as ``Band(low, high)`` where ``low``/``high`` are the 5th/95th
  percentiles of a simulated distribution. The mean is carried only as an
  internal sort key and is never rendered on its own.
* **Light fidelity, consistent method.** A fixed iteration count (default 10,000)
  and a fixed, documented distribution choice per variable type, applied
  identically everywhere.
* **Reproducible.** This is a git-native audit tool, so the same corpus must
  produce the same report. We seed a deterministic per-entity RNG stream from a
  string key, which is order-independent and stable across processes (Python's
  ``random.Random`` seeds str/bytes deterministically, independent of
  ``PYTHONHASHSEED``).

Distribution choices (see ``docs/methodology.md`` for the rationale):

* **Contact Frequency (CF)** and **Loss Magnitude (LM)** -> lognormal. Positive,
  right-skewed, multiplicative. The 90% CI ``[low, high]`` is read as the
  5th/95th percentiles and the lognormal parameters are solved in log space.
* **Probability of Action (PoA)** -> logit-normal. Naturally bounded to ``(0, 1)``,
  fit symmetrically in logit space the same way the lognormal is fit in log
  space. This keeps probabilities inside their valid range without the truncation
  artefacts of a clipped normal.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

# 95th percentile of the standard normal. A 90% CI spans the 5th to 95th
# percentile, i.e. +/- Z95 standard deviations around the (log/logit-space) mean.
Z95 = 1.6448536269514722

# The three light-FAIR variables an exception is allowed to move.
CONTACT_FREQUENCY = "contact_frequency"
PROBABILITY_OF_ACTION = "probability_of_action"
LOSS_MAGNITUDE = "loss_magnitude"

VARIABLES = (CONTACT_FREQUENCY, PROBABILITY_OF_ACTION, LOSS_MAGNITUDE)

# Which distribution family each variable uses.
_LOGNORMAL = "lognormal"
_LOGITNORMAL = "logitnormal"
_FAMILY = {
    CONTACT_FREQUENCY: _LOGNORMAL,
    PROBABILITY_OF_ACTION: _LOGITNORMAL,
    LOSS_MAGNITUDE: _LOGNORMAL,
}


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _expit(x: float) -> float:
    # Numerically stable logistic.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


@dataclass(frozen=True)
class Distribution:
    """A fitted distribution for one variable, ready to sample.

    ``family`` is ``lognormal`` or ``logitnormal``; ``mu``/``sigma`` are the
    parameters in the transformed (log or logit) space.
    """

    family: str
    mu: float
    sigma: float

    def transform(self, z_samples: list[float]) -> list[float]:
        """Map standard-normal draws into this distribution's space."""
        if self.family == _LOGNORMAL:
            return [math.exp(self.mu + self.sigma * z) for z in z_samples]
        if self.family == _LOGITNORMAL:
            return [_expit(self.mu + self.sigma * z) for z in z_samples]
        raise ValueError(f"unknown distribution family: {self.family}")


def fit_distribution(variable: str, low: float, high: float) -> Distribution:
    """Fit the distribution for ``variable`` to a 90% CI ``[low, high]``.

    ``low``/``high`` are treated as the 5th/95th percentiles.
    """
    if variable not in _FAMILY:
        raise ValueError(f"unknown variable: {variable!r}")
    if high <= low:
        raise ValueError(f"90% CI must be increasing, got [{low}, {high}]")

    family = _FAMILY[variable]
    if family == _LOGNORMAL:
        if low <= 0:
            raise ValueError(
                f"{variable} is lognormal and needs a strictly positive low "
                f"bound, got {low}"
            )
        mu = (math.log(low) + math.log(high)) / 2.0
        sigma = (math.log(high) - math.log(low)) / (2.0 * Z95)
        return Distribution(_LOGNORMAL, mu, sigma)

    # logit-normal (probabilities)
    if not (0.0 < low < high < 1.0):
        raise ValueError(
            f"{variable} is a probability and its 90% CI must satisfy "
            f"0 < low < high < 1, got [{low}, {high}]"
        )
    a, b = _logit(low), _logit(high)
    mu = (a + b) / 2.0
    sigma = (b - a) / (2.0 * Z95)
    return Distribution(_LOGITNORMAL, mu, sigma)


def percentile(sorted_samples: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already-sorted list. ``q`` in [0, 100]."""
    n = len(sorted_samples)
    if n == 0:
        raise ValueError("cannot take a percentile of an empty sample")
    if n == 1:
        return sorted_samples[0]
    rank = (q / 100.0) * (n - 1)
    lo = math.floor(rank)
    hi = math.ceil(rank)
    if lo == hi:
        return sorted_samples[lo]
    frac = rank - lo
    return sorted_samples[lo] * (1.0 - frac) + sorted_samples[hi] * frac


@dataclass(frozen=True)
class Band:
    """A 90% confidence interval plus an internal mean.

    ``low``/``high`` are the 5th/95th percentiles and are the only values ever
    rendered. ``mean`` is the expected value, used purely as a ranking key; the
    SPEC forbids rendering it as a lone figure, so the renderers never do.
    """

    low: float
    high: float
    mean: float

    @classmethod
    def from_samples(cls, samples: list[float]) -> "Band":
        ordered = sorted(samples)
        return cls(
            low=percentile(ordered, 5.0),
            high=percentile(ordered, 95.0),
            mean=sum(samples) / len(samples),
        )

    def __add__(self, other: "Band") -> "Band":  # convenience for combining means
        raise NotImplementedError(
            "Bands are not added directly; combine the underlying samples instead."
        )


class MonteCarlo:
    """Owns the iteration count and the deterministic RNG seeding scheme."""

    def __init__(self, iterations: int = 10_000, seed: int = 20260617):
        if iterations < 1000:
            # Below ~1k iterations the 5th/95th percentiles get noisy. We allow it
            # for fast tests but it is not a sensible production value.
            pass
        self.iterations = iterations
        self.seed = seed

    def _standard_normals(self, *key_parts: object) -> list[float]:
        """A reproducible stream of standard normals, keyed by ``key_parts``.

        Different keys give independent streams; the same key always gives the
        same stream regardless of call order or process.
        """
        key = f"{self.seed}|" + "|".join(str(p) for p in key_parts)
        rng = random.Random(key)
        return [rng.gauss(0.0, 1.0) for _ in range(self.iterations)]

    def ale_samples(
        self,
        cf: Distribution,
        poa: Distribution,
        lm: Distribution,
        *,
        key: str,
    ) -> list[float]:
        """Annual Loss Exposure draws: ``ALE = CF * PoA * LM`` (LEF = CF*PoA)."""
        z_cf = self._standard_normals(key, "cf")
        z_poa = self._standard_normals(key, "poa")
        z_lm = self._standard_normals(key, "lm")
        cf_s = cf.transform(z_cf)
        poa_s = poa.transform(z_poa)
        lm_s = lm.transform(z_lm)
        return [cf_s[i] * poa_s[i] * lm_s[i] for i in range(self.iterations)]

    def contribution_samples(
        self,
        *,
        moved: str,
        baseline: dict[str, Distribution],
        with_exception: Distribution,
        key: str,
    ) -> list[float]:
        """Marginal residual contribution of one exception, as a sample stream.

        The exception moves exactly one variable. We compute, per iteration::

            contribution = ALE(moved swapped to with_exception) - ALE(all baseline)

        under **common random numbers**: every iteration fixes one scenario --
        the same standard-normal draws feed the unmoved variables *and* the
        standardized position of the moved variable on both sides. The
        contribution is then purely the loss added by shifting that one
        variable's distribution from baseline to its with-exception range, with
        the scenario held constant.

        Why paired rather than independent draws for the moved variable: it
        isolates the exception's marginal effect (the whole point) and removes
        the Monte Carlo artefact where two close, independently-drawn estimates
        of the same variable produce a spuriously negative "contribution" in the
        lower tail. The band still has width -- from the unmoved variables and
        from where the shared scenario lands -- so uncertainty is preserved.
        """
        if moved not in VARIABLES:
            raise ValueError(f"cannot move unknown variable {moved!r}")

        n = self.iterations
        z = {
            CONTACT_FREQUENCY: self._standard_normals(key, "cf"),
            PROBABILITY_OF_ACTION: self._standard_normals(key, "poa"),
            LOSS_MAGNITUDE: self._standard_normals(key, "lm"),
        }
        base_s = {v: baseline[v].transform(z[v]) for v in VARIABLES}
        # Same standardized position for the moved variable on the exception side.
        moved_exc = with_exception.transform(z[moved])

        other_a, other_b = (v for v in VARIABLES if v != moved)
        out = [0.0] * n
        for i in range(n):
            out[i] = base_s[other_a][i] * base_s[other_b][i] * (moved_exc[i] - base_s[moved][i])
        return out

    @staticmethod
    def sum_streams(streams: list[list[float]]) -> list[float]:
        """Element-wise sum of independent sample streams (sum of independent RVs)."""
        if not streams:
            raise ValueError("no streams to sum")
        n = len(streams[0])
        out = [0.0] * n
        for s in streams:
            if len(s) != n:
                raise ValueError("streams must be the same length")
            for i in range(n):
                out[i] += s[i]
        return out


def appetite_state(residual: Band, threshold: float) -> str:
    """Three-state comparison of a residual band to a numeric appetite.

    * ``over`` -- the whole 90% band sits above the threshold.
    * ``within`` -- the whole band sits below it.
    * ``straddling`` -- the band crosses it (so whether you are over depends on
      the high end). Never a binary.
    """
    if residual.low >= threshold:
        return "over"
    if residual.high <= threshold:
        return "within"
    return "straddling"
