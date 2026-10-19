# 26 Frozen design V16: where does detection stop, and does epsilon change it (Parts A and B)

Written before any V16 world is run on the PC. It is an addendum to `18_FROZEN_DESIGN_V11.md`, `23_FROZEN_DESIGN_V14.md`, `24_FROZEN_DESIGN_V14D.md` and `25_FROZEN_DESIGN_V15.md`. It changes no earlier file. `RUN_V16.py` checks the hashes below, refuses to start while `RUN_V12.py`, `RUN_V13.py`, `RUN_V14.py`, `RUN_V14D.py` or `RUN_V15.py` is running, commits this file and the V16 scripts to git, and writes the commit hash and time to `_drafts/v16/FREEZE_RECORD_V16.txt` before the first job. It does not start until the author starts it, and only after the V15 results commit is in git. Part C (a preprocessing slip that changes a privacy verdict) is designed separately and is not part of this run.

## Questions
V15 planted verbatim real rows in two DP releases at epsilon 10 and asked whether the attacks notice. Two questions follow from it.

Part A, the floor. Verbatim copies are the easiest leak to see. How much noise can a planted copy carry, and how large a share of the release can be copies, before the same attacks and the same decision rule stop noticing? The answer is a detection floor measured on a grid. It tells a reader what a "no shift beyond 0.03" result excludes and what it does not.

Part B, epsilon. V15 used epsilon 10 only. Does the detection of planted verbatim rows depend on the epsilon of the release the rows are planted into? V14 and V14D showed that the clean releases are indistinguishable at epsilon 1 and 10. This part checks that detection is the same too.

## What this is, and what it is not
Planted rows are an instrument with a known answer. Neither part shows that any synthesizer leaks, neither shows that the audit detects leakage in general, and neither says anything about DP guarantees. The noisy copies are Laplace-perturbed members, the same mechanism as the near-copy positive control, so they say how the attacks respond to that kind of copy and nothing about other kinds. Results are for MWEM and the PrivBayes-style synthesizer, Adult and MIMIC-IV, and the grid below.

## What is unchanged
Data set-up, world seeds, the three standard arms (`clean_full`, `clean_matched`, `contaminated`), encoding, reference policy, reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control (Laplace, divisor 100), margin, the MWEM release (smartnoise-synth, split_factor 3), the PrivBayes-style release (DataSynthesizer 0.1.13, vendored in `_drafts/v14d/vendor`, k = 1 at epsilon 1 by the V14D rule) and the release seeds are the frozen V14 and V14D code, imported unchanged. The `plant` rule is the V15 rule with a different source of rows.

## What is new
Cells `adult_mwem`, `mimic_mwem`, `adult_pb`, `mimic_pb`, worlds 0 to 29. Epsilon 1 only. For each arm one DP synthetic table is produced exactly as in V14 and V14D at epsilon 1. All variants below are built from that table, so every contrast is paired within a world and an arm.
- Part B: a share f of the released rows is replaced by real member rows, verbatim, f = 0.05, 0.10, 0.25. f = 0 is the release itself.
- Part A: every member row is perturbed once with Laplace noise of scale (column SD) / d, with d = 4, 2, 1 (the same mechanism as the positive control, which uses d = 100; d = 1 is noise as large as the column SD). A share f of the released rows is replaced by noisy copies drawn from those perturbed rows, f = 0.05, 0.10, 0.25, 0.50. That is 12 grid points.
Positions and sources are drawn without replacement with seeded generators (verbatim: seed 9000 + 31 x world + arm index; noisy: seed 12000 + 31 x world + arm index + 100 x d; the noise itself uses seed 13 x world + 200 + d). The placebo is computed on the release at f = 0 only.

## Gates (as in V10, V11, V14, V14D and V15)
Records-only means on the three standard arms within 0.45 to 0.55. An attack is informative only if its near-copy positive control is above 0.80 in every arm and all its f = 0 placebo means are within 0.47 to 0.53. Attacks that fail are reported and excluded from the claims. In earlier runs the KDE-ratio attack failed its positive control on Adult, so I expect only the two distance attacks (DCR, DCRDiff) to be informative there. The decision is by the gate, not by this expectation.

## Replication check on world 0, fixed now
`RUN_V16.py` compares world 0 of all four cells with the recorded V14 (MWEM) and V14D (PrivBayes-style) values at epsilon 1: member counts, the records-only baseline, the positive control and, for the PrivBayes-style release, the release at f = 0 must agree to 1e-6. The MWEM release at f = 0 is not bit-reproducible (see the V15 amendment) and must agree within a sanity band of 0.08 in AUC. The band was set in V15 after seeing a difference of 0.0405 and is reused here unchanged. A cloud run of Adult world 0 with MWEM gave 0.0316. If the check fails, the run stops.

