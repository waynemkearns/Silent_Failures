# 24 Frozen design V14D: a PrivBayes-style audit-failure check (Part D)

Written 14 Oct 2026, before any V14D world is run on the PC. It is an addendum to `18_FROZEN_DESIGN_V11.md` and `23_FROZEN_DESIGN_V14.md`. It changes no V14 file. `RUN_V14D.py` checks the hashes below, refuses to start while `RUN_V12.py`, `RUN_V13.py` or `RUN_V14.py` is running, commits this file and the V14D scripts to git, and writes the commit hash and time to `_drafts/v14d/FREEZE_RECORD_V14D.txt` before the first job. It does not start until the author starts it.

## Question
Reviewer A asked for established DP synthesizers and named PrivBayes. V11 used MST. V14 adds MWEM and AIM. V14D repeats the V11 test with a PrivBayes-style synthesizer, on the same worlds and arms.

## What this is, and what it is not
The release is the correlated attribute mode of DataSynthesizer 0.1.13, a Python package whose code states that it is based on PrivBayes (Zhang, Cormode, Procopiuc, Srivastava and Xiao). It builds a Bayesian network with the greedy algorithm and an exponential mechanism, then adds Laplace noise to the conditional tables. It is a PrivBayes-style implementation. It is not the authors' code, and it is not guaranteed to reproduce the paper. Everything written about it says "PrivBayes-style, as implemented in DataSynthesizer".

## What is unchanged
Data set-up, world seeds, the three standard arms (`clean_full`, `clean_matched`, `contaminated`), encoding, reference policy, reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control (Laplace, divisor 100), margin, and the whole job function are the frozen V14 code, imported unchanged from `_drafts/v14/v14_protocol.py` (which imports the V10 functions). The only addition is one release method. `RUN_V14D.py` checks on Adult world 0 that the records-only baseline and the positive control of all three arms equal the V11 `adult_mst` world 0 values (largest absolute difference at most 1e-6) and stops if not.

