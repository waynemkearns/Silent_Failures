# 25 Frozen design V15: a sensitivity test with a planted leak of known size

Written before any V15 world is run. It is an addendum to `18_FROZEN_DESIGN_V11.md`, `23_FROZEN_DESIGN_V14.md` and `24_FROZEN_DESIGN_V14D.md`. It changes no earlier file. `RUN_V15.py` checks the hashes below, refuses to start while `RUN_V12.py`, `RUN_V13.py`, `RUN_V14.py` or `RUN_V14D.py` is running, commits this file and the V15 scripts to git, and writes the commit hash and time to `_drafts/v15/FREEZE_RECORD_V15.txt` before the first job. It does not start until the author starts it. See the amendment of 15 Oct 2026 below.

## Question
Every differentially private release tested so far (MST, MWEM, AIM, the PrivBayes-style synthesizer) gives attack AUCs near 0.50 in every arm, and the contaminated and size-matched arms are equivalent. A reviewer can say that is the expected answer, because a DP release gives the attacks nothing to find. The question here is whether the same attacks and the same decision rule would have noticed a leak in such a release if one were present. V15 plants a leak of known size and measures what the procedure reports.

## What this is, and what it is not
The leak is planted: a share f of the rows of a DP synthetic table is replaced by real member records, copied verbatim. This is a worst-case, easy-to-recognise form of leakage. It shows that the attacks and the decision rule have power against a known leak of a known size on a DP-synthesizer release. It does not show that any of these synthesizers leaks, it does not cover subtle or partial leakage, and it says nothing about DP guarantees.

## What is unchanged
Data set-up, world seeds, the three standard arms (`clean_full`, `clean_matched`, `contaminated`), encoding, reference policy, reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control (Laplace, divisor 100), margin, the MWEM release (smartnoise-synth, split_factor 3) and the PrivBayes-style release (DataSynthesizer 0.1.13, vendored in `_drafts/v14d/vendor`, k fixed by the V14D rule), and the release seeds are the frozen V14 and V14D code, imported unchanged. `RUN_V15.py` checks on world 0 of all four cells that the records-only baseline, the positive control and the release at epsilon 10 with no planted rows equal the V14 (MWEM) and V14D (PrivBayes-style) world 0 values (largest absolute difference at most 1e-6) and stops if not. The MWEM release is held to a sanity band instead, see the amendment below.

## What is new
Cells `adult_mwem`, `mimic_mwem`, `adult_pb`, `mimic_pb`, worlds 0 to 29. Epsilon 10 only. For each arm the DP synthetic table is produced exactly as in V14 and V14D. Then a share f of its rows is replaced by real member records: m = round(f x n) positions are drawn without replacement from the n released rows and replaced by m members drawn without replacement from the n members of that arm, using a seeded generator (seed 9000 + 31 x world + arm index). Planted share f = 0, 0.05, 0.10, 0.25. At f = 0 nothing is replaced, so the results repeat V14 and V14D. The placebo is computed at f = 0 only. The positive control and records-only baseline are as before.

## Gates (as in V10, V11, V14 and V14D)
Records-only means on the three standard arms within 0.45 to 0.55. An attack is informative only if its near-copy positive control is above 0.80 in every arm and all its f = 0 placebo means are within 0.47 to 0.53. Attacks that fail are reported and excluded from the claims.

## Decision rule, fixed now
Primary (detection), on the `clean_matched` arm: AUC at share f minus AUC at f = 0, paired by world, for each informative attack and each f > 0, with a 90% CI. One-sided tests of "increase > 0" and "increase > 0.03", each Holm corrected over the attack x f tests in the cell. Verdicts: "BEYOND the 0.03 margin" if the Holm p for "increase > 0.03" is below 0.05; "detected (increase > 0)" if only the Holm p for "increase > 0" is below 0.05; otherwise "not detected". For each attack the analysis reports the smallest f in the grid that is detected and the smallest that is beyond the margin. Secondary, descriptive: contaminated minus clean_matched at each f (two one-sided tests against the margin, Holm over attacks x f), and the AUC gain per unit f. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## What was seen before this freeze
Code testing in the cloud only. Adult world 0 with the PrivBayes-style release (real data) and Adult world 0 with the MWEM release were run through the full job once each. The PrivBayes-style output was printed: on the `clean_matched` arm the DCR AUC went from 0.471 at f = 0 to 0.506, 0.539 and 0.610 at f = 0.05, 0.10 and 0.25, and the other distance attacks rose in a similar way. A fabricated MIMIC-IV file was used to test the MIMIC-IV path with the PrivBayes-style release for a few worlds, and the analysis script was run on those test worlds. On the fabricated file the DCR AUC rose by about 0.45 to 0.5 per unit of f. No real MIMIC-IV result for V15 has been seen. The V14 and V14D analyses were read before this design was fixed, and this design repeats their releases at f = 0.