## Decision rule, fixed now
Detection contrast, clean_matched arm, for each informative attack: AUC at the planted release minus AUC at f = 0, paired by world, 90% CI. One-sided tests of "increase > 0" and "increase > 0.03", each Holm corrected inside its own family (Part B: attack x 3 shares; Part A: attack x 12 grid points; each cell separately). Verdicts: "BEYOND the 0.03 margin" if the Holm p for "increase > 0.03" is below 0.05; "detected (increase > 0)" if only the Holm p for "increase > 0" is below 0.05; otherwise "not detected". Reported: for Part B, the smallest share detected and the smallest beyond the margin per attack; for Part A, for each attack and each d, the smallest share detected and the smallest beyond the margin; "none in grid" where there is none. Absence of detection in a grid cell is not evidence that nothing is there.
Part B2 (epsilon comparison, needs the V15 results of the same cell): per world, the Part B gain at epsilon 1 minus the V15 gain at epsilon 10 for the same share f; 90% CI; equivalence within +/-0.03 (two one-sided tests, Holm over attack x 3 shares); verdicts "equivalent within the margin", "DIFFERENT beyond the margin" or "inconclusive". MWEM is not bit-reproducible, so the world-level pairing across the two runs is by world number only, not by identical releases.
Secondary, descriptive: contaminated minus clean_matched at f = 0 and at each Part B share, equivalence within +/-0.03, Holm over attack x 4 points.
Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made. Each cell is judged on its own gates and worlds.

## What was seen before this freeze
Code testing in the cloud only. Adult world 0 to 4 and a fabricated MIMIC-IV file (worlds 0 to 4) were run with the PrivBayes-style release, and Adult world 0 with the MWEM release, through the full job. The analysis script was run on the five PrivBayes-style test worlds of each file, and its output was read, in test mode. On Adult (PrivBayes-style, epsilon 1, five worlds) the DCR AUC gain was about 0.02, 0.05 and 0.12 at verbatim shares 0.05, 0.10 and 0.25; for noisy copies at d = 4 it was about 0.03, 0.05 and 0.10 at f = 0.05, 0.10 and 0.25; at d = 2 about 0.01 to 0.07 across f = 0.05 to 0.50; at d = 1 no gain. The gain at epsilon 1 was within about 0.007 of the V15 test value at epsilon 10 on five worlds. The real Adult world 0 values for both releases were read, and so was the record of the earlier V15 runs on world 0. No real MIMIC-IV result for V16 has been seen. V14, V14D and V15 analyses were read before this design was fixed. The grid (shares, divisors) was chosen after the first Adult test world, which showed that d = 4 is clearly visible, d = 2 is borderline and d = 1 is not; f = 0.05 was added to Part A and the d = 1 and f = 0.50 points were kept so the grid has both ends.

## Expected outcome, stated before the run
Part B: the gain per unit of f is about 0.4 to 0.6 for the distance attacks, as in V15, and does not depend on epsilon within +/-0.03 (Part B2 equivalent). Part A: at d = 4 the distance attacks are beyond the margin from f = 0.25 and possibly from f = 0.10; at d = 2 they are detected only at the largest shares and not beyond the margin below f = 0.50; at d = 1 nothing is detected in the grid. The KDE-ratio attack, if informative, rises less than the DCR attacks. The contaminated-minus-matched contrast may stay equivalent or become a shift at higher shares; either is reported.

## Known limits
Noisy copies are one family of near-copies (independent Laplace noise per column). Real leakage may look different. Four shares, three divisors, two synthesizers, one epsilon, two datasets. Verbatim and noisy rows are placed in the released table by construction, not by any synthesizer. DPCTGAN, PrivSyn, relational synthesizers and diffusion models are not run. The 0.03 margin is a decision rule, not a claim about privacy risk.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`:
- Part A: "When a known share f of a DP release (MWEM or PrivBayes-style, epsilon 1) was replaced by noisy copies of real members (Laplace noise of SD/d), the same attacks [verdict] on [dataset] at d = [d], f = [f] (AUC [x] higher, 90% CI [a, b]). The smallest share in the grid beyond the 0.03 margin was [f] at d = 4 and [f or none in the grid] at d = 2 and d = 1."
- Part B: "The AUC gain from planted verbatim rows at epsilon 1 was [equivalent within / different beyond] 0.03 of the gain at epsilon 10 on [dataset] ([a, b])."
No sentence may say that these synthesizers leak, that the audit detects leakage in general, that a release with a shift below the floor is private, or anything about DP guarantees. Anything not met is described as frozen and incomplete.

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
    8c0cefabf23f91f560ec41cbbc5d1dfc964a717531a1b8e3f1a4c23447c8b6b1  v16/v16_protocol.py
    2d812c062bb33d714123462d4464e91c0dc7aee8866bb8cbf326fe8fc7f04096  v16/analyse_v16.py
