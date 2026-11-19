# font-health-action

Kannada shaping tests for any font repository, on every commit.

The action shapes the 2,146 test strings of [kannadi's fontqa](https://github.com/openkannada/kannadi/tree/main/tools/fontqa) in your fonts with HarfBuzz, and runs [Shaperglot](https://github.com/googlefonts/shaperglot)'s `kn_Knda` checks. It fails when a font breaks a conjunct, an arkavattu or a vowel sign, draws a dotted circle or `.notdef`, or lacks a Kannada character. A baseline of known fontqa failures lets a font with gaps adopt it today and fail only on new problems.

## Use

```yaml
jobs:
  font-health:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7.0.1
      - uses: openkannada/font-health-action@v1
        with:
          fonts: fonts/ttf/*.ttf
```

The job summary shows a table of failures per face, and lists every new failure with its text. The full JSON report is written to `font-health/report.json`; upload it with `actions/upload-artifact` to keep it.

Run it on Linux: Shaperglot has no wheels for macOS on Apple Silicon. The action installs uv 0.12.17 with `astral-sh/setup-uv`, which later steps of the job also see.

## Inputs

| Input | Default | What it does |
|---|---|---|
| `fonts` | required | Font files or glob patterns (TTF, OTF, TTC), separated by spaces or new lines. `**` matches folders. Paths with spaces are not supported. Fonts with fewer than 40 Kannada characters, such as a Latin companion font, are skipped by both checks. |
| `fail-on` | `missing_glyph notdef dotted_circle no_conjunct no_arkavattu` | The fontqa failure kinds that fail the check, separated by spaces, commas or new lines. The others, `collision` and `indistinct`, are still reported. |
| `baseline` | none | A report from an earlier run. Its fontqa failures are known and do not fail the check. |
| `allow-missing` | none | Code points a font may lack, such as `U+0CDC`, for fontqa and Shaperglot both. |
| `shaperglot` | `true` | Run Shaperglot's `kn_Knda` checks too. Shaperglot reads single fonts, so TTC and OTC files are skipped. |
| `report` | `font-health/report.json` | Where to write the JSON report. |
| `proofs` | none | A folder for 1 proof sheet per face, with every failing string drawn large, known or new. |
| `kannadi-ref` | a pinned commit | The kannadi commit whose fontqa runs. |
| `shaperglot-version` | `1.2.2` | The Shaperglot release on PyPI. |

## Failure kinds

| Kind | Meaning |
|---|---|
| `missing_glyph` | A character in the string has no glyph, or a glyph with no ink |
| `notdef` | The shaped output holds glyph 0 although every character is mapped |
| `dotted_circle` | HarfBuzz inserted a dotted circle, so the font rejected the sequence |
| `no_conjunct` | Consonant + virama + consonant shapes like the same string with a ZWNJ: no subscript formed |
| `no_arkavattu` | ರ + virama + consonant does not form the arkavattu |
| `collision` | A mark overlaps another glyph by more than 3% of the smaller glyph's ink |
| `indistinct` | 2 different strings render with exactly the same ink |

fontqa's README describes the 7 groups of test strings and how each check works.

## Adopting it with known gaps

Run the action once without a baseline, copy the report into the repository, and pass it as `baseline`:

```yaml
      - uses: openkannada/font-health-action@v1
        with:
          fonts: Gari.ttf
          baseline: font-health/baseline.json
          allow-missing: U+0CBC U+0CBD
```

The check then fails only on fontqa failures the baseline does not list. When a fix makes a listed failure go away, the summary says so, and the baseline can shrink. The baseline does not cover Shaperglot: a font whose only Shaperglot gaps are missing characters lists them in `allow-missing`, and a font with other Shaperglot gaps sets `shaperglot: false` until they are fixed. The report is a valid baseline as it is; the keys it needs are `faces` and, within each face, `failures`. A face is named by the path given in `fonts` and its index in the file, as in `Gari.ttf#0`.

## Running it locally

```bash
git clone https://github.com/openkannada/kannadi
uv sync --project kannadi/tools/fontqa
uv run --project kannadi/tools/fontqa python health.py MyFont.ttf --baseline baseline.json
```

`health.py --help` lists the options. It exits 1 when a failure is new and 2 when no Kannada font was found.

## Contributing

Every commit needs a `Signed-off-by` line (`git commit -s`) under the [Developer Certificate of Origin](https://developercertificate.org/). Changes to the test strings belong in kannadi's fontqa; this repository only runs them.

## License

The code is under the MIT license or the Apache License 2.0, at your choice: see [LICENSE-MIT](LICENSE-MIT) and [LICENSE-APACHE](LICENSE-APACHE). The documentation is under [CC BY 4.0](LICENSES/CC-BY-4.0.txt). [REUSE.toml](REUSE.toml) gives the license of every file.

Part of [Open Kannada](https://github.com/openkannada), free and open-source tools that make Kannada work properly on computers.
