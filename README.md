# Code for "Silent Failures in Preprocessing" (anonymous submission)

This repository holds the code and aggregate results behind the revised paper. It contains no records.

## Contents
- `patterns/`: the nine executed examples (Table 2 of the paper), their outputs on Pandas 1.5.3, 2.0.3, 2.3.3 and 3.0.6, and the summary table.
- `scanner/`: the static pattern scanner, its tests, and the detection-limits suite (62 snippets) (Section 3.3).
- `pilot_scan/`: the frozen protocol and the aggregate result of the scan of 30 public repositories (Section 3.4). Repository names are withheld; they are available to the programme chairs on request. The freeze record was written before the search, but its git commit failed, so it is not time-stamped in version control.
- `challenge_set/`: the challenge-set script for CONTROL and V1 to V6 with its result file, and the V7 out-of-catalogue injection script with its result file (Section 3.2).
- `original_v8/`: the original three-arm experiment scripts and stored outputs, whose membership result is withdrawn in the paper (Section 4.2); a check of the attack on disjoint data; and a note recording that the unchanged script reproduces every stored field.
- `designs/`: the frozen design document of each run, written before the run. Each lists the sha256 of the scripts it covers. Author name and file-path text are redacted in these copies.
- `protocol/`: the repaired protocol and analysis scripts, one folder per run:
  - `repaired_protocol/`: the repaired V8 protocol, the KDE-ratio attack (own implementation) and a vendored copy of the synth_mia attacks.
  - `v9`: MIMIC-IV, Laplace-perturbed records, 100 worlds.
  - `v10`: Adult, Laplace-perturbed records, 100 worlds. `v11`: MST. `v12`: the original mismatch inside the repaired protocol, and MST. `v13`: injected patterns. `v14`: MWEM and AIM. `v14d`: PrivBayes-style generator. `v15`, `v16`: planted member rows at epsilon 10 and 1. `v17`: planted rows under injected patterns.
  - `v18`: smartnoise DPCTGAN at epsilon 1 and 10, with non-private CTGAN as a reference.
  - `v19`: our own DP-CTGAN on the standard CTGAN classes and opacus 1.5.2 (`dp_ctgan_opacus.py`). `RUN_V18_V19.py` runs V18 and then V19.
- `results/`: the analysis output of each run, V9 to V19, and `per_world/` with the per-world result files (aggregate AUCs per world, no records).

## Data
- Adult is the public UCI Adult file. Scripts read it from the environment variable `ADULT_CSV`.
- MIMIC-IV requires credentialed access and cannot be shared. Scripts read the canonical MIMIC-IV extract from the environment variable `MIMIC_CANONICAL_CSV`.

## Notes
- "Laplace-perturbed records" are not differentially private.
- The PrivBayes-style generator is DataSynthesizer's correlated attribute mode, not the original authors' code.
- V18: smartnoise DPCTGAN training moved its release further from the members than its own untrained generator, so its equivalence verdicts are labelled UNINFORMATIVE by the frozen rule.
- V19 is our own implementation. Its accounting is approximate (rows are drawn by CTGAN's conditional sampler, not Poisson sampling), and category frequencies are used outside the privacy budget.
- On the run machine, V18 and V19 loaded smartnoise-synth 1.0.6 and ctgan 0.11.1. The code paths used are identical to the versions named in the designs; see `protocol/v18/NOTE_PACKAGE_VERSIONS_V18_V19.md`.
- Results support equivalence between arms for the attacks that passed their controls. They are not evidence of privacy.

## Run scripts and vendored code
- `RUN_*.py` scripts are sanitised copies: local paths and the git identity were replaced, so their hashes differ from those in the designs, which refer to the originals.
- `protocol/v14d/vendor` is DataSynthesizer 0.1.13 with one serial-map edit, and `protocol/repaired_protocol/_vendored_synth_mia_0981eadb` is a copy of the synth_mia attack library. Both are third-party code under their own licences.

## Reproducibility note
MWEM (smartnoise-synth) is not bit-reproducible: the same call with the same seed gives different tables on repeat runs, so MWEM numbers can differ by up to about 0.04 AUC between runs. The MWEM results in the paper are the recorded runs. The other generators, the attacks and the world seeds repeat exactly.
