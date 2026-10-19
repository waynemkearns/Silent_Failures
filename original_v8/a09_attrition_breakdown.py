"""
A09 attrition-breakdown companion.

The main A09/V8 experiment (a09_v8_proxy_metric.py) persists only arm sizes and
per-seed DCR/MIA to v8_control_results.json. The Paper 1 (Silent Failures) §3.5
"Substrate attrition" table reports the intermediate P2+P6 cascade decomposition
(1,000 -> -260 -> -297 -> -192 -> 251; 402 masked = 105 overlap + 297 new), which
was previously produced only as runtime prints and never committed.

This script replicates the EXACT sampling/masking logic of a09_v8_proxy_metric.py
(SEED_SAMPLE=42, CAP_RATE=0.40, same dropped columns, same LAB_COLS) and writes
the attrition decomposition to a committed JSON so every number in the paper's
attrition table tethers to an artefact.

Read-only w.r.t. the source canonical; deterministic; no synthesis or MIA.
"""

import json
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

MIMIC_PATH = Path(__import__("os").environ["MIMIC_CANONICAL_CSV"])
DROP_COLS = ["encounter_date", "discharge_date", "patient_id", "encounter_id"]
LAB_COLS = [
    "lab_creatinine", "lab_glucose", "lab_hematocrit", "lab_hemoglobin",
    "lab_platelet_count", "lab_potassium", "lab_sodium", "lab_white_blood_cells",
]
SEED_SAMPLE = 42
CAP_RATE = 0.40

OUT = Path(__file__).parent / "results" / "verdict_flip" / "a09_attrition_breakdown.json"


def sha256_head(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    df_full = pd.read_csv(MIMIC_PATH)
    total_rows = len(df_full)
    df_full = df_full.drop(columns=DROP_COLS, errors="ignore")

    df_source = df_full.sample(n=2000, random_state=SEED_SAMPLE).reset_index(drop=True)
    df_train_pool = df_source.iloc[:1000].copy()

    lab_nan_pre = df_train_pool[LAB_COLS].isna().any(axis=1)
    already_incomplete = int(lab_nan_pre.sum())

    rng_cap = np.random.default_rng(SEED_SAMPLE)
    cap_mask = rng_cap.random(len(df_train_pool)) < CAP_RATE
    n_masked = int(cap_mask.sum())
    overlap = int((cap_mask & lab_nan_pre.values).sum())
    newly_contaminated = int((cap_mask & ~lab_nan_pre.values).sum())

    df_cont = df_train_pool.copy()
    df_cont.loc[cap_mask, LAB_COLS] = np.nan

    lab_nan_post = df_cont[LAB_COLS].isna().any(axis=1)
    any_nan_post = df_cont.isna().any(axis=1)
    removed_by_lab = int(lab_nan_post.sum())
    removed_nonlab_only = int((any_nan_post & ~lab_nan_post).sum())
    medcount_nan_nonlab = int(
        (df_cont["medication_count"].isna() & ~lab_nan_post).sum()
    ) if "medication_count" in df_cont.columns else None
    survivors = int((~any_nan_post).sum())

    clean_full = int((~lab_nan_pre).sum())

    result = {
        "experiment": "a09_attrition_breakdown",
        "purpose": "Persist the Paper 1 §3.5 substrate-attrition decomposition for the P2+P6 cascade.",
        "source_canonical": str(MIMIC_PATH),
        "source_sha256": sha256_head(MIMIC_PATH),
        "source_row_count": total_rows,
        "params": {"seed_sample": SEED_SAMPLE, "cap_rate": CAP_RATE, "lab_cols": LAB_COLS},
        "attrition_table": {
            "sampled_training_pool": len(df_train_pool),
            "already_incomplete_lab_nan": already_incomplete,
            "newly_contaminated_by_p2": newly_contaminated,
            "removed_nonlab_nan": removed_nonlab_only,
            "medication_count_nan_among_nonlab": medcount_nan_nonlab,
            "p6_survivor_cohort": survivors,
        },
        "p2_mask_detail": {
            "records_masked": n_masked,
            "mask_fraction": round(n_masked / len(df_train_pool), 4),
            "overlap_with_already_invalid": overlap,
            "previously_clean": newly_contaminated,
        },
        "cross_check": {
            "clean_full_expected_740": clean_full,
            "removed_by_lab_nan_post": removed_by_lab,
            "sum_removed": already_incomplete + newly_contaminated + removed_nonlab_only,
            "pool_minus_removed": len(df_train_pool)
            - (already_incomplete + newly_contaminated + removed_nonlab_only),
        },
    }

    OUT.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nWritten: {OUT}")


if __name__ == "__main__":
    main()
