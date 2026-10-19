# 27 Frozen design V17: does one pipeline slip hide a planted leak, or raise a false alarm?

Written 15 Oct 2026, before any V17 world is run on the PC. It is an addendum to `22_FROZEN_DESIGN_V13.md`, `24_FROZEN_DESIGN_V14D.md`, `25_FROZEN_DESIGN_V15.md` and `26_FROZEN_DESIGN_V16.md`. It changes no earlier file. `RUN_V17.py` checks the hashes below, refuses to start while any of `RUN_V12.py` to `RUN_V16.py` is running, commits this file and the V17 scripts to git, and writes the commit hash and time to `_drafts/v17/FREEZE_RECORD_V17.txt` before the first job. It does not start until the author starts it, and only after the V15 and V16 results commits are in git.

## Question
V13 measured how much each pipeline slip moves the attack AUC on a Laplace-perturbed release. It did not ask the question a reader cares about: if a release really did contain a leak, would the audit still say so with the slip in the pipeline, and if it did not, would the slip make the audit say there is one? V17 plants a leak of known size in a release, injects one slip at a time, and records the verdict the audit would give.

## What this is, and what it is not
The leak is planted, as in V15 and V16. A verdict is a statement about the attacks and the decision rule, not about any real release. The slips are the V13 slips with the V13 magnitudes (arbitrary, scaled-down analogues of the paper's patterns, not estimates of how often or how hard real pipelines hit them). Nothing here says that any synthesizer leaks, and nothing here says that a real pipeline would behave the same way.

## What is unchanged
Everything in V13 is imported unchanged: data set-up, worlds, the clean pipeline, the slips P1 (MIMIC-IV only), P2, P4a, P4b, P5 and P6, each applied to members only (`_asym`) or to members, holdout and reference (`_sym`), the shared member count across arms, the reference-fitted scaler, the attacks DCR, DCRDiff and KDE-ratio, the margin of 0.03 and the near-copy positive control (Laplace, divisor 100). The release function is the frozen V14D PrivBayes-style synthesizer (DataSynthesizer 0.1.13, vendored in `_drafts/v14d/vendor`, k by the V14D rule) at epsilon 10, and the planting rule is the V15 rule. `RUN_V17.py` checks on world 0 of both cells that the member counts, the records-only baselines of every arm and the clean-arm positive control equal the V13 values to 1e-6, and stops if not. In testing they matched exactly on Adult.

## What is new
Cells `adult_c` and `mimic_c`, worlds 0 to 29. For every arm of a world, one PrivBayes-style table is released from that arm's members (binning from that arm's reference), then, from that same table, four variants are built:
- f = 0: the release itself, no planted leak;
- verbatim, f = 0.10: a tenth of the released rows replaced by real member rows of that arm, copied verbatim;
- verbatim, f = 0.25;
- noisy copies, f = 0.25: a quarter of the released rows replaced by noisy copies of that arm's members (Laplace noise of scale column SD / 4, the V16 Part A mechanism; the noise SD is taken from that arm's members, as in V13).
Seeds: release 17 x world + 10; verbatim planting 9000 + 31 x world + arm index; noisy copies 12000 + 31 x world + arm index + 400, noise 13 x world + 204. The placebo (non-member half against non-member half) is computed at f = 0 only.

## Gates
Per cell, on the clean arm: records-only mean within 0.45 to 0.55. An attack is informative only if its near-copy positive control is above 0.80 and its clean-arm placebo mean at f = 0 is within 0.47 to 0.53. Pattern arms are never gated, because a shift in a pattern arm's baseline or placebo is a possible finding; they are printed and flagged. A leak variant is interpreted for an attack only if the clean arm itself is FLAGGED at that variant (the sensitivity gate); otherwise the pattern rows for that variant are reported as "not interpretable". In earlier runs KDE-ratio failed its positive control on Adult, so I expect only DCR and DCRDiff to be informative there.

