"""Config loading, overrides, and validation of the breach threshold."""

from __future__ import annotations

import pytest

from risk_ledger.config import DEFAULT_SINGLE_ACCEPTANCE_SHARE, Config


def test_defaults():
    cfg = Config()
    assert cfg.single_acceptance_share == DEFAULT_SINGLE_ACCEPTANCE_SHARE


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.5])
def test_single_acceptance_share_must_be_in_unit_interval(bad):
    with pytest.raises(ValueError):
        Config(single_acceptance_share=bad)


def test_load_reads_breach_section(tmp_path):
    (tmp_path / "config.yaml").write_text(
        "monte_carlo:\n  seed: 1\nbreach:\n  single_acceptance_share: 0.7\n"
    )
    cfg = Config.load(tmp_path)
    assert cfg.single_acceptance_share == 0.7
    assert cfg.seed == 1


def test_load_rejects_bad_breach_value(tmp_path):
    (tmp_path / "config.yaml").write_text("breach:\n  single_acceptance_share: 2\n")
    with pytest.raises(ValueError):
        Config.load(tmp_path)
