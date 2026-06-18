"""The one engine. Drift, appetite, and the ranked list are three lenses on it.

It computes, once:

* the **baseline ALE** band for every computable risk,
* the **marginal contribution** band of every computable exception, and
* the **current residual** band and appetite state for every risk (baseline plus
  the summed contributions of its active, trusted exceptions).

Contributions are summed as independent marginal estimates. Real effects can
interact; this is a deliberate light-fidelity simplification, stated plainly
rather than hidden.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .loader import Corpus
from .models import Exception_, Risk
from .montecarlo import (
    OPPORTUNITY_FREQUENCY,
    LOSS_MAGNITUDE,
    PROBABILITY_OF_REALIZATION,
    Band,
    Distribution,
    MonteCarlo,
    appetite_state,
    fit_distribution,
)


@dataclass
class Contributor:
    exception: Exception_
    band: Band


@dataclass
class ResidualResult:
    risk: Risk
    baseline: Band
    band: Band
    state: str  # over | straddling | within
    threshold: float
    # Active, trusted exceptions that entered the band, ranked by expected
    # contribution (descending). The mean is a sort key only.
    contributors: list[Contributor] = field(default_factory=list)
    # Active exceptions whose number is not trusted (uncalibrated, vague scope):
    # computed for visibility but kept OUT of the band above.
    untrusted: list[Contributor] = field(default_factory=list)


class Engine:
    def __init__(self, corpus: Corpus, config: Config):
        self.corpus = corpus
        self.config = config
        self.mc = MonteCarlo(iterations=config.iterations, seed=config.seed)

        self._risk_dists: dict[str, dict[str, Distribution]] = {}
        self._baseline_samples: dict[str, list[float]] = {}
        self._baseline_band: dict[str, Band] = {}
        self._contrib_samples: dict[str, list[float]] = {}
        self._contrib_band: dict[str, Band] = {}
        self._residual: dict[str, ResidualResult] = {}
        self._residual_samples: dict[str, list[float]] = {}

        self._compute_baselines()
        self._compute_contributions()
        self._compute_residuals()

    # -- baselines ----------------------------------------------------------

    def _compute_baselines(self) -> None:
        for rid, risk in self.corpus.risks.items():
            dists = self._fit_risk(risk)
            if dists is None:
                continue
            self._risk_dists[rid] = dists
            samples = self.mc.ale_samples(
                dists[OPPORTUNITY_FREQUENCY],
                dists[PROBABILITY_OF_REALIZATION],
                dists[LOSS_MAGNITUDE],
                key=f"baseline|{rid}",
            )
            self._baseline_samples[rid] = samples
            self._baseline_band[rid] = Band.from_samples(samples)

    def _fit_risk(self, risk: Risk) -> dict[str, Distribution] | None:
        try:
            return {
                OPPORTUNITY_FREQUENCY: fit_distribution(OPPORTUNITY_FREQUENCY, *risk.opportunity_frequency_90ci),
                PROBABILITY_OF_REALIZATION: fit_distribution(
                    PROBABILITY_OF_REALIZATION, *risk.probability_of_realization_90ci
                ),
                LOSS_MAGNITUDE: fit_distribution(LOSS_MAGNITUDE, *risk.loss_magnitude_90ci),
            }
        except (ValueError, TypeError):
            return None  # malformed baseline; validation reports it as an error

    def risk_is_computable(self, rid: str) -> bool:
        return rid in self._risk_dists

    # -- contributions ------------------------------------------------------

    def _compute_contributions(self) -> None:
        for exc in self.corpus.exceptions:
            if not exc.is_computable:
                continue
            if exc.mapped_risk not in self._risk_dists:
                continue
            try:
                exc_dist = fit_distribution(exc.moves, *exc.with_exception_90ci)
            except (ValueError, TypeError):
                continue
            samples = self.mc.contribution_samples(
                moved=exc.moves,
                baseline=self._risk_dists[exc.mapped_risk],
                with_exception=exc_dist,
                key=f"contrib|{exc.id}",
            )
            self._contrib_samples[exc.id] = samples
            self._contrib_band[exc.id] = Band.from_samples(samples)

    def contribution_band(self, exc_id: str) -> Band | None:
        return self._contrib_band.get(exc_id)

    def contribution_samples(self, exc_id: str) -> list[float] | None:
        return self._contrib_samples.get(exc_id)

    # -- residuals ----------------------------------------------------------

    def _compute_residuals(self) -> None:
        for rid in self._risk_dists:
            self._residual[rid] = self._residual_for(rid)

    def _residual_for(self, rid: str) -> ResidualResult:
        risk = self.corpus.risks[rid]
        baseline_samples = self._baseline_samples[rid]

        trusted: list[Contributor] = []
        untrusted: list[Contributor] = []
        streams = [baseline_samples]
        for exc in self.corpus.exceptions:
            if exc.mapped_risk != rid or not exc.is_active:
                continue
            samples = self._contrib_samples.get(exc.id)
            if samples is None:
                continue
            band = self._contrib_band[exc.id]
            if exc.counts_in_bands:
                trusted.append(Contributor(exc, band))
                streams.append(samples)
            else:
                untrusted.append(Contributor(exc, band))

        residual_samples = self.mc.sum_streams(streams)
        self._residual_samples[rid] = residual_samples
        residual_band = Band.from_samples(residual_samples)
        trusted.sort(key=lambda c: c.band.mean, reverse=True)
        untrusted.sort(key=lambda c: c.band.mean, reverse=True)
        return ResidualResult(
            risk=risk,
            baseline=self._baseline_band[rid],
            band=residual_band,
            state=appetite_state(residual_band, risk.appetite_threshold),
            threshold=risk.appetite_threshold,
            contributors=trusted,
            untrusted=untrusted,
        )

    def residual(self, rid: str) -> ResidualResult | None:
        return self._residual.get(rid)

    def residual_samples(self, rid: str) -> list[float] | None:
        return self._residual_samples.get(rid)

    def all_residuals(self) -> list[ResidualResult]:
        return [self._residual[rid] for rid in self._risk_dists]

    def single_acceptance_state(self, rid: str, exc_id: str) -> str | None:
        """Appetite state if this risk carried *only* this one exception.

        Used to tell an accumulation breach (every exception tolerable alone,
        together over) from a single-acceptance breach (one exception over by
        itself).
        """
        base = self._baseline_samples.get(rid)
        contrib = self._contrib_samples.get(exc_id)
        if base is None or contrib is None:
            return None
        samples = self.mc.sum_streams([base, contrib])
        return appetite_state(Band.from_samples(samples), self.corpus.risks[rid].appetite_threshold)

    def portfolio_residual_band(self) -> Band | None:
        """Total residual the organization is carrying across all tracked risks."""
        streams = list(self._residual_samples.values())
        if not streams:
            return None
        return Band.from_samples(self.mc.sum_streams(streams))

    def portfolio_appetite_total(self) -> float:
        return sum(
            self.corpus.risks[rid].appetite_threshold for rid in self._risk_dists
        )

    # -- combine arbitrary exception sets into one band (used by drift) -----

    def combined_band(self, exc_ids: list[str]) -> Band | None:
        streams = [self._contrib_samples[e] for e in exc_ids if e in self._contrib_samples]
        if not streams:
            return None
        return Band.from_samples(self.mc.sum_streams(streams))

    def residual_with(self, rid: str, exc_ids: list[str]) -> Band | None:
        """Residual band if ``rid`` carried only the given exceptions (plus baseline).

        Used for the ranked list's tail-risk catch: a cluster whose expected
        residual stays within appetite but whose upper bound alone breaches.
        """
        base = self._baseline_samples.get(rid)
        if base is None:
            return None
        streams = [base] + [
            self._contrib_samples[e] for e in exc_ids if e in self._contrib_samples
        ]
        return Band.from_samples(self.mc.sum_streams(streams))
