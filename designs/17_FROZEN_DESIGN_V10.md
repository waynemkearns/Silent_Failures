# 17 Frozen design V10: contamination effect on measured membership vulnerability, extended to a second dataset and a DP synthesizer

Written 12 Oct 2026, after the V9 result and before any V10 world is run. RUN_V10.py commits this file and the scripts to git before the first job and writes the commit hash and time to _drafts/v10/FREEZE_RECORD_V10.txt. V9 (16_FROZEN_DESIGN_V9.md) covers MIMIC-IV with Laplace-perturbed records and is not repeated.

## Question
Does P2 contamination (random 40% mask of the masked columns, then unscoped dropna) change measured membership AUC compared with a size-matched clean cohort, (a) on a public second dataset with Laplace-perturbed records, and (b) when the release is a real DP synthesizer, on both datasets?

## Cells
| Cell | Dataset | Release | Worlds |
| --- | --- | --- | --- |
| adult_laplace | UCI Adult (public, 32,561 rows, duplicates removed) | Laplace-perturbed records, divisor 1 (test) and 100 (positive control) | 100 |
| adult_mst | Adult | MST at epsilon 1, 10, 100 | target 50, minimum 30 |
| mimic_mst | MIMIC-IV canonical | MST at epsilon 1, 10, 100 | target 50, minimum 30 |

## Contamination on Adult (an analogue, stated as such)
Adult has no laboratory columns. The contaminated arm replaces '?' with missing, masks 40% of rows across fnlwgt, capital-gain, capital-loss and hours-per-week, then runs an unscoped dropna, which also removes rows with natural missingness in workclass, occupation and native-country. clean_full keeps all rows. clean_matched is a random subsample of clean_full at the contaminated size. Holdout and reference get the same preparation as their arm. Only the construction is shared with MIMIC, not the clinical meaning.

## Design, same as V9
Patient (row)-disjoint members, non-members and reference (1000 each per world, 3000 rows shuffled with seed 1000+w). Matched member count and a shared reference count per world (cap 250). Reference-fitted category vocabulary, unseen levels coded -1. Scaler fitted on the reference only. Records-only baseline, placebo and positive control in every arm.
Attacks: DCR, DCRDiff, Classifier, LocalNeighborhood (Synth-MIA 0981eadb) and KDE-ratio (own implementation, kde_ratio_own.py). DOMIAS, LOGAN, GenLRA and DensityEstimate are not run, to keep V9 and V10 comparable; they need torch.

## MST release
MST from smartnoise-synth run on publicly binned data: numeric columns are cut into 10 quantile bins with edges from the reference set, categorical columns use their codes, preprocessor_eps=0. Epsilon is therefore the total budget under add/remove-one-record adjacency. Synthetic bins are mapped back to the mean of reference values in the bin. No claim is made about delta or composition beyond the library's own accounting.

## Gates, fixed in advance (per cell)
- Records-only out-of-fold AUC within 0.45 to 0.55 in every arm (mean over worlds).
- An attack is informative only if its positive-control AUC exceeds 0.80 in every arm and its placebo means lie within 0.47 to 0.53 for every release setting of the cell. The positive control for all cells is the Laplace near-copy release at divisor 100 (a limit: it shows the attack detects near-copies, not that it would detect leakage from MST).

## Primary outcome
AUC(contaminated) minus AUC(clean_matched), paired by world, at Laplace divisor 1 (adult_laplace) or MST epsilon 1, 10 and 100 (MST cells). Margin +/-0.03. TOST with Holm correction within each cell across the informative (attack, setting) pairs, alpha 0.05, 90% CI reported.

## Stopping rule
RUN_V10.py stops starting new jobs 10 hours after launch. adult_laplace needs all 100 worlds. An MST cell needs at least 30 completed worlds, otherwise no equivalence claim is made for it. A smoke test (world 0 of each cell) decides whether a cell is dropped: an error or a 45-minute timeout drops the cell and is reported. A dropped cell is reported as dropped, not substituted.

## Verdicts allowed
Equivalent within margin / not shown equivalent / difference larger than margin / no informative attack / insufficient worlds / cell dropped. No other framing.

## Known limits, stated now
Adult's contamination is a synthetic analogue. The MST path could not be tested in the author's workspace (smartnoise-synth would not install there), so it is first exercised by the smoke test on the run machine. Positive control does not test MST leakage. Worlds are subsamples of one file per dataset. Weak privacy settings (epsilon 100) do not mean leakage is large. Equivalence is for the mean difference, not for every world.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    4d533c4b1992b823c815f8ecb187b1d93844de8998dc78048723b4c789ab8867  v10/analyse_v10.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
