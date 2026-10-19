# Note on package versions, V18 and V19 (written 18 Oct 2026, 22:20 local time, during the V18 world-0 smoke test)

The V18 environment report (`_drafts/v18/results/ENV_V18.txt`) shows versions that differ from the frozen design text:
- ctgan 0.11.1 and rdt 1.19.0 were already installed in the user site-packages and took precedence over ctgan 0.12.1 and rdt 2.0.0 in `<LOCAL_PATH>`. This is how the job was designed to load packages (the E: folder is appended after site-packages), but the design text named 0.12.1 and 2.0.0.
- smartnoise-synth is 1.0.6, not the 1.0.8 whose code was read in the cloud.

Checked in the cloud the same evening, before any V18 result was seen:
- smartnoise-synth 1.0.6 and 1.0.8: `snsynth/pytorch/nn/dpctgan.py` and `snsynth/pytorch/nn/ctgan/` are identical. The budget check, accounting and exact-frequency sampler described in the V18 design apply unchanged. Files that differ (aim, mst, transform/bin, transform/standard, utils) are not used by the all-categorical DPCTGAN release.
- ctgan 0.11.1 and 0.12.1: `synthesizers/ctgan.py` differs only in how the verbose progress line formats its numbers; `data_sampler.py`, `data_transformer.py` and `synthesizers/base.py` are identical. The CTGAN reference (V18) and the DP-CTGAN built on ctgan's classes (V19) are algorithmically the same under either version.

No frozen file was changed. The versions actually used are recorded in every result file (`meta`) and in `ENV_V18.txt` and `ENV_V19.txt`. The paper reports the versions actually used.
