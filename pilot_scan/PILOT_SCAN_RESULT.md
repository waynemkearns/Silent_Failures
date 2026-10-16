# Pilot scan result (run 12 Oct 2026, 16:28 UTC)

Protocol: `PILOT_SCAN_PROTOCOL_FROZEN.md`. Scanner v2 hash matched. Selection rule and queries unchanged.
The per-flag list names third-party repositories and is not included here. The list, commits and verdicts can be given to the programme chairs on request.

## Counts

- 30 repositories, 1,454 Python files, 1 file with a parse error.
- 163 flags in 21 repositories. 9 repositories had no flags.
- Verdicts after reading snippets: 9 real, 19 unclear, 135 benign. After rechecking the 28 real and unclear flags against full files: 17 real, 5 unclear, 141 benign.
- Repositories with at least one real finding: 7 of 30.

| Rule | Flags | Real | Unclear | Benign |
| --- | --- | --- | --- | --- |
| DROPNA_UNSCOPED | 57 | 16 | 0 | 41 |
| POS_SELECT | 32 | 1 | 0 | 31 |
| ROW_CAP | 41 | 0 | 5 | 36 |
| CONST_OUTPUT | 24 | 0 | 0 | 24 |
| ENC_PER_FRAME | 9 | 0 | 0 | 9 |

## What the data say

- "Real" means the pattern is present as the rule describes and could change a result. No effect was measured on any of them.
- The 9 real findings were rechecked against the full files on 12 Oct. Five are complete-case `dropna` calls made before the member/holdout split, so they are symmetric and are not the asymmetric defect from our V8 experiment. One applies the same `dropna` separately to real and synthetic frames. Two are possible misalignments after `dropna` in one library, flagged by its authors' own TODO comments, and not tested. One is minor order-dependent imputation. The 19 unclear flags were rechecked too: 8 became real (one asymmetric pattern, below), 6 became benign and 5 stay unclear.
- The 8 new real flags are one pattern copied across three tabular diffusion-model repositories: `syn_df.dropna()` is applied to the synthetic frame only, with no NaN handling on the real frame in the same function. This is the same asymmetric form as our V8 defect, in a fidelity metric (alpha and beta), not a membership test. Whether it changes a result depends on whether the real data contain NaNs. Not tested.
- The unscoped dropna pattern (our P6) was the only one with a repeat count: 8 real in 5 repositories, all of the complete-case kind described above. One further real case is order-dependent imputation (POS_SELECT).
- Precision is low. DROPNA_UNSCOPED real rate 8/57, POS_SELECT 1/32. Most dropna false positives are single-column Series calls with a variable column name, which v2 does not skip. Reported as a limit. The scanner was not changed.
- The encoder defect that invalidated our V8 experiment was not found in these repositories (0 real, 1 unclear).
- The 8 asymmetric dropna flags come from the same code copied into three repositories. Counts are not independent. Distinct patterns: about 6.
- One repository supplies 38 flags, mostly SQL LIMIT queries in test scripts.

## Limits to state

- One assessor. The 28 real and unclear flags were read in full files; the other 135 benign flags were judged from 3 to 7 line snippets.
- Rules were written while auditing our own pipelines.
- The freeze record was written before the search (hashes and timestamp), but the git commit of it failed. It is not time-stamped in version control.
- Selection is by stars within four queries. It is not a random sample. No prevalence claim.
- Notebooks not scanned.

## Allowed sentence

"In a pilot scan of 30 public Python repositories on synthetic-data privacy and health-data generation, chosen by a rule fixed in advance, our scanner flagged 163 candidates. On a full-file reading, 17 were real instances of the pattern in 7 repositories, 5 were unclear and 141 were benign. None was shown to change a result. One pattern, copied across three repositories, treats the synthetic and real frames asymmetrically, as our V8 defect did, in a fidelity metric; whether it matters depends on missing values in the real data. This is not a prevalence estimate."
