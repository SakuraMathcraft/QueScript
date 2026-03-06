# QueScript v1.0 Release Notes

Release date: 2026-03-06

## Highlights

QueScript v1.0 delivers a local-first survey workflow covering generation, simulation, measurement analysis, and auditability in one GUI:

- Text-to-HTML questionnaire generation
- Smart batch simulation with configurable sample size and response tendencies
- Branch-aware skip logic and per-sample path auditing
- Reliability/validity/discrimination analysis with EFA outputs
- Reproducibility artifacts for rerun and review

## New in v1.0

### Survey generation

- Added questionnaire text parsing to produce browser-ready HTML surveys
- Improved support for common question types (single choice, multiple choice, scale, matrix, text)

### Simulation engine

- Added GUI-driven simulation flow (no command line required for routine use)
- Added response tendency modes for non-scale selection behavior:
  - `random`
  - `positive`
  - `negative`
  - `central`
- Added configurable latent dimension settings for scale-data generation scenarios
- Added strict skip-path execution support based on question visibility/jump rules

### Measurement analysis

- Added built-in analysis report after simulation completion
- Added reliability analysis:
  - Cronbach's Alpha
  - Item diagnostics (CITC, Alpha-if-deleted)
- Added validity and structure checks:
  - KMO + Bartlett
  - EFA output (factor suggestions, variance contribution, loadings)
- Added item discrimination (critical-ratio style checks)

### Auditability and reproducibility

- Added run metadata and reproducibility fields (`run_id`, `seed`)
- Added audit artifacts:
  - `config.json`
  - `path_log.csv`
  - `analysis_meta.json`
- Added report-level signatures for reproducibility trace

### Packaging and delivery

- Added offline-oriented Windows packaging path
- Added local browser-runtime packaging support for Playwright-based execution layouts

## UX and GUI updates

- Added modernized GUI layout with simulation controls and status/progress display
- Added integrated run log panel and report display workflow
- Added clearer analysis sections and structured report output

## Compatibility

- Platform focus: Windows desktop usage
- Python runtime: project uses virtual-environment-based dependency management

## Output files (typical)

After a simulation/analysis run, output files are generated in the target survey directory:

- `survey_data_collected.csv`
- `config.json`
- `path_log.csv`
- `analysis_meta.json`

## Known limitations

- Branch-heavy questionnaires can reduce the number of globally comparable items in full-sample analysis.
- Structural metrics are sensitive to sample size and item coverage thresholds.
- Some advanced fit indicators may become unstable under small `n/p` conditions.

## Upgrade and usage notes

- Recommended baseline for more stable structural analysis: larger sample sizes (commonly `n >= 100`)
- For strong branch logic, prefer branch-aware interpretation in addition to full-sample summaries
- Keep each latent dimension with enough comparable items for better model stability

## Repository

- GitHub: https://github.com/SakuraMathcraft/QueScript

