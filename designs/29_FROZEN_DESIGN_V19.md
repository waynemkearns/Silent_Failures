# 29 Frozen design V19: a second DP GAN, DP-CTGAN on current opacus, on the same worlds and arms

Written before any V19 world is run on the PC. It is an addendum to `28_FROZEN_DESIGN_V18.md`. It changes no earlier file. `RUN_V19.py` checks the hashes below, refuses to start while any of `RUN_V12.py` to `RUN_V18.py` is running, commits this file and the V19 scripts to git with the message "V19 frozen design and scripts, committed before the V19 run", and writes the commit hash and time to `_drafts/v19/FREEZE_RECORD_V19.txt` before the first job. `RUN_V18_V19.py` starts V19 only after `RUN_V18.py` has ended normally. Nothing starts until the author starts it.

## Why
V18 evaluates smartnoise DPCTGAN, as the 7A response commits. Code testing for V18 showed that smartnoise's training moves its release further from the members than its own untrained generator, at every setting tried, so the V18 verdicts will probably be UNINFORMATIVE. Reviewer A's point is that deep generative models expose a different preprocessing surface from marginal models. To test the audit on a DP GAN that does learn, V19 runs a second DP-CTGAN, built on the standard CTGAN code and the current release of opacus.

## Question
On a DP GAN whose training brings the release closer to the members, do the contaminated and size-matched arms give equivalent attack AUCs? Would the same attacks see a planted leak in its release?

## What is unchanged
Everything listed as unchanged in `28_FROZEN_DESIGN_V18.md`: data set-up, world seeds, the three standard arms, encoding, reference policy, reference-fitted scaler, the five attacks, placebo, records-only baseline, near-copy positive control, margin, gates, public binning of the release input, the V15 planted-row rule and seeds, and the one-way and two-way TVD functions. V19 imports the frozen V14 and V18 code unchanged. `RUN_V19.py` repeats the V18 replication check against V14 world 0 (member counts, records-only baseline and positive control, largest absolute difference at most 1e-6).

## What is new
**Synthesizer.** `dp_ctgan_opacus.py`, our own code of about 60 lines, on top of the standard CTGAN (ctgan 0.11.1 as installed on the PC, tested in the cloud with 0.12.1, which is identical in these parts: its DataTransformer, DataSampler, Generator and Discriminator classes, unchanged) and opacus 1.5.2.
- Discriminator: pac = 1 and binary cross-entropy loss, because the CTGAN gradient penalty needs a double backward pass that per-sample clipping does not support. Each step sees B = 64 real rows and 64 generated rows. Every row's gradient is clipped to norm 1, and opacus' DPOptimizer adds Gaussian noise with standard deviation equal to the noise multiplier.
- Accounting: opacus' RDP accountant, one step per discriminator update, sample rate 64 / n, delta = 1/(n sqrt n). Training stops before the step that would take the spent epsilon over the target, so the spent value never exceeds the target. Epoch cap 300.
- Generator: trained only through the discriminator, which is post-processing.

**Releases.** Per arm, on the publicly binned member table, each with n rows: `dpctgan2_eps1` (epsilon 1, noise multiplier 5) and `dpctgan2_eps10` (epsilon 10, noise multiplier 1). Seeds: torch, numpy and random are seeded with 17 x world + epsilon + 100 before each fit. For each release, an untrained generator from the same code, seed and initial weights (zero training steps) is sampled as the fidelity comparison point.

**Choice of noise multipliers.** Fixed before the freeze on fabricated data only. With noise multiplier 1, a single step already exceeds epsilon 1, so epsilon 1 needs a larger multiplier; 5 gave the closest release of those tried at epsilon 1. At epsilon 10, multiplier 1 gave the closest release; multiplier 5 for hundreds of epochs drove the release away from the members, as in smartnoise. This choice was made on fabricated data, not real data, and is disclosed as such.

**Environment.** opacus 1.5.2 and opt-einsum 3.4.0 are installed with `--no-deps` into `<LOCAL_PATH>`. The V19 job places that folder first on its path, so opacus 1.5.2 shadows the opacus 0.14 used by V14 and V18 in the V19 processes only. The job checks that opacus 1.5 is loaded and stops if not. ctgan comes from the existing site-packages if present (ctgan 0.11.1 and rdt 1.19.0 on the PC, found in the V18 environment report), otherwise from `<LOCAL_PATH>`. ctgan 0.11.1 and 0.12.1 differ only in a progress-message format; see `_drafts/v18/NOTE_PACKAGE_VERSIONS_V18_V19.md`.

## Cells and worlds
`adult_gan2` and `mimic_gan2`, worlds 0 to 29. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## Gates
As in V18: records-only means within 0.45 to 0.55; an attack is informative for a release only if its positive control is above 0.80 in every arm and that release's placebo means are within 0.47 to 0.53.

