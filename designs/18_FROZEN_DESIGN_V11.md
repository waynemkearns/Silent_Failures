# 18 Frozen design V11: run settings for the two MST cells of V10

Written before any V11 world is run. This is an addendum to 17_FROZEN_DESIGN_V10.md. RUN_V11.py commits this file and the V11 scripts to git before the first job and writes the commit hash and time to _drafts/v11/FREEZE_RECORD_V11.txt.

## Why V11 exists
In the V10 run, the smoke test (world 0) of adult_mst and mimic_mst hit the 45-minute limit and both cells were dropped. The run left no log, so the cause was not recorded. A timing diagnostic was run afterwards on one MST fit (epsilon 10, 1,000 records, 10 bins per numeric column). This was done after the V10 outcome was known, and it is stated here for that reason.

| Dataset | Columns | Seconds per MST fit |
| --- | --- | --- |
| Adult | 4, 6, 8, 10, 12, 15 | 131, 109, 113, 124, 148, 177 |
| MIMIC-IV | 4, 6, 8, 10, 13, 17 | 41, 59, 111, 153, 164, 193 |

No fit failed or timed out at 300 s. One world needs 9 fits (3 arms by epsilon 1, 10, 100), so about 20 to 30 minutes of MST per world when run alone. The V10 smoke test ran the cells at the same time on 8 cores. The working explanation is that 9 fits per world plus contention exceeded 45 minutes. This was not confirmed by a log.

## What changes
Run settings only. The question, the cells' data and contamination, the seeds, the MST release, the attacks, the gates, the margin, the verdicts and the analysis script are the same as in V10.
- Cells run: adult_mst and mimic_mst only. adult_laplace is finished in V10 (100 worlds) and its results stand and are not rerun.
- Smoke test: world 0 of each MST cell, one cell at a time, 3-hour limit each. An error or timeout drops the cell and is reported as dropped.
- Main run: worlds 1 to 49 of both cells (target 50 worlds each, with world 0), 4 parallel workers, 2 threads each. A job is stopped after 3 hours.
- Progress: each MST fit writes a line to _drafts/v10/results/progress_<cell>_w<world>.log, so a timeout leaves a record.
- Temporary files go to E:\Temp.
- Stopping rule: no new job starts 10 hours after launch. Jobs already running are allowed to finish. An MST cell needs at least 30 completed worlds, as in V10, otherwise no equivalence claim is made for it.
- The V10 drop notices for the two MST cells are renamed so the analysis does not report them. They are kept in the results folder.

## Expected outcome, stated before the run
At 4 workers and about 30 to 45 minutes per world, 10 hours should give roughly 35 to 50 worlds per cell. This is an estimate. If fewer than 30 finish for a cell, the verdict is insufficient worlds.

## Known limits, in addition to those in V10
The positive control (Laplace near-copy) does not test whether an attack detects MST leakage. At epsilon 1 an MST release may leak too little for any attack to differ from 0.5, so an equivalence result there says little. The thread setting may change run time but not results.

## Files and hashes (sha256)
    53931f9b72cea584e462e5fa38966414eead7f7ba4552533b3057f6ad567cac5  v10/v10_protocol.py
    4d533c4b1992b823c815f8ecb187b1d93844de8998dc78048723b4c789ab8867  v10/analyse_v10.py
    3893d741d8d49a61fc01487faeb5e83ce1f4c9e3f9ca73d981b616b67d3322e9  repaired_protocol/kde_ratio_own.py
    98d5b40e1ddcaf5f71526d83e1fa623d4cced30075bdd2be1f1f271ab03409c8  v11/v11_protocol.py
