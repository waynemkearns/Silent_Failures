"""
V8 Control Run — Size-Matched Three-Way Comparison
===================================================
Addresses reviewer objection: the n=740 (clean) vs n=251 (contaminated) DCR difference
may be purely a sample-size effect (fewer training records → larger nearest-neighbour
distances mechanically). This control adds a third arm: clean_matched (n=251 randomly
subsampled from the clean substrate) to isolate the sample-size effect from the
contamination-selection effect.

Three arms:
  clean_full      n=740  (original clean substrate, all survivors of dropna(lab_cols))
  clean_matched   n=251  (random subsample of clean_full, size-matched to contaminated)
  contaminated    n=251  (P2+P6 survivor cohort from original V8)

Key comparisons:
  clean_full vs clean_matched   -> estimates the sample-size effect alone
  clean_matched vs contaminated -> estimates contamination-selection effect at matched n
  clean_full vs contaminated    -> total effect (replicates original V8)
"""

import json, sys, io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

MIMIC_PATH = Path(__import__("os").environ["MIMIC_CANONICAL_CSV"])
LAB_COLS = [
    "lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin",
    "lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"
]
NUMERIC_FEATURES = ["age","length_of_stay","risk_score","medication_count"] + LAB_COLS
CAT_FEATURES = ["sex","ethnicity","admission_type","deceased","is_emergency"]
SEEDS = [0, 1, 2, 3, 42]
EPSILON = 1.0
SEED_SAMPLE = 42
CAP_RATE = 0.40

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


def compute_dcr(syn, ref):
    nn = NearestNeighbors(n_neighbors=1).fit(ref)
    d, _ = nn.kneighbors(syn)
    return float(d.mean())


def compute_mia(train, syn, holdout, seed):
    rng = np.random.default_rng(seed)
    n = min(len(syn), len(train))
    idx = rng.choice(len(syn), n, replace=False)
    X = np.vstack([train, syn[idx]])
    y = np.hstack([np.ones(len(train)), np.zeros(n)])
    clf = RandomForestClassifier(100, random_state=seed).fit(X, y)
    st = clf.predict_proba(train)[:, 1]
    sh = clf.predict_proba(holdout)[:, 1]
    yt = np.hstack([np.ones(len(st)), np.zeros(len(sh))])
    ys = np.hstack([st, sh])
    return float(roc_auc_score(yt, ys))


