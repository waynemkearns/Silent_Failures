# 23 Frozen design V14: MWEM and AIM audit-failure checks and a DP GAN feasibility test

Written 14 Oct 2026, before any V14 world is run on the PC. It is an addendum to `17_FROZEN_DESIGN_V10.md` and `18_FROZEN_DESIGN_V11.md`. `RUN_V14.py` checks the hashes below, refuses to start while `RUN_V12.py` or `RUN_V13.py` is running, commits this file and the V14 scripts to git, and writes the commit hash and time to `_drafts/v14/FREEZE_RECORD_V14.txt` before the first job. It does not start until the author starts it.

## Question
Reviewer A asked for established DP synthesizers and reviewer D asked whether a specific algorithm such as MWEM was used. V11 used MST. V14 repeats the V11 test with two further DP synthesizers on the same worlds and arms: MWEM (Part A) and AIM (Part C). AIM models correlations between columns, as MST does. V14 also records whether a DP GAN (DPCTGAN) runs in our setup at all (Part B).

## What is unchanged
Data set-up, world seeds, the three standard arms (`clean_full`, `clean_matched`, `contaminated`), encoding, reference policy, reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control (Laplace, divisor 100) and margin are the V10 functions, imported unchanged from `_drafts/v10/v10_protocol.py`. The release is the only change. Part C reuses the same standard-arm code and the same worlds. `RUN_V14.py` checks on Adult world 0 that the records-only baseline and the positive control of all three arms equal the V11 `adult_mst` world 0 values (largest absolute difference at most 1e-6) and stops if not. In cloud testing the same quantities matched the V10 `adult_laplace` world 0 exactly.

## What is new
**Part A, MWEM.** Cells `adult_mwem` and `mimic_mwem`, worlds 0 to 29. MWEM from smartnoise-synth 1.0.8 at epsilon 1 and 10, with the budget total (`preprocessor_eps=0`), on publicly binned data prepared exactly as the V11 MST release (bin edges from the attacker's reference). Columns are modelled in groups of 3 (`split_factor=3`), because the unsplit algorithm cannot run on 15 to 17 columns. Epsilon 100 is not run.

**Part C, AIM.** Cells `adult_aim` and `mimic_aim`, worlds 0 to 29. AIM from smartnoise-synth 1.0.8 at epsilon 1 only, with the budget total (`preprocessor_eps=0`), default AIM settings, on the same publicly binned data as Parts A and V11. Epsilon 10 and 100 are not run. Part C runs after Part A. `RUN_V14.py` analyses and commits Part A before Part C starts, so a problem in Part C cannot affect Part A. Part C has its own time cap (default 20 hours from its start, `V14_AIM_MAX_HOURS`) and a 3 hour cap per world. A cell with fewer than 30 finished worlds reports INSUFFICIENT WORLDS and no claim is made for it.

**Part B, DP GAN feasibility.** DPCTGAN (smartnoise-synth), 20 epochs, epsilon 10, fitted on the clean_full members of world 0 of each dataset, then sampled. The run records versions, time and any error. No attack is computed and no claim about privacy or leakage is made from it. A failure is recorded and does not stop the run.

## Gates (as in V10 and V11)
Records-only means on the three standard arms within 0.45 to 0.55. An attack is informative only if its near-copy positive control is above 0.80 in every arm and all its MWEM placebo means are within 0.47 to 0.53. Attacks that fail are reported and excluded from the equivalence claim.

## Decision rule, fixed now
Primary contrast: `contaminated` minus `clean_matched`, paired by world, for each informative attack at epsilon 1 and 10. Two one-sided tests against a margin of 0.03 for equivalence, and one-sided tests for a shift beyond the margin, Holm corrected over the tests in the cell, with a 90% CI. Verdicts: "SHIFT beyond the margin" if the Holm shift p is below 0.05; "equivalent within the margin" if the Holm equivalence p is below 0.05; otherwise "inconclusive". Secondary, descriptive: `clean_matched` minus `clean_full`. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## What was seen before this freeze
Code testing in the cloud only (one AIM fit on Adult world 0 data took about 120 seconds at epsilon 1; one-world test results for AIM are in the cloud test folder and are not part of the analysis): Adult world 0 (real data) and MIMIC-IV world 0 on a fabricated file, one world each. Adult world 0 attack AUCs for all three arms at epsilon 1 and 10 were printed and were all between 0.47 and 0.53 for the distance attacks. Calibration of `split_factor`: values 3 (runs, about 30 seconds per fit) and the pairwise-marginal setting (fails with a memory error) were tried on Adult world 0 data. World 0 is included in the analysis. No real MIMIC-IV result has been seen.

## Expected outcome, stated before the run
MWEM at these settings carries little information about members, so I expect the attacks to sit near 0.5 in all arms and the contrast to be equivalent or inconclusive. The same applies to AIM. Because the attacks may sit at chance for a different reason than in V11, an "equivalent" verdict here shows only that the audit does not separate the arms, not that the release is private.

## Known limits
MWEM is run with `split_factor=3`, so it ignores correlations between column groups and is a weaker synthesizer than MST. MWEM at two epsilon values and AIM at epsilon 1 only, 30 worlds, two datasets. Each cell is its own Holm family. AIM at epsilon 1 says nothing about higher epsilon. The cloud test used Python 3.11, snsynth 1.0.8, torch 2.14 and opacus 0.14; the PC may differ, and the environment is recorded in `results/ENV_V14.txt`. The GAN test is a feasibility record: a success does not show that a full DP GAN evaluation would pass the controls. PrivBayes, PrivSyn, relational synthesizers and diffusion models are not run and smartnoise-synth does not ship them.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`: "On MWEM, a second DP marginal synthesizer, the same attacks [verdict] ([x] AUC, 90% CI [a, b]) at epsilon [e], with MWEM run in column groups of 3." For AIM, the same sentence with "AIM, a DP synthesizer that models column correlations", epsilon 1 only, and without the column-group clause. For the GAN: "DPCTGAN ran in our setup on both datasets; a full evaluation is not yet done" only if both smoke tests succeeded. Each cell (adult_mwem, mimic_mwem, adult_aim, mimic_aim) is judged on its own gates and worlds. Anything not met is described as frozen and incomplete.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    14ad869a72b150f1ca019e473c2ea662569d7bb19c85d36a4132c47aed1fc46e  v14/v14_protocol.py
    91bef28c8d8c393f58d6a7adaaeb0c356e26ec21ba8855511745794849f99770  v14/analyse_v14.py
