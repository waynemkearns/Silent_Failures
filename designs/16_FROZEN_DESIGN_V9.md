# 16 Frozen design V9: powered test of contamination effect on measured membership vulnerability

Written 11 Oct 2026, before any V9 world other than world 0 has been run. Status: margin CONFIRMED by the author at 22:47 local time on 11 Oct 2026. RUN_ME.py commits this file and the four scripts to git before any further world is run, and writes the commit hash and time to _drafts/overnight/FREEZE_RECORD.txt. World 0 was run once before the freeze as a smoke test and is kept in the results.

## Question
Does P2 contamination (40% lab mask then unscoped dropna) change measured membership vulnerability, compared with a size-matched clean cohort, for Laplace-perturbed records at noise divisor 1?

## Primary outcome
AUC(contaminated) minus AUC(clean_matched) at divisor 1, paired by world. Equivalence margin: +/-0.03 AUC (confirmed). Test: two one-sided t-tests per attack, Holm correction over informative attacks, alpha 0.05, 90% CI reported.

## Design
- 100 worlds (cohort draws), seeds fixed in the script (patients drawn with seed 1000+w). One noise seed per world.
- Patient-disjoint members, non-members, reference. Matched missingness. One feasible matched count per world. One shared reference count per world (cap 250).
- Vocabulary fitted on the world's reference patients (unseen levels coded -1).
- Attacks: DCR, DCRDiff, Classifier (Synth-MIA 0981eadb), KDE-ratio (own, kde_ratio_own.py), LocalNeighborhood (Synth-MIA, radius = median reference 1-NN distance, set from reference only). KDE-ratio and LocalNeighborhood run at divisors 1 and 100 and in placebos only.
- Not run: DOMIAS, LOGAN, GenLRA, DensityEstimate (need torch).
- Release: Laplace-perturbed records, scale = member sample SD / divisor. Not epsilon-DP.

## Gates, fixed in advance
- Records-only out-of-fold AUC within 0.45 to 0.55 in every arm (mean over worlds). If it fails, no equivalence claim.
- An attack is informative only if its mean positive-control AUC (divisor 100) exceeds 0.80 in every arm AND its placebo means (divisors 1 and 100, every arm) lie within 0.47 to 0.53.
- Only informative attacks enter the equivalence test. If none is informative, the result is "protocol cannot support an equivalence claim".

## Verdicts allowed
Equivalent within margin / not shown equivalent / difference larger than margin (CI wholly outside) / no informative attack. No other framing.

## Known limits, stated now
Single dataset (MIMIC-IV). Perturbation, not a DP synthesizer. Post-hoc origin of the protocol (v1 and v2 were designed after seeing the failed original). 100 draws from one canonical file are random subsamples of the same 545k encounters, not independent datasets.

## Files and hashes (sha256)
    239e094076427493cf723f667680d207f419337ff4dd838492cb0e5b5c3baa7e  repaired_protocol/v8_repaired_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    f41d1b4f7c247b5252c2c449a696677147352f8f80df3b4f4a7585c6cb7dee59  overnight/run_overnight.py
    cda4990dc96f5860d691cd270a8382eeef3460c60d4241a381be20268d708221  overnight/analyse_overnight.py
