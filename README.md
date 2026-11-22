# font-health-action

Kannada shaping tests for any font repository, on every commit.

The action shapes 2,146 Kannada test strings in your fonts with HarfBuzz, the shaping engine in Chrome, Firefox, Android and LibreOffice, and runs [Shaperglot](https://github.com/googlefonts/shaperglot)'s `kn_Knda` checks. It fails when a font cannot form a conjunct or the arkavattu, puts a dotted circle in a word, or lacks a Kannada character. Each failure is reported in plain words, with the string, what a correct font does, and what yours did.

## Quick start

```yaml
on: [push, pull_request]
jobs:
  font-health:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: openkannada/font-health-action@v1
        with:
          fonts: fonts/ttf/*.ttf
```

A run takes about 30 seconds to set up and 1 to 2 seconds per font.

## What it checks

The strings come from [kannadi's fontqa](https://github.com/openkannada/kannadi/tree/main/tools/fontqa): every consonant with every vowel sign, every consonant cluster, the arkavattu on every consonant, clusters with vowel signs, the Old Kannada letters and the newest characters (ೝ, ೳ, U+0CDC). A string fails for 1 of these reasons:

| Failure | What a correct font does, and what went wrong |
|---|---|
| no conjunct | The consonant after a virama is drawn as a subscript (ottu). The font drew a visible virama and 2 letters. |
| no arkavattu | ರ with a virama before a consonant becomes the arkavattu. The font kept ರ as a full letter. |
| dotted circle | Every sign attaches to its letter. The shaper could not attach one and drew a dotted circle. |
| .notdef | Every character is drawn. The shaped text holds the missing-glyph box. |
| missing character | The font has a glyph, with ink, for each character in the string. |
| collision | Marks do not run into other glyphs. A mark overlaps a glyph other than its base letter by more than 3% of the smaller one's ink. |
| strings drawn alike | Different text looks different. 2 strings were drawn with exactly the same ink, such as ೄ drawn as ೃ. |

The first 5 fail the check by default. Collisions and look-alikes are reported for a person to judge, since some designs join strokes on purpose.

## Reading the results

The job summary has a table with 1 row per font face: pass or fail, new failures, known failures, and other findings. Under it, each kind of new failure gets 1 paragraph with examples, and missing characters are listed by character with how many strings need each.

The artifact `font-health` holds the full JSON report and 1 proof sheet per face. A proof sheet draws up to 40 failing strings of each kind large in your font, known failures included, with the overlap boxed in red for collisions. The report lists every failing string by id, kind and detail, and works as a baseline.

## Adopting it with known gaps

Most fonts have gaps today. Download the report from a first run, commit it, and pass it as `baseline`:

```yaml
      - uses: openkannada/font-health-action@v1
        with:
          fonts: Gari.ttf
          baseline: font-health/baseline.json
          allow-missing: U+0CBC U+0CBD
```

The check then fails only on failures the baseline does not list, and the summary says when a listed failure is fixed, so the baseline can shrink. A face is named by its path exactly as the `fonts` pattern matched it, and its index in the file, as in `Gari.ttf#0`; keep the same pattern, relative to the repository, between the run that made the baseline and later runs. The baseline covers the shaping strings only; for Shaperglot, list characters a font may lack in `allow-missing`, or set `shaperglot: false` until its other gaps are fixed.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `fonts` | required | Font files or glob patterns (TTF, OTF, TTC), separated by spaces or new lines. `**` matches folders. A file that exists is taken as named, so `Foo[wght].ttf` works. Paths with spaces do not. Fonts with fewer than 40 Kannada characters, such as a Latin companion font, are skipped. |
| `fail-on` | `missing_glyph notdef dotted_circle no_conjunct no_arkavattu` | The failure kinds that fail the check, separated by spaces, commas or new lines. The others are `collision` and `indistinct`. |
| `baseline` | none | A report from an earlier run. Its failures are known and do not fail the check. |
| `allow-missing` | none | Code points a font may lack, such as `U+0CDC`, for both checks. |
| `shaperglot` | `true` | Run Shaperglot's `kn_Knda` checks too. Font collections (TTC) are skipped there. |
| `report` | `font-health/report.json` | Where to write the JSON report. |
| `proofs` | `font-health/proofs` | Where to write the proof sheets. Empty for none. |
| `artifact` | `font-health` | Name of the artifact with the report and proof sheets. Empty for none. |
| `kannadi-ref` | a pinned commit | The kannadi commit whose test strings run. |
| `shaperglot-version` | `1.2.2` | The Shaperglot release on PyPI. |

To run the action more than once in a workflow, as in a matrix of font families, give each use its own `artifact`, `report` and `proofs`: artifact names must be unique in a run, and a second use would otherwise overwrite the first one's files.

## Outputs

| Output | What it is |
|---|---|
| `report` | The path of the JSON report. |

Run it on Linux: Shaperglot has no wheels for macOS on Apple Silicon. The action installs uv 0.12.17 with `astral-sh/setup-uv`, which later steps of the job also see.

## Running it locally

```bash
git clone https://github.com/openkannada/font-health-action
git clone https://github.com/openkannada/kannadi
uv sync --project kannadi/tools/fontqa
uv run --project kannadi/tools/fontqa python font-health-action/health.py MyFont.ttf --proofs proofs
```

`health.py --help` lists the options. It exits 0 when nothing new fails, 1 when something does, and 2 for bad input such as a pattern that matches no file.

## Contributing

Every commit needs a `Signed-off-by` line (`git commit -s`) under the [Developer Certificate of Origin](https://developercertificate.org/). The test strings live in kannadi's fontqa, so send changes to them there; this repository runs them. See the [Open Kannada contributing guide](https://github.com/openkannada/.github/blob/main/CONTRIBUTING.md) and the [changelog](CHANGELOG.md).

## Related

- [kannadi](https://github.com/openkannada/kannadi): the source of the test strings, in `tools/fontqa`.
- [Neha Sans and Neha Serif](https://github.com/openkannada/noto-kannada-fork) and [Gari](https://github.com/openkannada/gari-font): Kannada fonts that run this action on every commit. Download them at [openkannada.org/fonts](https://openkannada.org/fonts/).
- [Shaperglot](https://github.com/googlefonts/shaperglot): Google Fonts' language-support checker, whose main branch has Kannada conjunct and arkavattu checks since 1.2.2.

## License

The code is under the MIT license or the Apache License 2.0, at your choice: see [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE). The documentation is under [CC BY 4.0](LICENSES/CC-BY-4.0.txt). [REUSE.toml](REUSE.toml) gives the license of every file.

Part of [Open Kannada](https://github.com/openkannada), free and open-source tools that make Kannada work properly on computers.
