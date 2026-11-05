"""Pick reasoning describes conditions, never price levels (W109, SPEC.md section 10).

The desk shows each strategy's `rules_fired` text verbatim, so a level such as
"SMA200=2407.84" would publish a price. Every strategy is run on synthetic
stocks priced near 50,000 (so any printed level is a five-digit number, while
oscillators, ratios, sigmas and percentiles stay well below 10,000) and its
reasoning must contain no such number.
"""

from __future__ import annotations

import importlib
import inspect
import re
import warnings
from pathlib import Path

import numpy as np
import pytest

from tests._picks_dataset import make_dataset, trading_dates

STRATEGIES = Path(__file__).resolve().parent.parent / "strategies"
PRICE_SCALE = 500.0  # base close 100 -> 50,000
LEVEL = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\d.])\d{5,}(?:\.\d+)?")


def _modules() -> list[str]:
    names = []
    for path in sorted(STRATEGIES.glob("*.py")):
        if path.stem.endswith("_audit") or path.stem.startswith("_"):
            continue
        if "def rules_fired" in path.read_text():
            names.append(f"strategies.{path.stem}")
    return names


@pytest.fixture(scope="module")
def dataset():
    moves = {"UPA": 0.002, "DNB": -0.002, "UPC": 0.001, "DND": -0.001, "FLT": 0.0}
    ds = make_dataset(moves, trading_dates(320)).sort_values(["symbol", "date"]).reset_index(drop=True)
    wiggle = np.exp(np.cumsum(np.random.default_rng(7).normal(0.0, 0.015, len(ds))))
    for col in ("open", "high", "low", "close", "prevclose"):
        ds[col] = ds[col] * PRICE_SCALE * wiggle
    ds["high"] = ds[["open", "close"]].max(axis=1) * 1.01
    ds["low"] = ds[["open", "close"]].min(axis=1) * 0.99
    return ds


def test_scan_finds_the_strategies():
    assert "strategies.t04_connors_rsi2" in _modules()
    assert len(_modules()) > 50


@pytest.mark.parametrize("module", _modules())
def test_reasoning_has_no_price_level(module, dataset):
    mod = importlib.import_module(module)
    if len(inspect.signature(mod.rules_fired).parameters) != 2:
        pytest.skip(f"{module} is a shared core; its wrappers are scanned")
    for symbol in dataset["symbol"].unique():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                text = mod.rules_fired(dataset, symbol)
            except (KeyError, ValueError):
                pytest.skip(f"{module} needs columns the synthetic set lacks")
        assert not LEVEL.search(text), f"{module} prints a price level: {text}"


def test_pattern_catches_the_w109_text():
    assert LEVEL.search("close above SMA200=2407.84".replace("2407.84", "24078.40"))
    assert LEVEL.search("close 1,234.50")
    assert not LEVEL.search("RSI(2)=6.50 -> score +0.3499, +3.58 sigma, percentile 7% of 375 stocks")
