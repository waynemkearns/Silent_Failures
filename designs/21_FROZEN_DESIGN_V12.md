# 21 Frozen design V12: asymmetric preparation, scaler isolation and an MST audit-failure arm

Written before any V12 world is run. It is an addendum to `17_FROZEN_DESIGN_V10.md` and `18_FROZEN_DESIGN_V11.md`. `RUN_V12.py` checks the hashes below, waits until `RUN_V11.py` has finished, commits this file and the V12 scripts to git, and writes the commit hash and time to `_drafts/v12/FREEZE_RECORD_V12.txt` before the first job.

## Question
Our original experiment was invalidated because members, holdout and reference were prepared differently. V12 measures what that mismatch does to attack AUC under the repaired protocol, on a Laplace-perturbed release and on a differentially private synthesizer (MST). It also repeats the scaler isolation for the two other attacks that pass the controls.

## What is unchanged
The data set-up, world seeds, preparation function, encoding, reference policy, attacks, controls, margin and release functions are the V10 functions, imported unchanged from `_drafts/v10/v10_protocol.py`. The three standard arms (`clean_full`, `clean_matched`, `contaminated`) are built by the same steps and seeds, so they must reproduce V10. `RUN_V12.py` checks this on Adult world 0 against `v10/results/adult_laplace_w0.json` (largest absolute difference must be at most 1e-6) and stops if it fails. During testing the three arms reproduced V10 DCR and DCRDiff to six decimals.

## What is new
**Part A, asymmetric preparation (Laplace-perturbed records).** One new arm, `contaminated_mismatched`. Members are the same records as in the `contaminated` arm (40% of rows masked on the MASK columns, then unscoped dropna). Holdout and reference are prepared as in the clean arm (dropna on the MASK columns for MIMIC, unchanged for Adult). Same member count, same reference size. This is the V8 situation: the attacker's non-members and reference are not the same population as the members. Cells: `adult_asym` and `mimic_asym`, 100 worlds each (worlds 0 to 99), release divisors 1 and 100, all five attacks, placebo and records-only baseline as in V10.

**Part B, scaler isolation (same files, descriptive).** For the three standard arms at divisor 1, DCR, DCRDiff and KDE-ratio are also computed with S1 (scaler fitted on the arm's members, as in the submitted procedure) and S3 (one fixed scaler fitted on 20,000 rows of the full file, encoded with the world's encoder). S2 is the reference-fitted scaler already used in the standard result. Size effect is `clean_matched` minus `clean_full`. Selection effect is `contaminated` minus `clean_matched`. No gates or verdicts, because this part repeats an exploratory finding.

**Part C, MST audit failure.** Cells `adult_mstasym` and `mimic_mstasym`. The `contaminated_mismatched` arm only, MST at epsilon 1 and 10 on publicly binned data exactly as in V11 (bin edges from the attacker's reference, `preprocessor_eps=0`), worlds 0 to 49. Compared, world by world, with the `contaminated` arm in the V11 cells `adult_mst` and `mimic_mst`. Epsilon 100 is not run.

## Gates (as in V10)
For each cell, on the three standard arms: records-only means within 0.45 to 0.55; for an attack to count as informative, the near-copy positive control must be above 0.80 in every arm and all placebo means within 0.47 to 0.53. For Part C the gates are read from the V11 cell, which is the evidence for the standard arms. The mismatched arm is never gated, because its records-only baseline is expected to fail. That is the finding.

## Decision rule, fixed now
Primary contrast: `contaminated_mismatched` minus `contaminated` (matched), paired by world, for each informative attack at divisor 1 (Part A) or epsilon 1 and 10 (Part C). One-sided t test of H0 that the difference is at most +0.03, Holm corrected over the tests of the cell, with a 90% CI. Verdicts: "SHIFT larger than the margin" if Holm p is below 0.05; "positive shift, not shown larger than the margin" if the CI lower bound is above 0; "no shift shown" otherwise. A negative shift beyond -0.03 is reported as such. Descriptive extras: mismatched minus `clean_matched`, the mismatched arm's mean AUC for all five attacks, its placebo, its positive control, and its records-only baseline.
Minimum worlds: 100 for the Laplace cells, 30 for the MST cells. Below the minimum the cell reports INSUFFICIENT WORLDS and no claim is made. A result that is not significant is reported as it is.

## What was seen before this freeze
During testing, on world 0 only: Adult, mismatched records-only baseline 0.539 against 0.484 for `contaminated`; DCR 0.549 against 0.547 and DCRDiff 0.521 against 0.528 at divisor 1. MIMIC, mismatched records-only 0.680 against 0.547 for `contaminated`; DCR 0.556 against 0.577 and DCRDiff 0.522 against 0.491. World 0 is included in the analysis. These are one world and do not set the outcome, but they suggest the Adult shift in the distance attacks may be small, so a "not shown larger than the margin" verdict on Adult is a real possibility.

## Expected outcome, stated before the run
The records-only baseline is likely to rise under mismatch, more on MIMIC than on Adult. Whether the distance attacks rise by more than 0.03 at divisor 1 is open. I do not predict it. For Part C at epsilon 1 the MST release carries very little information about members, so any shift would come from the mismatch itself.

## Run settings
Two workers, two threads each, temporary files on `<LOCAL_PATH>`. Order: worlds 1 to 99 of the two Laplace cells, then worlds 1 to 49 of the two MST cells. No new job starts 9 hours after the queue starts. A job is stopped after 3 hours. A smoke test runs world 0 of each cell first, one at a time. An erroring cell is dropped and reported.

## Known limits
One dataset pair, one preparation mismatch (the one from our original experiment), one contamination rate (40%). A mismatch of this kind produces a member and non-member population difference by construction, so a rise in AUC shows that the audit cannot tell that difference from leakage, not that any attack is weak. The MST release is run on publicly binned data with the bin edges taken from the attacker's reference, which is a design choice that may not match deployed use. The Laplace release is not epsilon-DP. Part B repeats an exploratory finding and carries no verdict.

## Allowed statements after the run, fixed now
Only if the analysis file exists and the cell met its minimum worlds and gates: "Under the repaired protocol, preparing members differently from holdout and reference raised [attack] AUC by [x] (90% CI [a, b]) on [dataset], with placebo near 0.5." For MST: "The same mismatch produced [x] on an epsilon-1 MST release, whose guarantee is unchanged." Anything not met is described as frozen and incomplete.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    e07f0567919f3df3703911dbe120e6d4820180464034509e6170cb0096175d67  v12/v12_protocol.py
    ec199ad998a774d12589073b3e73768ee75302f5e66f04f9691ac23578b592b7  v12/analyse_v12.py
