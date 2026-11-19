# SPDX-FileCopyrightText: 2026 The Open Kannada Authors
# SPDX-License-Identifier: MIT OR Apache-2.0
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import health  # noqa: E402


@dataclass
class Case:
    id: str


@dataclass
class Result:
    case: Case
    failures: list[str]
    missing: list[int] = field(default_factory=list)


def report(faces: dict) -> dict:
    return {
        "fontqa": "0123456789abcdef",
        "fail_on": ["missing_glyph", "no_conjunct"],
        "cases": 3,
        "texts": {"a": "ಕ್ಕ", "b": "ಕ್ಷ", "c": "೜"},
        "faces": {k: {"failures": v} for k, v in faces.items()},
    }


def test_parse_codepoints_accepts_prefixes_commas_and_case():
    assert health.parse_codepoints(["U+0CDC, u+0cf3", "0CDD"]) == {0x0CDC, 0x0CF3, 0x0CDD}


def test_missing_only_allowed_characters_is_not_a_failure():
    results = [
        Result(Case("c"), ["missing_glyph"], [0x0CDC]),
        Result(Case("d"), ["missing_glyph"], [0x0CDC, 0x0CF3]),
        Result(Case("a"), ["no_conjunct", "collision"]),
    ]
    got = health.face_failures(results, {0x0CDC})
    assert got == {"collision": ["a"], "missing_glyph": ["d"], "no_conjunct": ["a"]}


def test_without_baseline_every_failure_of_a_fail_on_kind_is_new():
    r = report({"F.ttf#0": {"no_conjunct": ["a", "b"], "collision": ["a"]}})
    diff = health.compare(r, None, {"no_conjunct"})
    assert diff == {"new": {"F.ttf#0": {"no_conjunct": ["a", "b"]}}, "fixed": {}}


def test_baseline_failures_are_known_and_fixed_ones_are_reported():
    base = report({"F.ttf#0": {"no_conjunct": ["a", "c"]}})
    now = report({"F.ttf#0": {"no_conjunct": ["a", "b"]}})
    diff = health.compare(now, base, {"no_conjunct"})
    assert diff["new"] == {"F.ttf#0": {"no_conjunct": ["b"]}}
    assert diff["fixed"] == {"F.ttf#0": {"no_conjunct": ["c"]}}


def test_a_new_face_has_no_baseline():
    base = report({"F.ttf#0": {"no_conjunct": ["a"]}})
    now = report({"F.ttf#0": {"no_conjunct": ["a"]}, "G.ttf#0": {"no_conjunct": ["a"]}})
    assert health.compare(now, base, {"no_conjunct"})["new"] == {"G.ttf#0": {"no_conjunct": ["a"]}}


def test_summary_lists_new_failures_with_their_text_and_caps_the_list():
    now = report({"F.ttf#0": {"no_conjunct": ["a", "b"]}})
    diff = health.compare(now, None, {"no_conjunct"})
    text = health.summary_markdown(now, diff, shown=1)
    assert "| `F.ttf#0` | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 2 |" in text
    assert "- no_conjunct: `a` ಕ್ಕ" in text
    assert "and 1 more" in text


def test_summary_says_when_nothing_is_new():
    now = report({"F.ttf#0": {}})
    text = health.summary_markdown(now, health.compare(now, None, {"no_conjunct"}))
    assert "No new failures." in text


def test_a_pattern_that_matches_nothing_is_an_error(tmp_path):
    with pytest.raises(SystemExit, match="matches no file"):
        health.expand([str(tmp_path / "*.ttf")])


def test_patterns_expand_and_repeat_once(tmp_path):
    (tmp_path / "A.ttf").write_bytes(b"")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "B.otf").write_bytes(b"")
    got = health.expand([f"{tmp_path}/**/*.?tf {tmp_path}/A.ttf"])
    assert [p.name for p in got] == ["A.ttf", "B.otf"]
