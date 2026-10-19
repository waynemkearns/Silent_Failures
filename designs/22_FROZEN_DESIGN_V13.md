# 22 Frozen design V13: what each defect pattern does to the audit, one pattern at a time

Written before any V13 world is run. It is an addendum to `17_FROZEN_DESIGN_V10.md` and `21_FROZEN_DESIGN_V12.md`. `RUN_V13.py` checks the hashes below, refuses to start while `RUN_V12.py` is running, commits this file and the V13 scripts to git, and writes the commit hash and time to `_drafts/v13/FREEZE_RECORD_V13.txt` before the first job. It does not start until the author starts it.

## Question
Reviewer D asked which defect pattern is the most dangerous for an empirical privacy evaluation. V12 measured one pattern (the P6 mismatch). V13 measures the others that can be injected into the repaired protocol: P1, P2, P4 and P5, with P6 repeated in the same table. Each is injected into an otherwise clean pipeline, once so that only the members are affected (asymmetric, the V8 situation) and once so that members, holdout and reference are all affected (symmetric, what a shared pipeline does). The outcome is the shift in attack AUC and in the records-only baseline against the clean pipeline.

## What is unchanged
Data set-up, world seeds (worlds 0 to 99, pool, holdout and reference of 1,000 each), encoding, reference policy, reference-fitted scaler, attacks (Synth-MIA DCR and DCRDiff, own KDE-ratio), placebo, records-only baseline, margin and the Laplace release function are the V10 functions, imported unchanged from `_drafts/v10/v10_protocol.py`. The release is Laplace-perturbed records, not epsilon-DP. The P6 arms use the same contamination draws as V10 and V12. `RUN_V13.py` checks on Adult world 0 that `P6_sym` equals the V10 `contaminated` arm and `P6_asym` equals the V12 `contaminated_mismatched` arm at divisor 1 (largest absolute difference at most 1e-6, when the member counts are equal) and stops if not. In testing both matched exactly.

## Arms and injections
One clean arm, plus for each pattern an asymmetric arm (members affected, holdout and reference clean) and a symmetric arm (all three affected). All arms of a world use the same number of members, the smallest available in any arm, so the AUCs are comparable. The injected magnitudes are fixed here and are not tuned. They are arbitrary scaled-down analogues of the paper's patterns, not estimates of how often or how hard real pipelines hit them.

| Pattern | Injection | Dataset |
| --- | --- | --- |
| P1 position-based selection | Each patient is replaced by their first row in file order, instead of a random admission | MIMIC-IV only (Adult has no patient identifier) |
| P2 row cap | Only the first 60% of each file, in file order, is kept | both |
| P4a formula bug, uniform | One numeric column (length of stay on MIMIC-IV, hours per week on Adult) is shifted by +0.5 standard deviations of the full file | both |
| P4b formula bug, extreme cluster | The same column is set to 9,999,999 for a random 8% of rows (the IPUMS sentinel form in the paper) | both |
| P5 silent exclusion | Values outside the 1st to 99th percentile of the full file become NaN in the mask columns, then dropna on those columns | both |
| P6 unscoped dropna | 40% of rows get NaN in the mask columns, then dropna on the whole frame (as in V10 and V12) | both |

Divisors of the Laplace release (noise scale equals the member sample SD divided by the divisor): 1, 2 and 4, plus 100 as the near-copy positive control on the clean arm. The set was fixed after calibration on the clean arm of Adult worlds 1000 to 1004, which are not part of the analysis: mean DCR AUC 0.51, 0.63 and 0.83 at divisors 1, 2 and 4. MIMIC-IV could not be calibrated in the cloud because the data stay on the PC, so the MIMIC divisors are the Adult ones. If a MIMIC divisor is at the ceiling the analysis marks it and does not test it.

## Gates
On the clean arm, per dataset: records-only mean within 0.45 to 0.55. An attack is informative only if its positive control (divisor 100) is above 0.80 and its placebo means on the clean arm are within 0.47 to 0.53 at every divisor. A test is not run when the clean AUC at that divisor is above 0.97 (ceiling). A pattern arm is never gated, because a shift in its records-only baseline is a possible finding. Its placebo mean is printed and flagged if outside 0.47 to 0.53.

## Decision rule, fixed now
For each pattern, form (asymmetric or symmetric), informative attack and divisor, the paired difference arm minus clean across worlds, with a 90% CI. Two one-sided tests against the margin of 0.03: equivalence (both sides) and shift (either side). Holm correction over all tests in a dataset, separately for equivalence and for shift. Verdicts: "SHIFT beyond the margin" if the Holm shift p is below 0.05; "equivalent within the margin" if the Holm equivalence p is below 0.05; otherwise "inconclusive". The records-only baseline shift is reported with its CI and is descriptive. The danger table lists, for each arm, the largest absolute mean shift over the tests and the records-only shift. Minimum worlds 50 per cell, planned 100. Below the minimum the cell reports INSUFFICIENT WORLDS and no claim is made.

## What was seen before this freeze
Divisor calibration: the clean arm of Adult worlds 1000 to 1004, DCR, DCRDiff and KDE-ratio AUC at divisors 1 to 100 (DCR 0.51 at divisor 1 and 1.00 at 100). Code testing: Adult worlds 0 to 6 were run through the full job and the draft analysis, and the output was read at the level of the danger table and the per-test lines. World 0 to 6 are in the analysis. From those 7 worlds, not a result: P4b asymmetric lowers DCR AUC by up to about 0.38 (the sentinel dominates the noise scale and the distances); P4a asymmetric raises the records-only baseline to about 0.90 while moving the distance attacks by 0.03 or less; the other asymmetric arms moved the distance attacks by about 0.03 or less; P4a symmetric is an exact identity under the reference-fitted scaler. MIMIC-IV was tested only on a fabricated file and no MIMIC-IV result has been seen.

## Expected outcome, stated before the run
On Adult I expect the 7-world pattern to hold: one pattern (P4b asymmetric) with a large shift that hides leakage rather than creating it, one (P4a asymmetric) that inflates the records-only baseline without moving the distance attacks much, and the rest within or near the margin. On MIMIC-IV I do not predict the order. P1 is the one pattern I cannot say anything about.

## Known limits
Magnitudes are arbitrary and one value each. P1 is MIMIC-IV only. Each pattern is injected alone and not in combination. P4a symmetric is an identity by construction and is included as a check. The P4b result depends on the Laplace scale being taken from the member sample SD, so it describes this release, and a release with a fixed scale would behave differently. The release is Laplace-perturbed records, not a differentially private algorithm. Two datasets, three attacks.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and its gates, and the results commit is confirmed by `git log`: "Under the repaired protocol we injected P1, P2, P4, P5 and P6 one at a time. [Pattern] shifted [attack] AUC by [x] (90% CI [a, b]) on [dataset]; [patterns] were within 0.03." Ranking language ("most dangerous") only in the form of the danger table, with the limits above. Anything not met is described as frozen and incomplete.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    2ecb0a5d37a39300fc26458e2349a040147e9ab132c3ce260835db2783d9797a  v13/v13_protocol.py
    5c171c4b366d297d722ba0fcf563e97b0538c4671f772249c6a071d8569cfa6c  v13/analyse_v13.py
