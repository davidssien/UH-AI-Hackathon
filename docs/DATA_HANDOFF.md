# Data handoff

Status: not ready for Houston ML use. No Houston dataset has been acquired, cleaned or validated in this checkout.

## Locations and interface
- Expected model inputs (config.yaml): data/train.csv, data/test.csv and data/sample_submission.csv. These files are absent from the inspected checkout; the paths are defaults, not deliverables.
- Large-file sharing: no Google Drive location or permissions verified. Agree a team destination before uploading.
- Existing folds.csv and nlp_folds.csv are identified by NOTES.md as demo folds. Do not use them as verified Houston folds.
- Existing demo generator uses California housing/IMDB and writes to model input paths; do not run it over real inputs.

## Before training
1. Supply teammate task, approved sources, target meaning/units, geographic/time scope and required submission contract.
2. Acquire and preserve originals; record version/checksum and reproducible cleaning commands.
3. Validate data and document actual results, exclusions and field definitions in DATA_QUALITY.md and DATA_DICTIONARY.md.
4. Coordinate config and fold changes with ML teammate. Preserve row order or validate ID-based alignment; agree group/time boundaries.
5. Resolve static split and feature risks recorded in DATA_QUALITY.md. No leakage-free evaluation has been verified.

## Limitations and evidence
No missing-value policy, outlier policy, Houston modeling exclusions or cleaned schema has been implemented. SETUP_REPORT.md records prior setup claims on example data; this task does not independently verify that environment. Do not interpret generic model scaffolding as a completed housing data pipeline.

The completed handoff must identify dataset versions and locations, read commands, schema, validation report, exclusions, split contract, reproducibility steps and remaining limitations. All remain pending dataset work.