## Verdict rule, fixed now
For each cell, informative attack, arm and variant: the mean AUC over worlds minus 0.5, with three one-sided or equivalence tests against the 0.03 margin: "AUC - 0.5 > 0.03" (flag), "AUC - 0.5 < -0.03" (inverted: members look farther from the release than non-members) and equivalence within +/-0.03 (clear). Each test family is Holm corrected over all arm x variant x attack tests in the cell. Verdict: FLAGGED if the Holm flag p is below 0.05; else INVERTED if the Holm inverted p is below 0.05; else clear if the Holm equivalence p is below 0.05; else inconclusive.
Outcomes for each pattern arm against the clean arm of the same cell: at a leak variant that the clean arm flags, "leak kept" if the pattern arm is FLAGGED and "LEAK MISSED" otherwise (with the verdict that replaced it); at f = 0, "FALSE ALARM" if the clean arm is not FLAGGED and the pattern arm is. Also reported, descriptive: the paired AUC difference pattern arm minus clean arm at each variant with a 90% CI, the share of worlds with AUC above 0.53, the records-only baseline of each arm (a records-only baseline above 0.55 is a separate alarm that the audit raises on its own), and the placebo mean of each arm. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## What was seen before this freeze
Code testing in the cloud only. Adult world 0 to 4 (real file) and a fabricated MIMIC-IV file (worlds 0 to 4) were run through the full job, and the analysis script was run on those test worlds in test mode and its output read. From five Adult worlds, not a result: the clean arm flagged verbatim planting at f = 0.25 (DCR AUC about 0.62); at f = 0.10 and for noisy copies it did not reach a verdict at five worlds. Verbatim planting stayed visible under every slip (the paired differences were within about 0.03 of the clean arm). Noisy copies were hidden by P4b asymmetric (DCR AUC 0.63 on the clean arm in Adult world 0 and 0.50 under P4b asymmetric; mean paired difference -0.13 over the five worlds) and by none of the other slips. P4a asymmetric raised the records-only baseline to about 0.90 without moving the distance attacks by more than about 0.03. The V13 analysis (100 worlds per cell) was read before this design was fixed; it showed the same P4a and P4b behaviour on Laplace-perturbed releases. No real MIMIC-IV result for V17 has been seen. The choice to add one noisy-copy variant was made after seeing that verbatim copies survive the slips in Adult world 0.

## Expected outcome, stated before the run
Verbatim planting stays FLAGGED under every slip, because the planted rows are copies of the same corrupted members and so stay at distance zero. The noisy-copy leak is MISSED under P4b asymmetric (the sentinel inflates the member SD, so the noisy copies are far from their members on that column), and kept under the other slips, with possible exceptions for P5 and P2 on MIMIC-IV. FALSE ALARM at f = 0: none for the distance attacks; P4a asymmetric raises the records-only baseline, which is a different alarm. On MIMIC-IV I cannot say what P1 does.

## Known limits
One PrivBayes-style release at one epsilon. Verbatim and noisy copies are planted by construction. One noisy-copy point only (SD/4, share 0.25). Slip magnitudes are arbitrary and one value each, injected one at a time. The P4b result depends on the noise scale being taken from the member sample SD, as in V13. The release is DP, but the planted rows are not; the verdicts say nothing about DP guarantees. MWEM, MST and AIM are not run here. Two datasets, three attacks, of which probably two are informative.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`: "With a known leak planted in a PrivBayes-style release at epsilon 10, [slip] [kept / missed] the leak under [attack] on [dataset]: the verdict was [verdict] against [verdict] on the clean pipeline (AUC [x] against [y])." and "No tested slip raised a false alarm under [attack]" or "[slip] raised a false alarm under [attack]", as the table says. Statements are for the variants in the grid only. No sentence may say that a slip is the most dangerous in general, that real pipelines behave this way, or that any synthesizer leaks.

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
    2ecb0a5d37a39300fc26458e2349a040147e9ab132c3ce260835db2783d9797a  v13/v13_protocol.py
    30b4ebdd3f0656387a24c2119f76adf06a6e8f69afe371aa8e51db8826276dbd  v17/v17_protocol.py
    1b9e0dbf1be7605ccfede892af9419aaafd21ac3247e57aa304429347168825a  v17/analyse_v17.py
