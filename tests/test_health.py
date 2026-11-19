# SPDX-FileCopyrightText: 2026 The Open Kannada Authors
# SPDX-License-Identifier: MIT OR Apache-2.0
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import health  # noqa: E402
import shaperglot_gate  # noqa: E402


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


def test_fixed_counts_only_kinds_that_fail_the_check():
    base = report({"F.ttf#0": {"collision": ["a"]}})
    now = report({"F.ttf#0": {}})
    assert health.compare(now, base, {"no_conjunct"})["fixed"] == {}


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
    with pytest.raises(health.UsageError, match="matches no file"):
        health.expand([str(tmp_path / "*.ttf")])


def test_patterns_expand_and_repeat_once(tmp_path):
    (tmp_path / "A.ttf").write_bytes(b"")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "B.otf").write_bytes(b"")
    got = health.expand([f"{tmp_path}/**/*.?tf {tmp_path}/A.ttf"])
    assert [p.name for p in got] == ["A.ttf", "B.otf"]


def test_list_inputs_split_on_spaces_new_lines_and_commas():
    assert health.parse_kinds(["missing_glyph\nno_conjunct, notdef"]) == [
        "missing_glyph",
        "notdef",
        "no_conjunct",
    ]
    assert health.parse_codepoints(["U+0CBC\nU+0CBD"]) == {0x0CBC, 0x0CBD}


def test_bad_inputs_exit_with_2(tmp_path, capsys):
    assert health.main([str(tmp_path / "*.ttf")]) == 2
    assert "matches no file" in capsys.readouterr().err
    (tmp_path / "A.ttf").write_bytes(b"")
    assert health.main([str(tmp_path / "A.ttf"), "--fail-on", "no_such_kind"]) == 2
    assert health.main([str(tmp_path / "A.ttf"), "--allow-missing", "U+XYZ"]) == 2


def test_a_file_that_is_not_a_font_exits_with_2(tmp_path, monkeypatch, capsys):
    def boom(paths, allowed, proofs):
        raise health.UsageError(f"{paths[0]} is not a readable font: bad")

    monkeypatch.setattr(health, "run", boom)
    (tmp_path / "README.ttf").write_text("hello")
    assert health.main([str(tmp_path / "README.ttf")]) == 2
    assert "not a readable font" in capsys.readouterr().err


def test_main_exits_1_on_new_failures_and_0_with_a_baseline(tmp_path, monkeypatch):
    font = tmp_path / "F.ttf"
    font.write_bytes(b"")
    key = f"{font.as_posix()}#0"

    def fake(paths, allowed, proofs):
        faces = {key: {"failures": {"no_conjunct": ["a"]}}}
        return {"cases": 1, "texts": {"a": "x"}, "faces": faces, "files": [font.as_posix()]}

    monkeypatch.setattr(health, "run", fake)
    out = tmp_path / "r.json"
    files = tmp_path / "files.txt"
    assert health.main([str(font), "--report", str(out), "--kannada-files", str(files)]) == 1
    assert files.read_text() == font.as_posix() + "\n"
    assert (
        health.main([str(font), "--report", str(tmp_path / "s.json"), "--baseline", str(out)]) == 0
    )


def test_proof_names_differ_for_the_same_stem_in_2_folders():
    a = health.proof_name(Path("ttf/Foo.ttf"), 0)
    b = health.proof_name(Path("otf/Foo.otf"), 0)
    assert a != b and a.endswith("-0.png")


def test_shaperglot_gate_reads_code_points_in_any_case_and_separator():
    assert shaperglot_gate.allowed_chars(["u+0cbc,U+0CBD", "0CDC"]) == {
        "\u0cbc",
        "\u0cbd",
        "\u0cdc",
    }