## Decision rule, fixed now
`analyse_v19.py` implements this rule and prints the verdicts. Each cell has its own Holm families.
1. **Fidelity.** On the `clean_matched` arm, two-way TVD of the trained release minus two-way TVD of its untrained generator, paired by world, one-sided test that the trained release is closer, Holm over the two releases. If not shown, every equivalence verdict for that release is labelled UNINFORMATIVE.
2. **Primary.** Contaminated minus clean_matched at f = 0, paired by world, for each informative attack and both releases. Two one-sided tests against the 0.03 margin, 90% CI, Holm over attacks x releases. Verdicts as in V14.
3. **Secondary, detection, as in V15**, per release.
4. **Descriptive.** Training record (discriminator steps, full epochs, whether the budget stopped training, spent epsilon, fit time), clean_matched minus clean_full, one-way TVD, uniform and non-member comparison points, and mean AUC tables.

## What was seen before this freeze
Code testing in the cloud only, on fabricated Adult-like and MIMIC-like files with independent columns. No real data was used.
- Fabricated 1,000-row table, two-way TVD to the members (one-way in brackets): untrained generator 0.19 (0.12); epsilon 10 with noise multiplier 1, 476 steps, 0.11 (0.06); epsilon 1 with noise multiplier 5, 403 steps, 0.17 (0.10); epsilon 10 with noise multiplier 5, 300 epochs, 0.38 (0.27). Non-members 0.08, uniform draw 0.35.
- Fabricated 251-row table: untrained 0.24; epsilon 10 with multiplier 1, 36 steps, 0.21; epsilon 1 with multiplier 5, 32 steps, 0.21.
- In the full job on fabricated world 0, the 1,000-row arm improved on its untrained generator at both epsilons (0.14 against 0.18 at epsilon 1, 0.12 against 0.17 at epsilon 10); the 251-row arms improved little or not at all. The spent epsilon never exceeded the target (largest 10.00 at epsilon 10, 1.00 at epsilon 1). One world took 233 seconds (Adult) on two cloud CPUs.
- The install was tested in a fresh Python 3.10 environment holding only the V14 packages, with opacus 0.14 still installed; the V19 job loaded opacus 1.5.2 from the separate folder.

## Expected outcome, stated before the run
I expect the fidelity test to pass at epsilon 10 on the Adult cell and possibly at epsilon 1, and to be weaker on MIMIC-IV, where the arms are smaller. Where it passes, I expect attack AUCs near 0.50 and equivalence between the contaminated and size-matched arms, as for the marginal synthesizers. I expect planted rows to be detected at f = 0.10 and 0.25.

## Known limits
Our own implementation, not a published package; the paper must say so and point to the code. Rows are drawn by CTGAN's conditional sampler, not by Poisson sampling, so the accounting is approximate. The conditioning vectors use the exact category frequencies of the training data, outside the budget, as in smartnoise, so the release is not differentially private with respect to those frequencies. Noise multipliers were fixed on fabricated data. Two epsilons, two datasets, one architecture. PrivSyn, PATECTGAN, relational synthesizers and diffusion models are not run.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`:
- "On a second DP-CTGAN, our implementation on the standard CTGAN code and opacus 1.5.2 (noise multiplier [s], [k] discriminator steps on average), the contaminated and size-matched arms [verdict] at epsilon [e] ([x] AUC, 90% CI [a, b])." If the fidelity rule labelled the verdict UNINFORMATIVE, the sentence must add: "Training did not bring the release closer to the members than an untrained generator, so this does not show whether the audit separates the arms."
- Secondary as in V18.
- The paper states the two known limits on accounting and category frequencies.
No sentence may say that this synthesizer is or is not private, or that the audit detects leakage in general.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    f14810f5eec162283d8739c913ee1359cffcbb4e4a009abb29a19ce5580365bc  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/dcr.py
    86cbac9eac2391c96961fb798370914336bacbff24e853b95203005f5062a823  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/dcr_diff.py
    f4f316e138bd0dd06ddea5e353cbc031e23a42aaecb14db35ef2e8a1e8d0e185  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/classifier.py
    cedd41d3008f8be1381b295f53883dbf86bf67acfa868fb598bf1f0784c85cb3  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/local_neighborhood.py
    14ad869a72b150f1ca019e473c2ea662569d7bb19c85d36a4132c47aed1fc46e  v14/v14_protocol.py
    be2673b3bf27d2e942a1f4e1d3bfd61e3d18c08ea16ffe063d0ff4e738db2956  v18/v18_protocol.py
    7ce5e9169f3dc14612f08b1a6afbf7394a66a76b3bb721ed4e2c819788d7354c  v19/v19_protocol.py
    05e13943a83d14614b17af610bc0ee9cd4059740bbee58d05220f7d398617e5a  v19/dp_ctgan_opacus.py
    ef8377ebbcecac54ca034cd58963b5020a32530ffde233ca259337abd3944198  v19/analyse_v19.py