def main():
    print("=" * 68)
    print("V8 Control Run — Three-Way Size-Matched Comparison")
    print("=" * 68)

    df_full = pd.read_csv(MIMIC_PATH)
    df_full = df_full.drop(
        columns=["encounter_date","discharge_date","patient_id","encounter_id"],
        errors="ignore"
    )
    df_source = df_full.sample(n=2000, random_state=SEED_SAMPLE).reset_index(drop=True)
    df_train_pool = df_source.iloc[:1000].copy()
    df_holdout_raw = df_source.iloc[1000:2000].copy()

    # ── Arm A: clean_full ─────────────────────────────────────────────────────
    df_clean_full = df_train_pool.dropna(subset=LAB_COLS).reset_index(drop=True)

    # ── Arm B: contaminated (P2+P6) ───────────────────────────────────────────
    rng_cap = np.random.default_rng(SEED_SAMPLE)
    cap_mask = rng_cap.random(len(df_train_pool)) < CAP_RATE
    df_cont_pool = df_train_pool.copy()
    df_cont_pool.loc[cap_mask, LAB_COLS] = np.nan
    df_contaminated = df_cont_pool.dropna().reset_index(drop=True)

    # ── Arm C: clean_matched (same n as contaminated, random subsample) ───────
    N_MATCH = len(df_contaminated)
    df_clean_matched = df_clean_full.sample(
        n=N_MATCH, random_state=SEED_SAMPLE
    ).reset_index(drop=True)

    print(f"\nArm sizes:")
    print(f"  clean_full      n = {len(df_clean_full)}")
    print(f"  clean_matched   n = {len(df_clean_matched)}")
    print(f"  contaminated    n = {len(df_contaminated)}")

    feats = [c for c in NUMERIC_FEATURES + CAT_FEATURES if c in df_clean_full.columns]
    df_holdout = df_holdout_raw.dropna(subset=LAB_COLS)

    per_seed = []
    for seed in SEEDS:
        enc_f = encode(df_clean_full, feats)
        enc_m = encode(df_clean_matched, feats)
        enc_c = encode(df_contaminated, feats)
        enc_h = encode(df_holdout, feats)

        sc_f = StandardScaler().fit(enc_f)
        sc_m = StandardScaler().fit(enc_m)
        sc_c = StandardScaler().fit(enc_c)

        Xf = sc_f.transform(enc_f)
        Xm = sc_m.transform(enc_m)
        Xc = sc_c.transform(enc_c)
        Xh_f = sc_f.transform(enc_h)
        Xh_m = sc_m.transform(enc_h)
        Xh_c = sc_c.transform(enc_h)

        syn_f = sc_f.transform(add_laplace(enc_f, EPSILON, seed))
        syn_m = sc_m.transform(add_laplace(enc_m, EPSILON, seed))
        syn_c = sc_c.transform(add_laplace(enc_c, EPSILON, seed))

        dcr_f = compute_dcr(syn_f, Xf)
        dcr_m = compute_dcr(syn_m, Xm)
        dcr_c = compute_dcr(syn_c, Xc)

        mia_f = compute_mia(Xf, syn_f, Xh_f, seed)
        mia_m = compute_mia(Xm, syn_m, Xh_m, seed)
        mia_c = compute_mia(Xc, syn_c, Xh_c, seed)

        per_seed.append({
            "seed": seed,
            "dcr_clean_full": dcr_f,
            "dcr_clean_matched": dcr_m,
            "dcr_contaminated": dcr_c,
            "mia_clean_full": mia_f,
            "mia_clean_matched": mia_m,
            "mia_contaminated": mia_c,
            "delta_size_effect": dcr_m - dcr_f,        # clean_matched - clean_full
            "delta_selection_effect": dcr_c - dcr_m,   # contaminated - clean_matched
            "delta_total": dcr_c - dcr_f,              # total (replicates V8)
        })
        print(
            f"  seed {seed}: "
            f"DCR full={dcr_f:.4f}  matched={dcr_m:.4f}  cont={dcr_c:.4f}  |  "
            f"size_delta={dcr_m-dcr_f:+.4f}  sel_delta={dcr_c-dcr_m:+.4f}  |  "
            f"MIA full={mia_f:.4f}  matched={mia_m:.4f}  cont={mia_c:.4f}"
        )

    # ── Aggregate ─────────────────────────────────────────────────────────────
    def mean_sd(key):
        vals = [r[key] for r in per_seed]
        return np.mean(vals), np.std(vals), vals

    print("\n── Summary (mean ± SD across 5 seeds) ─────────────────────────")
    for label, key in [
        ("DCR clean_full", "dcr_clean_full"),
        ("DCR clean_matched", "dcr_clean_matched"),
        ("DCR contaminated", "dcr_contaminated"),
        ("Δ size effect (matched-full)", "delta_size_effect"),
        ("Δ selection effect (cont-matched)", "delta_selection_effect"),
        ("Δ total effect (cont-full)", "delta_total"),
        ("MIA clean_full", "mia_clean_full"),
        ("MIA clean_matched", "mia_clean_matched"),
        ("MIA contaminated", "mia_contaminated"),
    ]:
        m, sd, vals = mean_sd(key)
        print(f"  {label:<40} {m:+.4f} ± {sd:.4f}  {vals}")

    m_size, _, _ = mean_sd("delta_size_effect")
    m_sel, _, _  = mean_sd("delta_selection_effect")
    m_tot, _, _  = mean_sd("delta_total")

    print("\n── Interpretation ──────────────────────────────────────────────")
    if abs(m_size) > abs(m_sel):
        print("  SAMPLE-SIZE DOMINATES: size effect larger than selection effect.")
        print("  The original V8 DCR difference is primarily explained by n, not contamination.")
        conclusion = "size_dominated"
    elif m_sel > 0.05:
        print("  SELECTION EFFECT SURVIVES SIZE-MATCHING: contamination produces")
        print("  DCR inflation beyond the pure sample-size effect.")
        conclusion = "selection_survives"
    else:
        print("  INCONCLUSIVE: selection effect is present but small.")
        conclusion = "inconclusive"
    print(f"  size_effect={m_size:+.4f}  selection_effect={m_sel:+.4f}  total={m_tot:+.4f}")

    # ── Save ─────────────────────────────────────────────────────────────────
    out = {
        "experiment": "v8_control_size_matched",
        "date_run": datetime.utcnow().isoformat(),
        "arm_sizes": {"clean_full": len(df_clean_full),
                      "clean_matched": len(df_clean_matched),
                      "contaminated": len(df_contaminated)},
        "per_seed": per_seed,
        "aggregate": {
            k: {"mean": round(np.mean([r[k] for r in per_seed]), 6),
                "sd":   round(np.std([r[k] for r in per_seed]), 6),
                "values": [round(r[k], 6) for r in per_seed]}
            for k in per_seed[0] if k != "seed"
        },
        "conclusion": conclusion,
    }
    path = OUT_DIR / "v8_control_results.json"
    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults saved to: {path}")
    return out


if __name__ == "__main__":
    main()
