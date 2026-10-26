import json

import pytest

from picks.source import _REGISTRY, DEFAULT_SOURCE, load_live_source, resolve_strategy


def test_resolve_strategy_imports_the_registered_module():
    module = resolve_strategy("champion_v1@v1")
    assert hasattr(module, "score")
    assert hasattr(module, "rules_fired")


def test_resolve_strategy_rejects_an_unknown_id():
    with pytest.raises(ValueError):
        resolve_strategy("not-a-real-strategy@v1")


def test_load_live_source_dry_mode_falls_back_to_champion_v1_when_missing(tmp_path):
    missing = tmp_path / "live_source.json"
    assert load_live_source("dry", missing, tmp_path / "live_source.draft.json") == DEFAULT_SOURCE


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


def _source(strategy: str) -> dict:
    return {"chosen_on": "2026-10-30",
            "tables": {k: {"strategy": strategy, "label": "provisional", "why": "x"}
                       for k in ("day_bullish", "day_bearish", "week_bullish", "week_bearish")}}


def test_dry_mode_uses_the_draft_when_the_real_file_is_missing(tmp_path):
    draft = tmp_path / "live_source.draft.json"
    draft.write_text(json.dumps(_source("e2a_a02_crowded@v1")))
    assert load_live_source("dry", tmp_path / "live_source.json", draft) == _source("e2a_a02_crowded@v1")


def test_live_mode_never_reads_the_draft(tmp_path):
    draft = tmp_path / "live_source.draft.json"
    draft.write_text(json.dumps(_source("e2a_a02_crowded@v1")))
    assert load_live_source("live", tmp_path / "live_source.json", draft) is None


def test_real_file_wins_over_the_draft(tmp_path):
    real, draft = tmp_path / "live_source.json", tmp_path / "live_source.draft.json"
    real.write_text(json.dumps(_source("champion_v1@v1")))
    draft.write_text(json.dumps(_source("e2a_a02_crowded@v1")))
    assert load_live_source("dry", real, draft) == _source("champion_v1@v1")


@pytest.mark.parametrize("strategy_id", sorted(_REGISTRY))
def test_every_registered_strategy_resolves(strategy_id):
    module = resolve_strategy(strategy_id)
    assert callable(module.score) and callable(module.rules_fired)


def test_committed_draft_names_only_registered_strategies():
    from picks.source import DRAFT_SOURCE_PATH, TABLE_KEYS
    if not DRAFT_SOURCE_PATH.exists():
        pytest.skip("no draft committed")
    draft = json.loads(DRAFT_SOURCE_PATH.read_text())
    assert set(draft["tables"]) == set(TABLE_KEYS)
    for cfg in draft["tables"].values():
        assert cfg["strategy"] in _REGISTRY and cfg["label"] in ("provisional", "gated")
