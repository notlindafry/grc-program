"""Monte Carlo engine: fits, bands, appetite states, contribution properties."""

from __future__ import annotations

import math

import pytest

from risk_ledger.montecarlo import (
    OPPORTUNITY_FREQUENCY,
    LOSS_MAGNITUDE,
    PROBABILITY_OF_REALIZATION,
    Band,
    MonteCarlo,
    appetite_state,
    fit_distribution,
    percentile,
)


@pytest.mark.parametrize(
    "variable,low,high",
    [
        (OPPORTUNITY_FREQUENCY, 12, 50),
        (LOSS_MAGNITUDE, 250000, 600000),
        (PROBABILITY_OF_REALIZATION, 0.01, 0.05),
        (PROBABILITY_OF_REALIZATION, 0.08, 0.30),
    ],
)
def test_fit_recovers_90ci(variable, low, high):
    mc = MonteCarlo(iterations=40000, seed=1)
    dist = fit_distribution(variable, low, high)
    samples = sorted(dist.transform(mc._standard_normals("t", variable)))
    assert percentile(samples, 5) == pytest.approx(low, rel=0.03)
    assert percentile(samples, 95) == pytest.approx(high, rel=0.03)


def test_probability_samples_stay_in_unit_interval():
    mc = MonteCarlo(iterations=10000, seed=2)
    dist = fit_distribution(PROBABILITY_OF_REALIZATION, 0.01, 0.4)
    samples = dist.transform(mc._standard_normals("p"))
    assert all(0.0 < s < 1.0 for s in samples)


def test_fit_rejects_point_estimates_and_bad_ranges():
    with pytest.raises(ValueError):
        fit_distribution(OPPORTUNITY_FREQUENCY, 10, 10)  # not increasing
    with pytest.raises(ValueError):
        fit_distribution(LOSS_MAGNITUDE, 0, 100)  # lognormal needs positive low
    with pytest.raises(ValueError):
        fit_distribution(PROBABILITY_OF_REALIZATION, 0.5, 1.5)  # probability out of (0,1)


def test_percentile_interpolates():
    data = [0.0, 10.0]
    assert percentile(data, 0) == 0.0
    assert percentile(data, 100) == 10.0
    assert percentile(data, 50) == pytest.approx(5.0)


def test_appetite_state_three_way():
    over = Band(low=900_000, high=1_700_000, mean=1_200_000)
    straddling = Band(low=400_000, high=800_000, mean=600_000)
    within = Band(low=50_000, high=300_000, mean=150_000)
    assert appetite_state(over, 500_000) == "over"
    assert appetite_state(straddling, 600_000) == "straddling"
    assert appetite_state(within, 500_000) == "within"


def test_contribution_is_paired_and_nonnegative_for_upward_move():
    """A clearly-worsening exception adds positive risk in every scenario."""
    mc = MonteCarlo(iterations=8000, seed=3)
    baseline = {
        OPPORTUNITY_FREQUENCY: fit_distribution(OPPORTUNITY_FREQUENCY, 10, 40),
        PROBABILITY_OF_REALIZATION: fit_distribution(PROBABILITY_OF_REALIZATION, 0.005, 0.02),
        LOSS_MAGNITUDE: fit_distribution(LOSS_MAGNITUDE, 200000, 500000),
    }
    worse = fit_distribution(PROBABILITY_OF_REALIZATION, 0.08, 0.30)
    samples = mc.contribution_samples(
        moved=PROBABILITY_OF_REALIZATION, baseline=baseline, with_exception=worse, key="e1"
    )
    band = Band.from_samples(samples)
    assert band.low > 0  # whole 90% band positive
    assert min(samples) >= -1e-6  # paired CRN: no spurious negative scenarios


def test_reproducible_same_seed():
    mc = MonteCarlo(iterations=5000, seed=42)
    a = mc.ale_samples(
        fit_distribution(OPPORTUNITY_FREQUENCY, 10, 40),
        fit_distribution(PROBABILITY_OF_REALIZATION, 0.01, 0.05),
        fit_distribution(LOSS_MAGNITUDE, 200000, 500000),
        key="r",
    )
    b = mc.ale_samples(
        fit_distribution(OPPORTUNITY_FREQUENCY, 10, 40),
        fit_distribution(PROBABILITY_OF_REALIZATION, 0.01, 0.05),
        fit_distribution(LOSS_MAGNITUDE, 200000, 500000),
        key="r",
    )
    assert a == b  # identical streams from identical keys


def test_independent_keys_differ():
    mc = MonteCarlo(iterations=2000, seed=42)
    z1 = mc._standard_normals("a")
    z2 = mc._standard_normals("b")
    assert z1 != z2
