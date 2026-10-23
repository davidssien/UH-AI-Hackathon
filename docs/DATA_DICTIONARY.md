# Data dictionary

Status: Houston schema pending. No source field definitions, units or observed dtypes are available yet.

The following names are repository interface defaults, not observed Houston fields:

| Name | Repository role | Type / units |
| --- | --- | --- |
| id | Configured tabular row ID; dropped from features | Pending actual dataset |
| target | Configured regression target; converted to float by shared runner | Numeric conversion expected; meaning/units unknown |
| fold | Root fold-file assignment used by row position | Integer; -1 denotes unvalidated rows in time split generation |

NLP label/text settings and California housing demo fields are not Houston field definitions.

When data arrives, document each actual field's source name, output name, observed/storage dtype, meaning, units, allowed/missing values, transformations, provenance and modeling inclusion/exclusion rationale. Establish target semantics and prediction-time availability with the ML teammate.
