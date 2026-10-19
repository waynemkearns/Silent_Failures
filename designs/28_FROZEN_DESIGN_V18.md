# 28 Frozen design V18: DPCTGAN, a DP GAN, with a non-private CTGAN reference, on the same worlds and arms

Written 17 Oct 2026, before any V18 world is run on the PC. It is an addendum to `23_FROZEN_DESIGN_V14.md` and `25_FROZEN_DESIGN_V15.md`. It changes no earlier file. `RUN_V18.py` checks the hashes below, refuses to start while any of `RUN_V12.py` to `RUN_V17.py` is running, commits this file and the V18 scripts to git with the message "V18 frozen design and scripts, committed before the V18 run", and writes the commit hash and time to `_drafts/v18/FREEZE_RECORD_V18.txt` before the first job. It does not start until the author starts it.

## Why
The submitted response to review 7A says: "We will evaluate DPCTGAN, which already runs in our setup, in the revision; PrivSyn and diffusion are not evaluated." Reviewer A asked for DP GANs because deep generative models expose a different preprocessing surface from marginal models. V14 Part B only showed that DPCTGAN runs (20 epochs, epsilon 10, no attack, no claim). V18 is the evaluation.

## Question
On a DP GAN release, do the contaminated and size-matched arms give equivalent attack AUCs, as they did for MST, MWEM, AIM and the PrivBayes-style synthesizer? Three further questions decide how that answer can be read. Did the GAN learn anything about the members? Would the same attacks have seen a planted leak in a GAN release? And what do the attacks see on a GAN that does learn the table, without DP?