## Expected outcome, stated before the run
Replacing a share f of the released rows with member records puts those members at distance zero from the release, so the distance attacks should rise roughly in proportion to f, by about 0.4 to 0.7 AUC per unit of f. The 0.03 margin therefore corresponds to a planted share of about 4 to 8 percent of the rows. I expect f = 0.10 and f = 0.25 to be beyond the margin and f = 0.05 to be detected but near or below the margin. I expect the KDE-ratio attack on MIMIC-IV to rise less than the DCR attacks. The contaminated-minus-matched contrast may stay equivalent or become a shift at f > 0; either is reported.

## Known limits
Verbatim copies are the easiest leak to see. Two synthesizers, one epsilon, four shares, two datasets. The planted share is a property of the released table, not a statement about what any synthesizer releases. DPCTGAN, PrivSyn, relational synthesizers and diffusion models are not run.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`: "When a known share f of a DP release (MWEM or PrivBayes-style, epsilon 10) was replaced by real member records, the same attacks [verdict] on [dataset] (AUC [x] higher, 90% CI [a, b] at f = [f]); the smallest share in the grid that exceeded the 0.03 margin was [f]." Each cell is judged on its own gates and worlds. Anything not met is described as frozen and incomplete. No sentence may say that these synthesizers leak or that the audit detects leakage in general.

## Amendment, after the first start and before worlds 1 to 29
The first start of `RUN_V15.py` (freeze commit aacd4e3, 15 Oct 10:22 Dublin) ran world 0 of the four cells and stopped at its own exact-replication check with a largest difference of 0.0405. Cause: the two PrivBayes-style cells repeated V14D exactly, the records-only baseline and the positive control repeated exactly in all four cells, but the MWEM release at f = 0 did not repeat V14. MWEM in smartnoise-synth is not bit-reproducible: in the cloud the same call with the same seed gave different tables on repeat runs, and two cloud runs of Adult world 0 differed by up to 0.024 AUC at f = 0. This is a property of the library and not of the V15 code. It also means the V14 MWEM numbers cannot be regenerated bit for bit. They stand as the recorded run.
What we saw: the world 0 values of all four cells from that first start (f = 0 and f > 0). They were not analysed, but they were visible when this amendment was written.
Change: the check stays exact (1e-6) for the member counts, the records-only baseline, the near-copy positive control and the PrivBayes-style release at f = 0. For the MWEM release at f = 0 it requires only that the largest absolute AUC difference from V14 is at most 0.08, a sanity band set at about twice the 0.04 seen. The band was chosen after seeing 0.0405, and is disclosed as such. Nothing else changes: the f = 0 arm in V15 is generated inside V15, and the primary contrast (AUC at f minus AUC at f = 0, paired by world) compares V15 with V15, so it does not depend on matching V14. World 0 files from the first start are kept and counted. The amended freeze commit message is "V15 amended design and scripts (MWEM replication check), committed before worlds 1 to 29 were run", and its hash is written to `_drafts/v15/FREEZE_RECORD_V15_AMENDED.txt`. The first freeze record `FREEZE_RECORD_V15.txt` is kept.

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
    7db7ce52f225bd5459e7b3c35617e868200111828c8d5af978e8ddf0ec0bf994  v15/v15_protocol.py
    66a8379dec6017fb7bf5859900ce60931d353191e2dca47e5a26c3cf1f50b3e6  v15/analyse_v15.py
