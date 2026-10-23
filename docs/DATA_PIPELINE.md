# Data pipeline

Status: repository inspection verified; Houston acquisition and cleaning not started.

## Sources
No Houston dataset has been acquired or inspected in this checkout. Source URLs, licenses, versions, coverage and download commands remain pending teammate instructions. No Google Drive dataset location has been verified.

## Existing interfaces (static code inspection)
- config.yaml: DATA_DIR=data, TRAIN=train.csv, TEST=test.csv, SAMPLE_SUB=sample_submission.csv, ID_COL=id, TARGET=target. These are defaults, not a verified Houston schema.
- src/common.py: load_data reads train/test with pandas.read_csv; load_folds reads the fold column positionally from root folds.csv.
- src/features.py: build drops configured target, ID and DROP_COLS, concatenates train/test, applies selected feature functions and casts categorical fields. Optional count/group aggregate features use the combined frame. Target encoding is invoked inside the outer fold with inner KFold; see DATA_QUALITY.md for limits.
- src/make_folds.py writes root fold files and refuses replacement unless --force. It supports KFold, target-binned stratification, groups and time modes. Do not regenerate existing files during this documentation task.
- src/make_sub.py aligns predictions from test row order to sample IDs and checks several submission constraints. It has not been executed during this inspection.
- scripts/make_demo_data.py writes demo CSVs into data/ and data/nlp/. It must not be run over housing inputs.

## Planned reproducibility record
Once authorized, record original and derived locations, source/version/checksum, exact commands and dependencies, per-step row counts, key/type/unit conversions, exclusions and checks. Preserve originals separately from outputs. Agree storage conventions with the team before creating datasets; existing data/ is an ignored model input path, not an implemented raw/processed separation.

No cleaning script, acquisition command or transformation specific to Houston has been implemented or run here.