## What is new
Cells `adult_pb` and `mimic_pb`, worlds 0 to 29. The release is on the same publicly binned data as the V11 MST release (bin edges from the attacker's reference). Epsilon is the total budget, at epsilon 1 and 10. DataSynthesizer spends epsilon/2 on the network and epsilon/2 on the conditional tables. Epsilon 100 is not run.

**Vendored code.** DataSynthesizer 0.1.13 (MIT licence, licence file included) is copied into `_drafts/v14d/vendor/DataSynthesizer`, without `ModelInspector.py`, which this run does not use and which needs plotting libraries. One edit was made, in `lib/PrivBayes.py` (lines 159 and 160): a multiprocessing `Pool` is replaced by a serial list comprehension over the same tasks. The tasks are independent and the order is kept, so results are unchanged. The edit avoids starting a pool of worker processes on every step on an 8 GB machine. Cloud testing compared the original and the edited code on the same data and seed and found the same network (see "What was seen"). The three `__init__.py` files that are empty in the original (`datatypes`, `datatypes/utils`, `lib`) each hold one comment line, so that no file is zero bytes. Every vendored file is hash-checked below. Nothing is installed on the PC.

**Network degree k.** The package's own automatic choice (k = 0) uses a default epsilon of 0.1 and, in our sizes, returned k = 7 or 8, which is not usable. So k is fixed here, by this rule: the largest k in {1, 2, 3} for which the usefulness score n x (epsilon/2) / ((d - k) x 2^(k+3)) is at least 4, evaluated at the smallest matched-arm member count seen in V14 (Adult 522, MIMIC-IV 218), and k = 1 if none qualifies. d is the number of columns (Adult 15, MIMIC-IV 17). The usefulness form is the one in the DataSynthesizer code, which cites PrivBayes Lemma 3. This gives the table below, fixed for every arm of a cell:

| dataset | epsilon 1 | epsilon 10 |
|---|---|---|
| Adult (d 15) | k = 1 | k = 2 |
| MIMIC-IV (d 17) | k = 1 | k = 1 |

k = 1 means each column has one parent, a tree. The member counts used for the rule came from the finished V14 files (counts only, no attack result).

## Gates (as in V10, V11 and V14)
Records-only means on the three standard arms within 0.45 to 0.55. An attack is informative only if its near-copy positive control is above 0.80 in every arm and all its PrivBayes-style placebo means are within 0.47 to 0.53. Attacks that fail are reported and excluded from the equivalence claim.

## Decision rule, fixed now
Primary contrast: `contaminated` minus `clean_matched`, paired by world, for each informative attack at epsilon 1 and 10. Two one-sided tests against a margin of 0.03 for equivalence, and one-sided tests for a shift beyond the margin, Holm corrected over the tests in the cell, with a 90% CI. Verdicts: "SHIFT beyond the margin" if the Holm shift p is below 0.05; "equivalent within the margin" if the Holm equivalence p is below 0.05; otherwise "inconclusive". Secondary, descriptive: `clean_matched` minus `clean_full`. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## What was seen before this freeze
Code testing in the cloud only. One fit of this synthesizer on Adult world 0 binned data at epsilon 1 with k = 2 took 8.4 seconds and returned a valid table inside the input category ranges. The original and edited code gave the same network on the same data and seed. Adult world 0 (real data) and MIMIC-IV world 0 (a fabricated file) were run through the full job once each to test the code, and the Adult output was printed. On Adult world 0 the standard-arm values (records-only baseline and positive control) matched the V14 MWEM run exactly, as they should. The contaminated-minus-matched difference in that single world was about +0.03 to +0.05 for the DCR and DCRDiff attacks at epsilon 1 and 10, which one world cannot distinguish from noise. World 0 is included in the analysis. The V14 Part A analysis had not been read when this design was fixed. No real MIMIC-IV result for this synthesizer has been seen.

## Expected outcome, stated before the run
As for MWEM, I expect the attacks to sit near 0.5 in all arms and the contrast to be equivalent or inconclusive. Because the attacks may sit at chance for a different reason than in V11, an "equivalent" verdict shows only that the audit does not separate the arms, not that the release is private. At epsilon 1 with k = 1 the release carries little information beyond single-column and parent-child distributions.

## Known limits
This is a PrivBayes-style implementation, not the authors' code. The degree k is fixed by the rule above, not tuned per run. Two epsilon values, 30 worlds, two datasets. The category list of each column is read from the member data, as in the other runs. One edit to the vendored code (serial map). PrivSyn, PrivLava, PrivPetal and diffusion models are not run.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`: "On a PrivBayes-style synthesizer (DataSynthesizer), the same attacks [verdict] ([x] AUC, 90% CI [a, b]) at epsilon [e], with the network degree fixed at k." Each cell is judged on its own gates and worlds. Anything not met is described as frozen and incomplete.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    14ad869a72b150f1ca019e473c2ea662569d7bb19c85d36a4132c47aed1fc46e  v14/v14_protocol.py
    fd4d2a8b3e790fe249ff06d0ba11b61ba9f957b74c67d7750183121b99793299  v14d/v14d_protocol.py
    c925ef1ef0d6bd5a257cbf27b677310ba6cdd17091f14a0819feb576ff6a0d92  v14d/analyse_v14d.py
    aae3153bb086a4d94c8945a569a11efa55aeff5bece9e85cf4d547ab2a99339b  v14d/vendor/DataSynthesizer/DataDescriber.py
    cd079fbc239a7888f053a79eca78baa68118dc8d0898e52c2fdeb6bdb1479873  v14d/vendor/DataSynthesizer/DataGenerator.py
    71f27f6f1bc7976f4cb3cf4327ce90be10a9d0c714c0c9a9b21f6efa4c278b0b  v14d/vendor/DataSynthesizer/LICENSE
    e4df34c761d58cb47efcaed59fe07c8f0bd34576bdd5154432bb3cd38ab12ee0  v14d/vendor/DataSynthesizer/__init__.py
    ad41b67eb7757e734327771626cf4181de9278e186454c72d7d64ce6ddbeb520  v14d/vendor/DataSynthesizer/datatypes/AbstractAttribute.py
    66ece9636a2b9581264952726acbbaf9bc650930a014754be0d7949f45efe74e  v14d/vendor/DataSynthesizer/datatypes/DateTimeAttribute.py
    0c54959cff619d2a1dba524e6276306c11d13415df7f45dc0fdc5161e3791285  v14d/vendor/DataSynthesizer/datatypes/FloatAttribute.py
    9681a4430afebc109ec570568bad60221b5fa4cac0c67201199615354e9c31be  v14d/vendor/DataSynthesizer/datatypes/IntegerAttribute.py
    8585f9f9022a221015a340bd4ec5a27be5de262f21fc0c4a56bf5cd54c8b753e  v14d/vendor/DataSynthesizer/datatypes/SocialSecurityNumberAttribute.py
    272d41daaa17d7132ee0a19333732f2829c18d6e4dd36ecc8510d4a4563253ac  v14d/vendor/DataSynthesizer/datatypes/StringAttribute.py
    5c138d6bad6d0e77ff970a68d0746022670776a6cec3c54522670d73733e12ab  v14d/vendor/DataSynthesizer/datatypes/__init__.py
    90e781a103e6f80e3064fe963c6026dcf4727d078fe65841ee7cc6d2d3a5331b  v14d/vendor/DataSynthesizer/datatypes/utils/AttributeLoader.py
    ddcee35d45fb49d91c46e9e41f1318eea48a6023d857a9332448826841016a04  v14d/vendor/DataSynthesizer/datatypes/utils/DataType.py
    5c138d6bad6d0e77ff970a68d0746022670776a6cec3c54522670d73733e12ab  v14d/vendor/DataSynthesizer/datatypes/utils/__init__.py
    df0d9b2df3f79f7155cc57186de467287ef16796182e1b266c7b9bc83aed8172  v14d/vendor/DataSynthesizer/lib/PrivBayes.py
    5c138d6bad6d0e77ff970a68d0746022670776a6cec3c54522670d73733e12ab  v14d/vendor/DataSynthesizer/lib/__init__.py
    fa29fa0d402a8adb7f172a111a7b14e21feab24e3f11aa2ba54875eed36d46f5  v14d/vendor/DataSynthesizer/lib/utils.py
