# SPDX-FileCopyrightText: 2026 The Open Kannada Authors
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Shape kannadi's fontqa test strings in font files, compare the failures with a baseline,
and write a JSON report and a Markdown summary.

Runs in fontqa's environment:

    uv run --project KANNADI/tools/fontqa python health.py FONT... [options]

Exit status: 0 when no failure of a --fail-on kind is missing from the baseline, 1 when one
is, 2 for a usage error such as a path that matches no font.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
import unicodedata
from pathlib import Path

FAILURES = (
    "missing_glyph", "notdef", "dotted_circle", "no_conjunct", "no_arkavattu", "collision",
    "indistinct",
)  # fmt: skip
DEFAULT_FAIL_ON = ("missing_glyph", "notdef", "dotted_circle", "no_conjunct", "no_arkavattu")
# Faces with fewer Kannada characters than this are other scripts in a shared collection file.
MIN_KANNADA = 40
SHOWN = 25


class UsageError(Exception):
    """A bad input: exit status 2."""


def tokens(items: list[str]) -> list[str]:
    """Items split on white space, new lines and commas, as the action passes them."""
    return [t for item in items for t in item.replace(",", " ").split()]


def parse_codepoints(items: list[str]) -> set[int]:
    try:
        return {int(t.upper().removeprefix("U+"), 16) for t in tokens(items)}
    except ValueError as e:
        raise UsageError(f"not a code point: {e}") from e


def parse_kinds(items: list[str]) -> list[str]:
    kinds = tokens(items)
    unknown = [k for k in kinds if k not in FAILURES]
    if unknown:
        raise UsageError(f"unknown failure kind {', '.join(unknown)}; use {', '.join(FAILURES)}")
    return sorted(set(kinds), key=FAILURES.index)


