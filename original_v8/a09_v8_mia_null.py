"""
V8 MIA label-permutation null
=============================
For each arm and seed, train the same Random Forest MIA after randomly
permuting membership labels, then evaluate AUC on the true train/holdout
labels. Under a calibrated attack, null AUC should be near 0.5.
"""

import json
import sys
import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

MIMIC_PATH = Path(__import__("os").environ["MIMIC_CANONICAL_CSV"])
LAB_COLS = [
    "lab_creatinine", "lab_glucose", "lab_hematocrit", "lab_hemoglobin",
    "lab_platelet_count", "lab_potassium", "lab_sodium", "lab_white_blood_cells",
]
NUMERIC_FEATURES = ["age", "length_of_stay", "risk_score", "medication_count"] + LAB_COLS
CAT_FEATURES = ["sex", "ethnicity", "admission_type", "deceased", "is_emergency"]
SEEDS = [0, 1, 2, 3, 42]
EPSILON = 1.0
SEED_SAMPLE = 42
CAP_RATE = 0.40
N_NULL = 20  # permutations per arm×seed

OUT_DIR = Path(__file__).parent / "results" / "verdict_flip"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def encode(df, feats):
    out = df[feats].copy()
    for c in CAT_FEATURES:
        if c in out.columns:
            le = LabelEncoder()
            out[c] = le.fit_transform(out[c].astype(str))
    return out.fillna(0)


def add_laplace(df_enc, epsilon, seed):
    rng = np.random.default_rng(seed)
    out = df_enc.copy().values.astype(float)
    for i in range(out.shape[1]):
        s = df_enc.iloc[:, i].std()
        if s > 0:
            out[:, i] += rng.laplace(0, s / epsilon, len(out))
    return out


def mia_auc(train, syn, holdout, seed, permute_train_labels=False, perm_seed=None):
    rng = np.random.default_rng(seed)
    n = min(len(syn), len(train))
    idx = rng.choice(len(syn), n, replace=False)
    X = np.vstack([train, syn[idx]])
    y = np.hstack([np.ones(len(train)), np.zeros(n)])
    if permute_train_labels:
        prng = np.random.default_rng(perm_seed)
        y = prng.permutation(y)
    clf = RandomForestClassifier(100, random_state=seed).fit(X, y)
    st = clf.predict_proba(train)[:, 1]
    sh = clf.predict_proba(holdout)[:, 1]
    yt = np.hstack([np.ones(len(st)), np.zeros(len(sh))])
    ys = np.hstack([st, sh])
    return float(roc_auc_score(yt, ys))


def main():
    print("=" * 68)
    print("V8 MIA Label-Permutation Null")
    print("=" * 68)

    df_full = pd.read_csv(MIMIC_PATH)
    df_full = df_full.drop(
        columns=["encounter_date", "discharge_date", "patient_id", "encounter_id"],
        errors="ignore",
    )
    df_source = df_full.sample(n=2000, random_state=SEED_SAMPLE).reset_index(drop=True)
    df_train_pool = df_source.iloc[:1000].copy()
    df_holdout_raw = df_source.iloc[1000:2000].copy()

    df_clean_full = df_train_pool.dropna(subset=LAB_COLS).reset_index(drop=True)
    rng_cap = np.random.default_rng(SEED_SAMPLE)
    cap_mask = rng_cap.random(len(df_train_pool)) < CAP_RATE
    df_cont_pool = df_train_pool.copy()
    df_cont_pool.loc[cap_mask, LAB_COLS] = np.nan
    df_contaminated = df_cont_pool.dropna().reset_index(drop=True)
    N_MATCH = len(df_contaminated)
    df_clean_matched = df_clean_full.sample(
        n=N_MATCH, random_state=SEED_SAMPLE
    ).reset_index(drop=True)
    df_holdout = df_holdout_raw.dropna(subset=LAB_COLS)

    feats = [c for c in NUMERIC_FEATURES + CAT_FEATURES if c in df_clean_full.columns]
    arms = {
        "clean_full": df_clean_full,
        "clean_matched": df_clean_matched,
        "contaminated": df_contaminated,
    }
    print({k: len(v) for k, v in arms.items()}, "holdout", len(df_holdout))

    results = {arm: {"true": [], "null_mean": [], "null_sd": [], "null_all": []} for arm in arms}

    for seed in SEEDS:
        for arm_name, df_arm in arms.items():
            enc = encode(df_arm, feats)
            enc_h = encode(df_holdout, feats)
            sc = StandardScaler().fit(enc)
            X = sc.transform(enc)
            Xh = sc.transform(enc_h)
            syn = sc.transform(add_laplace(enc, EPSILON, seed))

            true_auc = mia_auc(X, syn, Xh, seed, permute_train_labels=False)
            null_aucs = [
                mia_auc(X, syn, Xh, seed, permute_train_labels=True, perm_seed=seed * 1000 + k)
                for k in range(N_NULL)
            ]
            results[arm_name]["true"].append(true_auc)
            results[arm_name]["null_mean"].append(float(np.mean(null_aucs)))
            results[arm_name]["null_sd"].append(float(np.std(null_aucs)))
            results[arm_name]["null_all"].append([round(a, 6) for a in null_aucs])
            print(
                f"seed {seed} {arm_name:14s}  true={true_auc:.4f}  "
                f"null={np.mean(null_aucs):.4f}±{np.std(null_aucs):.4f}  "
                f"(n_perm={N_NULL})"
            )

    print("\n── Aggregate ──────────────────────────────────────────────────")
    summary = {}
    for arm_name, r in results.items():
        summary[arm_name] = {
            "true_mean": round(float(np.mean(r["true"])), 6),
            "true_sd": round(float(np.std(r["true"])), 6),
            "null_mean": round(float(np.mean(r["null_mean"])), 6),
            "null_sd_across_seeds": round(float(np.std(r["null_mean"])), 6),
            "true_values": [round(x, 6) for x in r["true"]],
            "null_seed_means": [round(x, 6) for x in r["null_mean"]],
        }
        print(
            f"{arm_name:14s}  true={summary[arm_name]['true_mean']:.4f}±"
            f"{summary[arm_name]['true_sd']:.4f}  "
            f"null={summary[arm_name]['null_mean']:.4f}±"
            f"{summary[arm_name]['null_sd_across_seeds']:.4f}"
        )

    out = {
        "experiment": "v8_mia_label_permutation_null",
        "date_run": datetime.utcnow().isoformat(),
        "n_permutations_per_arm_seed": N_NULL,
        "seeds": SEEDS,
        "summary": summary,
        "per_seed": results,
    }
    path = OUT_DIR / "v8_mia_null_results.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved: {path}")
    return out


if __name__ == "__main__":
    main()
