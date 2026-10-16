# Code for "Silent Failures in Preprocessing" (anonymous submission)

This repository holds the code and analysis outputs behind the rebuttal and revision of the paper. It contains no data.

## Contents
- `protocol/`: the evaluation protocol and analysis scripts used for the rebuttal runs, one folder per frozen design (v10 Laplace, v11 MST, v12 mismatch and MST, v13 injected patterns, v14 MWEM and AIM, v14d PrivBayes-style generator, v15 planted member rows, v16 planted rows at epsilon 1 with noisy copies, v17 planted rows under injected patterns). `protocol/v14d/vendor` is DataSynthesizer 0.1.13 with one serial-map edit; it is third-party code under its own licence.
- `designs/`: the frozen design documents, written before each run. Author name and file-path text are redacted in these copies; the originals are time-stamped in the authors' private git history. Each lists the sha256 of the scripts it covers.
- `scanner/`: the static pattern scanner, its tests, and the detection-limits suite (62 snippets).
- `patterns/`: the nine toy examples, their outputs on Pandas 1.5.3, 2.0.3, 2.3.3 and 3.0.6, and the summary table.
- `results/`: the analysis output file of each run (aggregate text only, no records), v10 to v17. These are the files the rebuttal numbers are read from.
- `pilot_scan/`: the frozen protocol and the aggregate result of the scan of 30 public repositories. Repository names are withheld here; they are available to the programme chairs on request. The freeze record was written before the search, but its git commit failed, so it is not time-stamped in version control.

## Data
- Adult is the public UCI Adult file. Put it at `data/adult.csv`.
- MIMIC-IV requires credentialed access and cannot be shared. Scripts read the canonical MIMIC extract from the path in the environment variable `MIMIC_CANONICAL_CSV`.

## Notes
- Settings: patient-disjoint split, matched missingness, reference-fitted scaler and vocabulary, label-free attacks, placebo and near-copy controls, equivalence margin 0.03.
- "Laplace-perturbed records" are not differentially private.
- The PrivBayes-style generator is DataSynthesizer's correlated attribute mode, not the original authors' code.
- The runs test whether a preprocessing slip or contamination changes attack scores. They make no claim about the privacy of any generator.

## Run scripts and vendored code
- `protocol/vNN/RUN_VNN.py` drive each run. These are sanitised copies: local data paths and the git identity were replaced, so their hashes differ from the ones in the frozen designs, which refer to the originals. The design documents list the originals' hashes.
- `protocol/repaired_protocol/_vendored_synth_mia_0981eadb` is a vendored copy of the `synth_mia` membership-inference attack library, used for the DCR, DCRDiff, Classifier and LocalNeighborhood attacks. It is third-party code; check the upstream licence before reuse.

## Run order
For v15 to v17: `protocol/vNN/vNN_protocol.py` builds the releases and attacks per world; `analyse_vNN.py` reads the per-world result files and writes the analysis output in `results/`. The per-world result files (aggregate AUCs per world, no records) are in `results/per_world/`.

## Reproducibility note
- MWEM (smartnoise-synth) is not bit-reproducible: the same call with the same seed gives different tables on repeat runs, so MWEM numbers can differ by up to about 0.04 AUC between runs. The MWEM results in the paper are the recorded runs. The other generators, the attacks and the world seeds repeat exactly.