def expand(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for token in [t for p in patterns for t in p.split()]:
        # A file that exists is taken as named: variable fonts are often called Foo[wght].ttf.
        matches = [token] if Path(token).is_file() else sorted(glob.glob(token, recursive=True))
        if not matches:
            raise UsageError(f"{token} matches no file")
        paths += [Path(m) for m in matches if Path(m).is_file()]
    return list(dict.fromkeys(paths))


def face_failures(results, allowed_missing: set[int]) -> dict[str, list[str]]:
    """Case ids by failure kind. A case missing only allowed characters is not a failure."""
    out: dict[str, list[str]] = {}
    for r in results:
        for kind in r.failures:
            if kind == "missing_glyph" and set(r.missing) <= allowed_missing:
                continue
            out.setdefault(kind, []).append(r.case.id)
    return {k: sorted(v) for k, v in sorted(out.items())}


def face_details(results, allowed_missing: set[int]) -> dict[str, dict]:
    """What went wrong in each failing case: missing code points, the strings it is drawn
    like, and the glyphs that collide."""
    out: dict[str, dict] = {}
    for r in results:
        detail = {}
        missing = [f"U+{c:04X}" for c in r.missing if c not in allowed_missing]
        if missing:
            detail["missing"] = missing
        if r.same_as:
            detail["same_as"] = sorted(r.same_as)
        if r.collisions:
            detail["collisions"] = [[c.a, c.b, round(c.share, 3)] for c in r.collisions]
        if detail:
            out[r.case.id] = detail
    return out


# Names Python's Unicode data may not know yet.
NAMES = {0x0CDC: "KANNADA ARCHAIC SHRII", 0x0CDD: "KANNADA LETTER NAKAARA POLLU",
         0x0CF3: "KANNADA SIGN COMBINING ANUSVARA ABOVE RIGHT"}  # fmt: skip


def char_name(code: str) -> str:
    cp = int(code[2:], 16)
    return f"{code} {NAMES.get(cp) or unicodedata.name(chr(cp), '')}".strip()


KIND_WORDS = {
    "missing_glyph": "missing characters",
    "notdef": ".notdef glyphs",
    "dotted_circle": "dotted circles",
    "no_conjunct": "no conjunct",
    "no_arkavattu": "no arkavattu",
    "collision": "collisions",
    "indistinct": "strings drawn alike",
}


def compare(report: dict, baseline: dict | None, fail_on: set[str]) -> dict:
    """New failures (in the report, of a --fail-on kind, not in the baseline) and fixed ones
    (in the baseline, no longer failing), by face and kind."""
    known = (baseline or {}).get("faces", {})
    new: dict[str, dict[str, list[str]]] = {}
    fixed: dict[str, dict[str, list[str]]] = {}
    for face, entry in report["faces"].items():
        before = known.get(face, {}).get("failures", {})
        for kind, cases in entry["failures"].items():
            if kind not in fail_on:
                continue
            added = sorted(set(cases) - set(before.get(kind, [])))
            if added:
                new.setdefault(face, {})[kind] = added
        for kind, cases in before.items():
            if kind not in fail_on:
                continue
            gone = sorted(set(cases) - set(entry["failures"].get(kind, [])))
            if gone:
                fixed.setdefault(face, {})[kind] = gone
    return {"new": new, "fixed": fixed}


ORDER = (
    "dotted_circle",
    "notdef",
    "no_conjunct",
    "no_arkavattu",
    "missing_glyph",
    "collision",
    "indistinct",
)
MEANING = {
    "dotted_circle": "the shaper could not attach a sign and drew a dotted circle.",
    "notdef": "the shaped text holds the .notdef glyph, though every character is mapped.",
    "no_conjunct": "the consonant after the virama should be drawn as a subscript (ottu); "
    "the font draws the same glyphs as with a ZWNJ: a visible virama and 2 letters.",
    "no_arkavattu": "ರ with a virama before a consonant should become the arkavattu; "
    "the font keeps ರ as a full letter, with a visible virama or the consonant below it.",
    "collision": "a mark overlaps a glyph other than its base letter by more than 3% of "
    "the smaller glyph's ink; the glyphs are named as the font names them.",
    "indistinct": "the string is drawn with exactly the same ink as a different string.",
}
EXAMPLES = 6


def strings(n: int) -> str:
    return f"{n} string" + ("" if n == 1 else "s")


def example(kind: str, case: str, report: dict, face: str) -> str:
    """1 failing string, with what is specific to it."""
    text = report["texts"].get(case, "")
    detail = report["faces"][face].get("details", {}).get(case, {})
    if kind == "collision" and detail.get("collisions"):
        parts = "; ".join(f"{a} and {b} by {share:.0%}" for a, b, share in detail["collisions"])
        return f"{text} (`{case}`): {parts}"
    if kind == "indistinct" and detail.get("same_as"):
        others = ", ".join(detail["same_as"])
        return f"{text} (`{case}`) is drawn like {others}"
    return f"{text} (`{case}`)"


def new_failures(report: dict, face: str, kinds: dict[str, list[str]], shown: int) -> list[str]:
    """1 paragraph per failure kind: what it means, how many strings, and examples."""
    out = []
    details = report["faces"][face].get("details", {})
    for kind in sorted(kinds, key=ORDER.index):
        cases = kinds[kind]
        title = f"**{KIND_WORDS[kind].capitalize()}, {strings(len(cases))}.**"
        if kind == "missing_glyph":
            by_char: dict[str, list[str]] = {}
            for case in cases:
                for code in details.get(case, {}).get("missing", []):
                    by_char.setdefault(code, []).append(case)
            out.append(f"{title} The font has no glyph with ink for:")
            for code, where in sorted(by_char.items(), key=lambda kv: -len(kv[1]))[:shown]:
                sample = report["texts"].get(where[0], "")
                out.append(f"- {char_name(code)}, needed by {strings(len(where))} such as {sample}")
        else:
            out.append(f"{title} In each, {MEANING[kind]}")
            out += [
                f"- {example(kind, case, report, face)}" for case in cases[: min(shown, EXAMPLES)]
            ]
            if len(cases) > EXAMPLES:
                out.append(f"- and {len(cases) - EXAMPLES} more, in the JSON report")
        out.append("")
    return out


def summary_markdown(report: dict, diff: dict, shown: int = SHOWN) -> str:
    lines = ["## Kannada font health", ""]
    lines.append(
        f"{report['cases']} Kannada test strings shaped with HarfBuzz (kannadi fontqa "
        f"`{report['fontqa'][:12]}`). The check fails on: "
        f"{', '.join(KIND_WORDS[k] for k in report['fail_on']) or 'nothing'}."
    )
    lines += [
        "",
        "| Face | Result | New failures | Known failures | Other findings |",
        "|---|---|---:|---:|---|",
    ]
    for face, entry in report["faces"].items():
        added = sum(len(v) for v in diff["new"].get(face, {}).values())
        failing = sum(len(entry["failures"].get(k, [])) for k in report["fail_on"])
        others = ", ".join(
            f"{len(entry['failures'][k])} {KIND_WORDS[k]}"
            for k in FAILURES if k not in report["fail_on"] and entry["failures"].get(k)
        ) or "none"  # fmt: skip
        result = "fail" if added else "pass"
        lines.append(f"| `{face}` | {result} | {added} | {failing - added} | {others} |")
    for face, kinds in diff["new"].items():
        lines += ["", f"### New failures in `{face}`", ""]
        lines += new_failures(report, face, kinds, shown)
    if diff["fixed"]:
        count = sum(len(c) for kinds in diff["fixed"].values() for c in kinds.values())
        lines += ["", f"{count} failures in the baseline no longer occur; update the baseline."]
    if not diff["new"]:
        lines += ["", "No new failures."]
    return "\n".join(lines) + "\n"


def proof_name(path: Path, index: int) -> str:
    """A file name unique to the path, so Foo.ttf and Foo.otf in 2 folders do not collide."""
    parts = path.with_suffix("").parts[1:] if path.is_absolute() else path.with_suffix("").parts
    return "_".join(p for p in parts if p not in ("", ".", "..")) + f"{path.suffix}-{index}.png"


def run(paths: list[Path], allowed_missing: set[int], proofs: Path | None) -> dict:
    from fontqa.checks import mark_indistinct, run_case
    from fontqa.kannada import all_cases
    from fontqa.shaping import faces_in

    cases = all_cases()
    faces: dict[str, dict] = {}
    files: list[str] = []
    for path in paths:
        try:
            found = faces_in(path)
        except Exception as e:
            raise UsageError(f"{path} is not a readable font: {e}") from e
        for face in found:
            key = f"{path.as_posix()}#{face.index}"
            if face.info["kannada_codepoints"] < MIN_KANNADA:
                print(f"{key}: not a Kannada face, skipped")
                continue
            results = [run_case(face, case) for case in cases]
            mark_indistinct(face, results)
            faces[key] = {
                "failures": face_failures(results, allowed_missing),
                "details": face_details(results, allowed_missing),
            }
            if path.as_posix() not in files:
                files.append(path.as_posix())
            counts = ", ".join(f"{k} {len(v)}" for k, v in faces[key]["failures"].items())
            print(f"{key}: {counts or 'all pass'}")
            if proofs:
                from fontqa.proof import sheet

                sheet(face, results, proofs / proof_name(path, face.index), None)
    texts = {c.id: c.text for c in cases}
    return {"cases": len(cases), "texts": texts, "faces": faces, "files": files}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("fonts", nargs="+", help="font files or glob patterns")
    p.add_argument("--fail-on", nargs="*", default=list(DEFAULT_FAIL_ON), help=", ".join(FAILURES))
    p.add_argument("--baseline", type=Path, help="a report whose failures are known")
    p.add_argument("--allow-missing", nargs="*", default=[], help="code points, e.g. U+0CDC")
    p.add_argument("--report", type=Path, default=Path("font-health/report.json"))
    p.add_argument("--summary", type=Path, help="append the Markdown summary to this file")
    p.add_argument("--proofs", type=Path, help="write a proof sheet per face here")
    p.add_argument("--fontqa-ref", default="unknown", help="kannadi commit, for the report")
    p.add_argument("--kannada-files", type=Path, help="write the files with a Kannada face here")
    args = p.parse_args(argv)
    try:
        return check(args)
    except UsageError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


def check(args: argparse.Namespace) -> int:
    baseline = None
    if args.baseline:
        try:
            baseline = json.loads(args.baseline.read_text())
        except (OSError, ValueError) as e:
            raise UsageError(f"cannot read the baseline {args.baseline}: {e}") from e
    paths = expand(args.fonts)
    if not paths:
        raise UsageError("no font files")
    fail_on = parse_kinds(args.fail_on)
    allowed = parse_codepoints(args.allow_missing)
    report = run(paths, allowed, args.proofs)
    report = {
        "fontqa": args.fontqa_ref,
        "fail_on": fail_on,
        "allow_missing": [f"U+{c:04X}" for c in sorted(allowed)],
        **report,
    }
    if not report["faces"]:
        raise UsageError("no Kannada face in the given fonts")
    if args.kannada_files:
        args.kannada_files.write_text("".join(f + "\n" for f in report["files"]))
    diff = compare(report, baseline, set(fail_on))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({**report, **diff}, ensure_ascii=False, indent=1) + "\n")
    markdown = summary_markdown(report, diff)
    if args.summary:
        with args.summary.open("a") as f:
            f.write(markdown)
    print(markdown)
    return 1 if diff["new"] else 0


if __name__ == "__main__":
    sys.exit(main())
