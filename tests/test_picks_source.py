import json

import pytest

from picks.source import DEFAULT_SOURCE, load_live_source, resolve_strategy


def test_resolve_strategy_imports_the_registered_module():
    module = resolve_strategy("champion_v1@v1")
    assert hasattr(module, "score")
    assert hasattr(module, "rules_fired")


def test_resolve_strategy_rejects_an_unknown_id():
    with pytest.raises(ValueError):
        resolve_strategy("not-a-real-strategy@v1")


def test_load_live_source_dry_mode_falls_back_to_champion_v1_when_missing(tmp_path):
    missing = tmp_path / "live_source.json"
    assert load_live_source("dry", missing) == DEFAULT_SOURCE


def test_load_live_source_live_mode_returns_none_when_missing(tmp_path):
    missing = tmp_path / "live_source.json"
    assert load_live_source("live", missing) is None


def test_load_live_source_reads_the_real_file_when_present_in_either_mode(tmp_path):
    path = tmp_path / "live_source.json"
    real = {
        "chosen_on": "2026-10-30",
        "tables": {
            "day_bullish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
            "day_bearish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
            "week_bullish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
            "week_bearish": {"strategy": "champion_v1@v1", "label": "provisional", "why": "x"},
        },
    }
    path.write_text(json.dumps(real))
    assert load_live_source("live", path) == real
    assert load_live_source("dry", path) == real
