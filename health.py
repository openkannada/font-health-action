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
from pathlib import Path

FAILURES = (
    "missing_glyph", "notdef", "dotted_circle", "no_conjunct", "no_arkavattu", "collision",
    "indistinct",
)  # fmt: skip
DEFAULT_FAIL_ON = ("missing_glyph", "notdef", "dotted_circle", "no_conjunct", "no_arkavattu")
# Faces with fewer Kannada characters than this are other scripts in a shared collection file.
MIN_KANNADA = 40
SHOWN = 25


def parse_codepoints(items: list[str]) -> set[int]:
    out = set()
    for item in items:
        for token in item.replace(",", " ").split():
            out.add(int(token.upper().removeprefix("U+"), 16))
    return out


def expand(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        for token in pattern.split():
            matches = sorted(glob.glob(token, recursive=True)) or []
            if not matches:
                raise SystemExit(f"error: {token} matches no file")
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
            gone = sorted(set(cases) - set(entry["failures"].get(kind, [])))
            if gone:
                fixed.setdefault(face, {})[kind] = gone
    return {"new": new, "fixed": fixed}


def summary_markdown(report: dict, diff: dict, shown: int = SHOWN) -> str:
    lines = ["## Kannada font health", ""]
    lines.append(
        f"{report['cases']} test strings from kannadi fontqa at `{report['fontqa'][:12]}`. "
        f"Failing on: {', '.join(report['fail_on']) or 'nothing'}."
    )
    header = "| Face | " + " | ".join(FAILURES) + " | New |"
    lines += ["", header, "|---" * (len(FAILURES) + 2) + "|"]
    for face, entry in report["faces"].items():
        counts = [str(len(entry["failures"].get(k, []))) for k in FAILURES]
        added = sum(len(v) for v in diff["new"].get(face, {}).values())
        lines.append(f"| `{face}` | " + " | ".join(counts) + f" | {added} |")
    for face, kinds in diff["new"].items():
        lines += ["", f"### New failures in `{face}`", ""]
        listed = [(kind, case) for kind, cases in kinds.items() for case in cases]
        for kind, case in listed[:shown]:
            text = report["texts"].get(case, "")
            lines.append(f"- {kind}: `{case}` {text}")
        if len(listed) > shown:
            lines.append(f"- and {len(listed) - shown} more in the JSON report")
    if diff["fixed"]:
        count = sum(len(c) for kinds in diff["fixed"].values() for c in kinds.values())
        lines += ["", f"{count} failures in the baseline no longer occur; update the baseline."]
    if not diff["new"]:
        lines += ["", "No new failures."]
    return "\n".join(lines) + "\n"


def run(paths: list[Path], allowed_missing: set[int], proofs: Path | None) -> dict:
    from fontqa.checks import mark_indistinct, run_case
    from fontqa.kannada import all_cases
    from fontqa.shaping import faces_in

    cases = all_cases()
    faces: dict[str, dict] = {}
    for path in paths:
        for face in faces_in(path):
            key = f"{path.as_posix()}#{face.index}"
            if face.info["kannada_codepoints"] < MIN_KANNADA:
                print(f"{key}: not a Kannada face, skipped")
                continue
            results = [run_case(face, case) for case in cases]
            mark_indistinct(face, results)
            faces[key] = {"failures": face_failures(results, allowed_missing)}
            counts = ", ".join(f"{k} {len(v)}" for k, v in faces[key]["failures"].items())
            print(f"{key}: {counts or 'all pass'}")
            if proofs:
                from fontqa.proof import sheet

                sheet(face, results, proofs / f"{path.stem}-{face.index}.png", None)
    return {"cases": len(cases), "texts": {c.id: c.text for c in cases}, "faces": faces}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("fonts", nargs="+", help="font files or glob patterns")
    p.add_argument("--fail-on", nargs="*", default=list(DEFAULT_FAIL_ON), choices=FAILURES)
    p.add_argument("--baseline", type=Path, help="a report whose failures are known")
    p.add_argument("--allow-missing", nargs="*", default=[], help="code points, e.g. U+0CDC")
    p.add_argument("--report", type=Path, default=Path("font-health/report.json"))
    p.add_argument("--summary", type=Path, help="append the Markdown summary to this file")
    p.add_argument("--proofs", type=Path, help="write a proof sheet per face here")
    p.add_argument("--fontqa-ref", default="unknown", help="kannadi commit, for the report")
    args = p.parse_args(argv)

    paths = expand(args.fonts)
    if not paths:
        print("error: no font files", file=sys.stderr)
        return 2
    allowed = parse_codepoints(args.allow_missing)
    report = run(paths, allowed, args.proofs)
    report = {
        "fontqa": args.fontqa_ref,
        "fail_on": sorted(args.fail_on, key=FAILURES.index),
        "allow_missing": [f"U+{c:04X}" for c in sorted(allowed)],
        **report,
    }
    if not report["faces"]:
        print("error: no Kannada face in the given fonts", file=sys.stderr)
        return 2
    baseline = json.loads(args.baseline.read_text()) if args.baseline else None
    diff = compare(report, baseline, set(args.fail_on))
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
