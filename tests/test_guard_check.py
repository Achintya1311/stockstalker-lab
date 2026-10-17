from pathlib import Path

from scripts.guard_check import find_violations, is_protected, load_protected_entries

REAL_PROTECTED = Path(__file__).resolve().parent.parent / "PROTECTED.txt"


def test_load_protected_entries_skips_comments_and_blanks(tmp_path):
    path = tmp_path / "PROTECTED.txt"
    path.write_text("# a comment\n\nSPEC.md\nengine/\n  # indented comment\n")
    assert load_protected_entries(path) == ["SPEC.md", "engine/"]


def test_load_protected_entries_reads_the_real_file():
    entries = load_protected_entries(REAL_PROTECTED)
    assert "SPEC.md" in entries
    assert "PROTECTED.txt" in entries
    assert "config/splits.yml" in entries
    assert "engine/" in entries
    assert "gates/" in entries
    assert ".github/" in entries


def test_is_protected_exact_file_match():
    entries = ["SPEC.md", "config/splits.yml"]
    assert is_protected("SPEC.md", entries) is True
    assert is_protected("config/splits.yml", entries) is True
    assert is_protected("config/universe.yml", entries) is False
    assert is_protected("README.md", entries) is False


def test_is_protected_directory_prefix_match():
    entries = ["engine/", "gates/"]
    assert is_protected("engine/replay.py", entries) is True
    assert is_protected("engine/sub/deep.py", entries) is True
    assert is_protected("gates/gates.py", entries) is True
    assert is_protected("strategies/champion_v1.py", entries) is False
    # a path that merely starts with the same prefix string, but isn't inside
    # the directory, must not false-positive
    assert is_protected("engine_v2/other.py", entries) is False


def test_is_protected_bare_directory_name_without_trailing_slash():
    entries = [".github/"]
    assert is_protected(".github", entries) is True
    assert is_protected(".github/workflows/dataset.yml", entries) is True


def test_find_violations_filters_a_mixed_change_list():
    entries = load_protected_entries(REAL_PROTECTED)
    changed = [
        "strategies/champion_v1.py",
        "SPEC.md",
        "gates/gates.py",
        "reports/champion_v1_train.md",
        ".github/workflows/replay.yml",
    ]
    assert find_violations(changed, entries) == ["SPEC.md", "gates/gates.py", ".github/workflows/replay.yml"]


def test_find_violations_empty_when_nothing_protected_touched():
    entries = load_protected_entries(REAL_PROTECTED)
    changed = ["strategies/champion_v1.py", "reports/champion_v1_train.md", "cards/catalog.csv"]
    assert find_violations(changed, entries) == []
