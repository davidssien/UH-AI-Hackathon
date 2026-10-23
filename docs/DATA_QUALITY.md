# Data quality

Status: static repository inspection only. No Houston dataset validation has been performed.

| Check | Actual result |
| --- | --- |
| Houston rows and fields | Not available in inspected checkout |
| Missing values, duplicates, outliers | Not measured |
| Geographic coverage, units, dates, license | Not verified |
| Train/test ID integrity and schema compatibility | Not checked against actual data |
| Exclusions and retained-row counts | None implemented or measured |
| Existing tabular fold rows | 16,640, counted with CSV header excluded |
| Existing NLP fold rows | 1,600, counted with CSV header excluded |

Fold counts describe repository artifacts only, not Houston dataset sizes. NOTES.md identifies these as demo folds; correspondence to real data is unverified.

## Modeling risks found in code (not runtime failures)
- src/features.py concatenates train/test before optional count and group aggregation features; validation and test distributions influence these features. Review transductive use against challenge rules and fit statistics within training folds for an inductive evaluation.
- Target encoding uses outer-training labels and inner KFold. Its smoothing prior uses all outer-training labels, including each inner holdout's labels. Inner splits also ignore temporal/group boundaries. Review before enabling --te; no leakage-free guarantee is established.
- src/make_folds.py time mode creates TimeSeriesSplit validation blocks, but src/common.py run_cv selects training as folds != k. That includes later blocks, so the shared runner does not preserve the original forward-only training indices. Do not treat CV=time as a verified temporal evaluation.
- Fold files store only a positional fold column. Data reordering/filtering can invalidate alignment without a stable ID/checksum contract.
- Generic KFold does not enforce property/group separation or chronology. The correct split depends on the housing task and prediction time.
- Configured DROP_COLS is empty. No actual Houston leakage exclusions have been chosen; identifying target-derived and future-only fields awaits schema and task inspection.

No model code was modified and no training/tests were run. These findings require coordination with the ML teammate.

## Planned validation
Check provenance, schema/types/units, IDs, train/test consistency, missingness, exact and entity-level duplicates, geography, dates, plausible ranges and target availability. Agree thresholds and exclusions from actual source semantics, preserve an exclusion log, and verify split overlap/alignment before handoff.
