# Pilot scan protocol (frozen before the first search)

Written 12 Oct 2026. Purpose: give reviewers B, D and E evidence from code we did not write, so the paper's pattern claims do not rest only on our own pipelines.

## What this is and is not

- It is a small pilot. It counts how often six code-visible candidate patterns appear in popular public Python repositories on synthetic data and health-data preprocessing.
- It is not a prevalence estimate. The repositories are not a random sample of anything.
- A flag is suspicious code. It is not a verified defect. Each flag is read in context and given a verdict.
- The scanner rules were written while auditing our own pipelines. They are tuned to those pipelines. This is a limit and will be stated.

## Fixed before looking

- Scanner: `scanner/pipeline_scan.py`, v2, sha256 3f378ee6aedfc7f21ac9963b6d3e15893de4e9f398b02459c08f4c3a94f113e4. No edits during the pilot. If it crashes on a file, the file is counted as a scan error.
- Rules: ENC_PER_FRAME, DROPNA_UNSCOPED, ROW_CAP, DEAD_MERGE, POS_SELECT, CONST_OUTPUT.
- Queries, each run on GitHub repository search with `language:python fork:false`, sorted by stars, top 10:
  1. synthetic data membership inference
  2. synthetic tabular data privacy evaluation
  3. synthetic health data generation
  4. mimic preprocessing synthetic
- Combine the lists in the order above, drop duplicates, keep the first 30.
- Exclude repositories owned by the authors and by the owners of the two external pipelines already audited in the paper.
- Exclude repositories over 500,000 KB.
- Clone with `--depth 1`. Record the commit hash.
- Scan every `.py` file. Skip folders named test, tests, testing, .venv, venv, env, site-packages, node_modules, .git, build, dist. Notebooks are not scanned. This is a limit.
- The run date and query results are recorded in the authors' private freeze record and selection file.

## Adjudication

- One assessor (the author and Claude, working from the saved snippets). No second rater. This is a limit and will be stated.
- Verdicts: `real` (the code does what the rule describes and could change a result), `benign` (the pattern is present but harmless, with the reason in the note), `unclear` (cannot tell from the snippet).
- Report counts of flags and repositories per rule, and the number of `real`, `benign` and `unclear`. Do not report a rate per repository as a prevalence.
- Nothing is dropped after the result is seen. If a flag is hard to judge it stays `unclear`.

## What we may say afterwards

- Allowed: "In a pilot scan of N public repositories chosen by a rule fixed in advance, the scanner flagged K candidates in M repositories. On reading, X were real, Y benign, Z unclear."
- Not allowed: any prevalence claim, any claim that a named repository has a bug without the maintainers having had a chance to see it, any claim that the scanner is accurate. Its precision and recall are unknown.
- Repository names are not put in the paper or the rebuttal. Maintainers are told first if any `real` finding is serious.
