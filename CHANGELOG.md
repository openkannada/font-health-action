# Changelog

All notable changes to this action. The `v1` tag follows the latest 1.x release.

## [1.1.0] - 2026-11-19

### Added

- Proof sheets on by default (`font-health/proofs`), uploaded with the report as the `font-health` artifact. The `artifact` input names it; empty for none.
- The job summary has a pass and fail table per face, then 1 paragraph per kind of new failure with what a correct font does and up to 6 examples. Missing characters are grouped by character.
- Each failing case in the report keeps its detail: missing code points, look-alike strings and colliding glyphs.

### Fixed

- A file name with brackets, such as `NotoSansKannada[wdth,wght].ttf`, is taken as named when the file exists. Before, it was read as a glob pattern and matched nothing.

## [1.0.0] - 2026-11-19

### Added

- The action: shapes 2,146 Kannada test strings with HarfBuzz, runs Shaperglot's `kn_Knda` checks, and fails on missing characters, .notdef, dotted circles, missing conjuncts and a missing arkavattu.
- Baselines for known failures, and `allow-missing` for code points a font may lack.

[1.1.0]: https://github.com/openkannada/font-health-action/releases/tag/v1.1.0
[1.0.0]: https://github.com/openkannada/font-health-action/releases/tag/v1.0.0