## What is unchanged
Data set-up, world seeds, the three standard arms (`clean_full`, `clean_matched`, `contaminated`), encoding, reference policy, reference-fitted scaler, the five attacks, placebo, records-only baseline, near-copy positive control (Laplace, divisor 100), margin, gates, and the public binning of the release input (bin edges from the attacker's reference, as for every DP release since V11). They are the frozen V10 and V14 code, imported unchanged. `RUN_V18.py` checks on world 0 of both cells that the member counts, the records-only baseline and the positive control equal the V14 `adult_mwem` and `mimic_mwem` world 0 values (largest absolute difference at most 1e-6) and stops if not. These quantities do not depend on the release, so an exact match is required.

## What is new
**Releases.** Three per arm, all fitted on the same publicly binned member table, each with n rows (the member count of the arm).
- `dpctgan_eps1` and `dpctgan_eps10`: DPCTGAN from smartnoise-synth (the version installed on the PC, recorded in `ENV_V18.txt`), `preprocessor_eps=0`. Batch size 64, as in the V14 Part B feasibility run. Epoch cap 300, the library default. Every other setting is the library default, including noise multiplier 5, gradient clipping norm 1 and delta = 1/(n sqrt n). Seeds: torch, numpy and random are seeded with 17 x world + epsilon before each fit.
- `ctgan_nodp`: CTGAN from the `ctgan` package, version 0.12.1, which is not differentially private. Library defaults: batch 500, 300 epochs. Seed 17 x world + 3. It is a reference only. It shows what the attacks see on a GAN that learns the table. No privacy statement is made about it.
Nine fits per world, plus an untrained generator for each release (same library, same seed and initial weights, zero training steps), which is sampled but not attacked. `ctgan` 0.12.1, `rdt` 2.0.0, `tqdm` 4.67.1 and `colorama` 0.4.6 are installed with `--no-deps` into a separate folder, `<LOCAL_PATH>`, which the job appends after the existing site-packages, so every package already installed for V14 keeps precedence.

**DPCTGAN training record.** For every DPCTGAN fit: epochs trained, whether the library's budget check stopped training, the spent epsilon recomputed with the library's own accountant and settings, and fit time.

**Planted-row sensitivity test, as in V15.** For each arm and release, a share f of the released rows is replaced by real member rows, copied verbatim, with the V15 rule and seeds (seed 9000 + 31 x world + arm index). f = 0, 0.05, 0.10, 0.25. No new fit is needed. The placebo is computed at f = 0 for each release.

**Fidelity check.** On the binned table, the total variation distance (TVD) between the release and the members, averaged over single columns (one-way) and over all column pairs (two-way). The deciding comparison point is the untrained generator of the same release. Both GAN libraries draw rows from the exact category frequencies of the training data, so an untrained generator is already much closer to the members than a uniform draw; only a gain over the untrained generator shows that training learned anything. The non-members (the sampling floor), an independent uniform draw over each column's bins (seed 7000 + 31 x world + arm index) and one-way TVD are reported but do not decide.

## Cells and worlds
`adult_gan` and `mimic_gan`, worlds 0 to 29. Minimum 30 worlds per cell; below that the cell reports INSUFFICIENT WORLDS and no claim is made.

## Gates (as in V10 to V17)
Records-only means on the three standard arms within 0.45 to 0.55. An attack is informative for a release only if its near-copy positive control is above 0.80 in every arm and that release's placebo means (f = 0, all arms) are within 0.47 to 0.53. Attacks that fail are reported and excluded from the claims for that release.

## Decision rule, fixed now
Each cell is analysed on its own, with its own Holm families. `analyse_v18.py` implements this rule and prints the verdicts.
1. **Fidelity, which decides how the equivalence verdicts are read.** On the `clean_matched` arm, two-way TVD of the trained release minus two-way TVD of its untrained generator, paired by world, one-sided test that the trained release is closer, Holm over the three releases. If this is not shown for a release, every equivalence verdict for that release is labelled UNINFORMATIVE, because a release that training did not bring closer to the members cannot show whether the audit separates the arms.
2. **Primary (DPCTGAN).** Contaminated minus clean_matched at f = 0, paired by world, for each informative attack and both DPCTGAN releases. Two one-sided tests against the 0.03 margin, 90% CI, Holm over attacks x the two releases. Verdicts as in V14: "equivalent within the margin", "SHIFT beyond the margin", or "inconclusive".
3. **Reference (CTGAN, not DP).** The same contrast for `ctgan_nodp`, in its own Holm family.
4. **Secondary, detection, as in V15.** On the `clean_matched` arm, AUC at share f minus AUC at f = 0, paired by world, for each informative attack and f > 0, per release. "detected" if the Holm p for "increase > 0" is below 0.05; "beyond the margin" if the Holm p for "increase > 0.03" is below 0.05.
5. **Descriptive.** The DPCTGAN training record, clean_matched minus clean_full at f = 0, one-way TVD, and mean AUC for every arm, release, share and attack.

## What was seen before this freeze
Code testing in the cloud only, on fabricated Adult-like and MIMIC-like files with independent columns. No real data was used. Nothing was tuned on real data, and all settings were fixed before any real-data fit.
- The library code (smartnoise-synth 1.0.8) was read. `dpctgan.py` checks the spent epsilon at the start of each epoch and stops when it exceeds the target, so a budget-stopped fit has spent slightly more than the target. `ctgan/data_sampler.py` computes exact category frequencies from the training data and uses them for the conditioning vectors, outside the privacy accounting. `patectgan.py` uses one or two teachers at these row counts and fills its teacher list with one shared discriminator object; PATECTGAN is therefore not used.
- Fabricated Adult file, world 0, batch 64, cap 300: at epsilon 1 training stopped after 14 epochs on the 1,000-row arm and 6 epochs on the 251-row arms (spent 1.02 and 1.06); at epsilon 10 the 1,000-row arm reached the cap at 300 epochs (spent 5.68) and the 251-row arms stopped at 287 (spent 10.02).
- One-way TVD to the members on the fabricated 1,000-row table: non-members 0.03; uniform draw 0.22; DPCTGAN at epsilon 10 0.61 to 0.68 (the release collapses towards one bin per column); DPCTGAN with almost no noise (noise multiplier 0.01, epsilon 1e9) 0.20; DPCTGAN at epsilon 10 with batch 500 or 200 0.42 to 0.51; CTGAN without DP, library defaults, 0.11 (0.06 on 251 rows). CTGAN with batch 50 was worse (0.17 and 0.09) and slower, so library defaults were kept. The library's own non-private mode for DPCTGAN (`disabled_dp=True`) ran out of memory.
- Batch 500 was not chosen for DPCTGAN because it exceeds the 251-row arms, which makes the library's sampling rate larger than 1.
- Later the same day, before any run: an untrained generator was found to beat the uniform draw in both libraries (two-way TVD on the fabricated 1,000-row table: smartnoise DPCTGAN untrained 0.17, uniform 0.35). Trained smartnoise DPCTGAN was further from the members than its own untrained generator at every setting tried (for example 0.50 at epsilon 10 with noise multiplier 1). The comparison point was therefore changed from the uniform draw to the untrained generator. This change was made before the design was frozen and before any real-data fit.
- One full fabricated world took 269 seconds (Adult) and 128 seconds (MIMIC-like) on two cloud CPUs, with all three releases.
- The install command was tested in a fresh Python 3.10 environment holding only the V14 packages.

## Expected outcome, stated before the run
At epsilon 1, DPCTGAN trains for only a few epochs, so I expect a release close to noise and attack AUCs near 0.50 in every arm. At epsilon 10 I expect DPCTGAN to collapse partly or fully, as on the fabricated table, so I expect the fidelity rule to label its verdicts UNINFORMATIVE. For CTGAN without DP I expect a release closer to the members than its untrained generator, at least on the 1,000-row arm, attack AUCs near or slightly above 0.50, and equivalence between the contaminated and size-matched arms. I expect planted rows to be detected for every release as in V15, with f = 0.10 and 0.25 beyond the margin.

## Known limits
One DP GAN from one library here; a second DP GAN on current opacus is run separately as V19 (`29_FROZEN_DESIGN_V19.md`). Library defaults, library defaults, two epsilons, two datasets. The epsilon is the library's nominal DP-SGD value for the discriminator, as computed by its own accountant; it is not audited here. The library samples rows by condition vector, not by Poisson sampling, so its accounting is approximate. Category sets and their exact frequencies are taken from the training data outside the privacy budget, so the release is not differentially private with respect to those quantities. CTGAN without DP is a reference, not a private synthesizer. The planted share is a property of the released table, not a statement about what either GAN releases. PrivSyn, PATECTGAN, relational synthesizers (PrivLava, PrivPetal) and diffusion models are not run.

## Allowed statements after the run, fixed now
Only if the analysis file exists, the cell met its minimum worlds and gates, and the results commit is confirmed by `git log`:
- Primary: "On DPCTGAN, a DP GAN (smartnoise-synth, batch 64, epoch cap 300), the contaminated and size-matched arms [verdict] at epsilon [e] ([x] AUC, 90% CI [a, b]); the GAN trained for [k] epochs on average at that epsilon." If the fidelity rule labelled the verdict UNINFORMATIVE, the sentence must add: "Training did not bring the release closer to the members than an untrained generator, so this does not show whether the audit separates the arms."
- Reference: "On CTGAN without differential privacy, used as a reference, the contaminated and size-matched arms [verdict] ([x] AUC, 90% CI [a, b])." with the same UNINFORMATIVE clause if it applies.
- Secondary: "When a known share f of a [DPCTGAN or CTGAN] release was replaced by real member records, the same attacks [verdict] (AUC [x] higher, 90% CI [a, b] at f = [f])."
- Library limits: the paper states that smartnoise DPCTGAN draws conditioning vectors from exact category frequencies outside its privacy accounting, and that its accounting is the library's own.
Each cell is judged on its own gates and worlds. Anything not met is described as frozen and incomplete. No sentence may say that DPCTGAN or CTGAN is or is not private, or that the audit detects leakage in general.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    f14810f5eec162283d8739c913ee1359cffcbb4e4a009abb29a19ce5580365bc  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/dcr.py
    86cbac9eac2391c96961fb798370914336bacbff24e853b95203005f5062a823  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/dcr_diff.py
    f4f316e138bd0dd06ddea5e353cbc031e23a42aaecb14db35ef2e8a1e8d0e185  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/classifier.py
    cedd41d3008f8be1381b295f53883dbf86bf67acfa868fb598bf1f0784c85cb3  repaired_protocol/_vendored_synth_mia_0981eadb/attackers/local_neighborhood.py
    14ad869a72b150f1ca019e473c2ea662569d7bb19c85d36a4132c47aed1fc46e  v14/v14_protocol.py
    be2673b3bf27d2e942a1f4e1d3bfd61e3d18c08ea16ffe063d0ff4e738db2956  v18/v18_protocol.py
    581449c2eef1589bf44033c710f799e424eb5ec6e29bd96d60a9ab77a03de388  v18/analyse_v18.py
