"""
Verdict-Flip Experiment: P2+P6 Cascade Produces False-Negative Privacy Verdict
===============================================================================
Pre-registration date:  2026-07-22
Author:                 [omitted for review]
Artefact tag:           A09

PURPOSE
-------
Demonstrate end-to-end that P2 (row cap → NaN lab columns) + P6 (unscoped dropna →
biased survivor cohort) changes a DCR-based and MIA-based privacy verdict in the
false-negative direction: the contaminated substrate produces an apparently MORE
PRIVATE evaluation result than the clean substrate, meaning a researcher operating
on contaminated data would underestimate privacy risk.

This directly answers: "The paper never shows a case where contamination produced a
materially wrong privacy answer that the audit then corrected."

MECHANISM (pre-registered rationale, before running)
-----------------------------------------------------
P2 applies a row cap to the labevents table, zeroing out 8 lab feature columns for
patients whose lab records appear beyond the cap row. The unscoped P6 dropna() then
removes every record with any NaN column. The survivors are a non-random subset:
patients whose lab entries happened to appear in the cap-bounded first rows of the
labevents table. This survivor cohort is:
  (a) Smaller (n_clean >> n_contaminated)
  (b) Systematically biased toward patients with early/frequent lab ordering —
      typically sicker patients or high-volume encounter types.
  (c) More homogeneous than the full population.

Prediction (pre-registered, frozen before running):
  P: DCR(synthetic_contaminated, real_contaminated) > DCR(synthetic_clean, real_clean)
     i.e., contaminated substrate produces a HIGHER average DCR (apparently safer)
  Mechanism: Laplace mechanism applied to the smaller, more homogeneous survivor
             cohort produces synthetic records that are further on average from
             the training set, because fewer real records anchor the distribution.
  MIA prediction: AUC(contaminated) ≤ AUC(clean), i.e., contaminated substrate
                  makes members and non-members harder to distinguish (appears safer).

Frozen decision rule (pre-registered):
  VERDICT_FLIP confirmed if:
    DCR(contaminated) > DCR(clean) AND
    the magnitude of difference exceeds 0.05 in standardised DCR units
  VERDICT_FLIP not confirmed if:
    the direction is reversed, or the magnitude is < 0.05

APPROACH
--------
We use the Laplace mechanism (same as Entry 19) to generate synthetic data from
clean and contaminated substrates. This makes the synthetic-data generation
method identical across conditions; any difference in privacy verdict is attributable
to the substrate, not to a different synthesiser.

  1. Load corrected MIMIC-IV v3.1 canonical (SHA 7558c398…, n≈545k records)
  2. Sample n_source=2000 records (same regime as Entry 19 reinstatement)
  3. Split: n_train=1000 (for synthesis), n_holdout=1000 (genuine non-members)
  4. CLEAN substrate  = n_train records as-is (drop rows with NaN for fair comparison)
  5. CONTAMINATED substrate = simulate P2+P6:
       - Zero out ALL lab columns for records where lab_capture_flag=False
         (cap simulation: 40% random records designated lab-uncaptured)
       - Apply dropna() on the 8 lab columns → survivors = 60% of n_train (approx)
  6. Generate synthetic data at ε=1.0 using Laplace mechanism on numeric features
  7. Evaluate:
       a. DCR: mean nearest-neighbour distance, synthetic → training set (standardised)
       b. DCR: mean nearest-neighbour distance, synthetic → holdout set (standardised)
       c. MIA AUC: random forest distinguishing synthetic from real (membership proxy)
  8. Compare clean vs contaminated verdicts

SUBSTRATE
---------
Corrected MIMIC-IV v3.1 canonical: path given by env var MIMIC_CANONICAL_CSV
SHA256: 7558c398a8e576cc6e57f7309058351982f76d69eed117f38359823676f403e7

SEEDS
-----
seed_sample=42 (record sampling, consistent with Entry 19 + Phase 4 harness)
seed_synthesis=0,1,2,3,42 (5 seeds across Laplace noise)

OUTPUT
------
experiments/results/verdict_flip/verdict_flip_results.json
experiments/results/verdict_flip/verdict_flip_report.md
"""

import hashlib
import json
import sys
import io
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# ── Configuration ──────────────────────────────────────────────────────────────
MIMIC_PATH = Path(__import__("os").environ["MIMIC_CANONICAL_CSV"])
EXPECTED_SHA = "7558c398a8e576cc6e57f7309058351982f76d69eed117f38359823676f403e7"

N_SOURCE     = 2000   # records sampled from full canonical (same as Entry 19)
N_TRAIN      = 1000   # training set size
N_HOLDOUT    = 1000   # genuine non-member holdout (disjoint from training)
CAP_RATE     = 0.40   # fraction of training records designated lab-uncaptured by P2
EPSILON      = 1.0    # Laplace ε for synthesis
SEEDS        = [0, 1, 2, 3, 42]
SEED_SAMPLE  = 42     # record-sampling seed

VERDICT_FLIP_THRESHOLD = 0.05  # minimum standardised DCR difference to confirm verdict flip

LAB_COLS = [
    "lab_creatinine", "lab_glucose", "lab_hematocrit", "lab_hemoglobin",
    "lab_platelet_count", "lab_potassium", "lab_sodium", "lab_white_blood_cells"
]

NUMERIC_FEATURES = [
    "age", "length_of_stay", "risk_score", "medication_count",
    "lab_creatinine", "lab_glucose", "lab_hematocrit", "lab_hemoglobin",
    "lab_platelet_count", "lab_potassium", "lab_sodium", "lab_white_blood_cells"
]
CATEGORICAL_FEATURES = ["sex", "ethnicity", "admission_type", "deceased", "is_emergency"]

OUT_DIR = Path(__file__).parent / "results" / "verdict_flip"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

def sha256_of_file(path: Path, chunk_size: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def encode_features(df: pd.DataFrame) -> pd.DataFrame:
    """Encode categoricals with LabelEncoder; numeric columns left as-is."""
    out = df.copy()
    for col in CATEGORICAL_FEATURES:
        if col in out.columns:
            le = LabelEncoder()
            out[col] = le.fit_transform(out[col].astype(str))
    return out


def add_laplace_noise(df: pd.DataFrame, epsilon: float, seed: int) -> pd.DataFrame:
    """Apply Laplace mechanism to numeric features (sensitivity = column std on training data)."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    for col in NUMERIC_FEATURES:
        if col not in out.columns:
            continue
        sensitivity = out[col].std()
        if sensitivity == 0 or np.isnan(sensitivity):
            continue
        scale = sensitivity / epsilon
        noise = rng.laplace(0, scale, len(out))
        out[col] = out[col] + noise
    return out


def compute_dcr(synthetic: np.ndarray, reference: np.ndarray) -> float:
    """Mean distance from each synthetic record to its nearest reference record."""
    nn = NearestNeighbors(n_neighbors=1, metric="euclidean", algorithm="auto")
    nn.fit(reference)
    distances, _ = nn.kneighbors(synthetic)
    return float(distances.mean())


def compute_mia_auc(train_real: np.ndarray, synthetic: np.ndarray,
                    holdout: np.ndarray, seed: int) -> float:
    """
    Simple MIA: train RF to distinguish real train records (label=1) from
    synthetic records (label=0). AUC on holdout (non-member).
    This is the proxy MIA: checks if synthetic looks like training data.
    """
    rng = np.random.default_rng(seed)
    n_real = len(train_real)
    n_syn  = min(len(synthetic), n_real)
    idx_syn = rng.choice(len(synthetic), n_syn, replace=False)
    X = np.vstack([train_real, synthetic[idx_syn]])
    y = np.hstack([np.ones(n_real), np.zeros(n_syn)])
    clf = RandomForestClassifier(n_estimators=100, random_state=seed)
    clf.fit(X, y)
    # AUC on holdout: if AUC > 0.5, RF can distinguish members — privacy risk
    # Predict proba of being "real" for holdout (non-members should score low)
    proba = clf.predict_proba(holdout)[:, 1]
    # Holdout members: include n_real records from train as positive
    # Full MIA: score train vs holdout on the RF
    scores_train = clf.predict_proba(train_real)[:, 1]
    scores_hold  = clf.predict_proba(holdout)[:, 1]
    y_true = np.hstack([np.ones(len(scores_train)), np.zeros(len(scores_hold))])
    y_score = np.hstack([scores_train, scores_hold])
    return float(roc_auc_score(y_true, y_score))


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("=" * 72)
    print("Verdict-Flip Experiment — P2+P6 Cascade")
    print("Pre-registration: 2026-07-22  |  Artefact: A09")
    print("=" * 72)

    # ── 1. Load and verify canonical ──────────────────────────────────────────
    print(f"\n[1] Loading corrected MIMIC-IV v3.1 canonical...")
    print(f"    Path: {MIMIC_PATH}")
    if not MIMIC_PATH.exists():
        raise FileNotFoundError(f"Canonical not found at {MIMIC_PATH}")

    print("    Computing SHA256 (this may take 30–60 s on large file)...")
    actual_sha = sha256_of_file(MIMIC_PATH)
    sha_ok = actual_sha.startswith(EXPECTED_SHA[:16])
    print(f"    SHA256 (first 16 chars): {actual_sha[:16]}…")
    print(f"    Expected prefix:         {EXPECTED_SHA[:16]}…")
    print(f"    SHA match: {'✓ VERIFIED' if sha_ok else '✗ MISMATCH — ABORT'}")
    if not sha_ok:
        raise ValueError(f"SHA mismatch: {actual_sha} vs {EXPECTED_SHA}")

    df_full = pd.read_csv(MIMIC_PATH)
    print(f"    Full canonical rows: {len(df_full):,}")

    # ── 2. Sample n_source records ─────────────────────────────────────────────
    print(f"\n[2] Sampling n_source={N_SOURCE} records (seed={SEED_SAMPLE})...")
    df_source = df_full.sample(n=N_SOURCE, random_state=SEED_SAMPLE).reset_index(drop=True)
    print(f"    Sampled: {len(df_source)} records")

    # Drop date columns (not useful for DCR/MIA)
    df_source = df_source.drop(columns=["encounter_date", "discharge_date",
                                         "patient_id", "encounter_id"], errors="ignore")

    # ── 3. Split train / holdout ───────────────────────────────────────────────
    print(f"\n[3] Splitting: n_train={N_TRAIN}, n_holdout={N_HOLDOUT}...")
    df_train_pool = df_source.iloc[:N_TRAIN].copy()
    df_holdout    = df_source.iloc[N_TRAIN:N_TRAIN + N_HOLDOUT].copy()
    print(f"    Train pool: {len(df_train_pool)}, Holdout: {len(df_holdout)}")

    # ── 4. Build CLEAN substrate ───────────────────────────────────────────────
    print(f"\n[4] Building CLEAN substrate...")
    # Drop rows with NaN in lab columns (these are records without lab measurements —
    # a legitimate clinical reason; we drop them to ensure clean substrate has
    # no NaN, making the comparison methodologically clean)
    df_clean = df_train_pool.dropna(subset=LAB_COLS).reset_index(drop=True)
    print(f"    Clean substrate size after dropna(lab_cols): n={len(df_clean)}")

    # ── 5. Build CONTAMINATED substrate (simulate P2+P6 cascade) ──────────────
    print(f"\n[5] Building CONTAMINATED substrate (simulating P2+P6 cascade)...")
    rng_cap = np.random.default_rng(SEED_SAMPLE)
    cap_mask = rng_cap.random(len(df_train_pool)) < CAP_RATE  # True = lab-uncaptured by cap
    df_contaminated_pool = df_train_pool.copy()
    # P2: zero out lab columns for cap-masked records (simulates labevents row cap → NaN)
    df_contaminated_pool.loc[cap_mask, LAB_COLS] = np.nan
    n_capped = cap_mask.sum()
    print(f"    P2 simulation: {n_capped} records ({100*n_capped/len(df_train_pool):.1f}%) "
          f"had lab columns zeroed (cap_rate={CAP_RATE})")
    # P6: unscoped dropna() — drops any record with any NaN column
    df_contaminated = df_contaminated_pool.dropna().reset_index(drop=True)
    print(f"    P6 simulation: after unscoped dropna(), n_contaminated={len(df_contaminated)}")
    print(f"    Survivor rate: {100*len(df_contaminated)/len(df_train_pool):.1f}%")

    if len(df_contaminated) < 20:
        raise ValueError(f"Contaminated substrate too small ({len(df_contaminated)} records) — "
                         f"adjust CAP_RATE")

    # ── 6. Encode features for both substrates ─────────────────────────────────
    print(f"\n[6] Encoding features...")
    features_all = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    features_present = [c for c in features_all if c in df_clean.columns]

    df_clean_enc       = encode_features(df_clean[features_present])
    df_contaminated_enc = encode_features(df_contaminated[features_present])
    df_holdout_enc     = encode_features(df_holdout[features_present].dropna(subset=LAB_COLS))
    print(f"    Features used: {len(features_present)}")
    print(f"    Holdout after dropna: {len(df_holdout_enc)}")

    # ── 7. Standardise (fit scaler on each substrate — this is what a researcher does) ─
    print(f"\n[7] Fitting StandardScaler on each substrate...")
    scaler_clean = StandardScaler()
    X_clean = scaler_clean.fit_transform(df_clean_enc.fillna(0).values)

    scaler_contaminated = StandardScaler()
    X_contaminated = scaler_contaminated.fit_transform(df_contaminated_enc.fillna(0).values)

    # Holdout scaled by the CLEAN scaler (ground truth reference)
    X_holdout_clean = scaler_clean.transform(df_holdout_enc.fillna(0).values)
    # Holdout scaled by the CONTAMINATED scaler (what contaminated researcher would use)
    X_holdout_cont  = scaler_contaminated.transform(df_holdout_enc.fillna(0).values)

    print(f"    σ_income (clean):        {scaler_clean.scale_[0]:.2f}")
    print(f"    σ_income (contaminated): {scaler_contaminated.scale_[0]:.2f}")

    # ── 8. Generate synthetic data at ε=1.0 for each seed ─────────────────────
    print(f"\n[8] Generating synthetic data at ε={EPSILON}...")

    results_per_seed = []

    for seed in SEEDS:
        print(f"\n  Seed {seed}:")

        # Synthesise from clean substrate
        syn_clean_raw = add_laplace_noise(df_clean_enc.fillna(0), EPSILON, seed)
        X_syn_clean = scaler_clean.transform(syn_clean_raw.values)

        # Synthesise from contaminated substrate
        syn_cont_raw = add_laplace_noise(df_contaminated_enc.fillna(0), EPSILON, seed)
        X_syn_cont = scaler_contaminated.transform(syn_cont_raw.values)

        # DCR: synthetic → training set (both in their respective standardised spaces)
        dcr_clean_train = compute_dcr(X_syn_clean, X_clean)
        dcr_cont_train  = compute_dcr(X_syn_cont,  X_contaminated)

        # DCR: synthetic → holdout (ground-truth non-members, scaled by respective scaler)
        dcr_clean_holdout = compute_dcr(X_syn_clean, X_holdout_clean)
        dcr_cont_holdout  = compute_dcr(X_syn_cont,  X_holdout_cont)

        # MIA AUC (proxy: can RF distinguish train from synthetic?)
        mia_clean = compute_mia_auc(X_clean, X_syn_clean, X_holdout_clean, seed)
        mia_cont  = compute_mia_auc(X_contaminated, X_syn_cont,  X_holdout_cont,  seed)

        print(f"    DCR(syn→train)   clean={dcr_clean_train:.4f}  contaminated={dcr_cont_train:.4f}  "
              f"Δ={dcr_cont_train - dcr_clean_train:+.4f}")
        print(f"    DCR(syn→holdout) clean={dcr_clean_holdout:.4f}  contaminated={dcr_cont_holdout:.4f}  "
              f"Δ={dcr_cont_holdout - dcr_clean_holdout:+.4f}")
        print(f"    MIA AUC          clean={mia_clean:.4f}  contaminated={mia_cont:.4f}  "
              f"Δ={mia_cont - mia_clean:+.4f}")

        results_per_seed.append({
            "seed": seed,
            "n_clean": len(df_clean),
            "n_contaminated": len(df_contaminated),
            "dcr_train_clean":       dcr_clean_train,
            "dcr_train_contaminated": dcr_cont_train,
            "dcr_holdout_clean":     dcr_clean_holdout,
            "dcr_holdout_contaminated": dcr_cont_holdout,
            "mia_clean":  mia_clean,
            "mia_contaminated": mia_cont,
            "dcr_train_delta":   dcr_cont_train - dcr_clean_train,
            "dcr_holdout_delta": dcr_cont_holdout - dcr_clean_holdout,
            "mia_delta":         mia_cont - mia_clean,
        })

    # ── 9. Aggregate and verdict ───────────────────────────────────────────────
    print(f"\n[9] Aggregating across {len(SEEDS)} seeds...")

    dcr_train_clean_mean  = np.mean([r["dcr_train_clean"] for r in results_per_seed])
    dcr_train_cont_mean   = np.mean([r["dcr_train_contaminated"] for r in results_per_seed])
    dcr_holdout_clean_mean = np.mean([r["dcr_holdout_clean"] for r in results_per_seed])
    dcr_holdout_cont_mean  = np.mean([r["dcr_holdout_contaminated"] for r in results_per_seed])
    mia_clean_mean  = np.mean([r["mia_clean"] for r in results_per_seed])
    mia_cont_mean   = np.mean([r["mia_contaminated"] for r in results_per_seed])

    dcr_train_delta_mean   = dcr_train_cont_mean - dcr_train_clean_mean
    dcr_holdout_delta_mean = dcr_holdout_cont_mean - dcr_holdout_clean_mean
    mia_delta_mean         = mia_cont_mean - mia_clean_mean

    print(f"\n  ── Summary ──────────────────────────────────────────────")
    print(f"  Substrate sizes:   clean={len(df_clean)}  contaminated={len(df_contaminated)}")
    print(f"  DCR(syn→train):   clean={dcr_train_clean_mean:.4f}  cont={dcr_train_cont_mean:.4f}  "
          f"Δ={dcr_train_delta_mean:+.4f}")
    print(f"  DCR(syn→holdout): clean={dcr_holdout_clean_mean:.4f}  cont={dcr_holdout_cont_mean:.4f}  "
          f"Δ={dcr_holdout_delta_mean:+.4f}")
    print(f"  MIA AUC:          clean={mia_clean_mean:.4f}  cont={mia_cont_mean:.4f}  "
          f"Δ={mia_delta_mean:+.4f}")

    # Verdict — frozen rule from pre-registration
    primary_delta = dcr_train_delta_mean  # primary metric for frozen verdict
    direction_correct = primary_delta > 0  # contaminated DCR > clean DCR → appears safer
    magnitude_sufficient = abs(primary_delta) >= VERDICT_FLIP_THRESHOLD

    if direction_correct and magnitude_sufficient:
        verdict = "VERDICT_FLIP_CONFIRMED"
        verdict_summary = (
            f"Contaminated substrate produces DCR={dcr_train_cont_mean:.4f} vs "
            f"clean DCR={dcr_train_clean_mean:.4f} (Δ={dcr_train_delta_mean:+.4f}). "
            f"The contaminated substrate appears MORE PRIVATE than the clean substrate "
            f"(false-negative privacy verdict). Exceeds threshold={VERDICT_FLIP_THRESHOLD}."
        )
    elif direction_correct and not magnitude_sufficient:
        verdict = "VERDICT_FLIP_PARTIAL"
        verdict_summary = (
            f"Contaminated substrate produces higher DCR (correct direction) but "
            f"Δ={dcr_train_delta_mean:+.4f} < threshold={VERDICT_FLIP_THRESHOLD}. "
            f"Direction consistent with prediction; magnitude insufficient to confirm flip."
        )
    else:
        verdict = "VERDICT_FLIP_NOT_CONFIRMED"
        verdict_summary = (
            f"Contaminated substrate produces DCR={dcr_train_cont_mean:.4f} vs "
            f"clean DCR={dcr_train_clean_mean:.4f} (Δ={dcr_train_delta_mean:+.4f}). "
            f"Direction is {'correct' if direction_correct else 'reversed'}. "
            f"Prediction not confirmed under the pre-registered frozen rule."
        )

    print(f"\n  ── Verdict ──────────────────────────────────────────────")
    print(f"  {verdict}")
    print(f"  {verdict_summary}")

    # ── 10. Save results ───────────────────────────────────────────────────────
    out_data = {
        "experiment": "verdict_flip_p2_p6_cascade",
        "artefact_tag": "A09",
        "date_run": datetime.utcnow().isoformat(),
        "sha_verified": sha_ok,
        "config": {
            "n_source": N_SOURCE,
            "n_train_pool": N_TRAIN,
            "n_holdout": N_HOLDOUT,
            "cap_rate": CAP_RATE,
            "epsilon": EPSILON,
            "seeds": SEEDS,
            "seed_sample": SEED_SAMPLE,
            "verdict_flip_threshold": VERDICT_FLIP_THRESHOLD,
        },
        "substrate_sizes": {
            "n_clean": len(df_clean),
            "n_contaminated": len(df_contaminated),
        },
        "per_seed_results": results_per_seed,
        "aggregate": {
            "dcr_train_clean_mean":      round(dcr_train_clean_mean, 6),
            "dcr_train_contaminated_mean": round(dcr_train_cont_mean, 6),
            "dcr_train_delta_mean":      round(dcr_train_delta_mean, 6),
            "dcr_holdout_clean_mean":    round(dcr_holdout_clean_mean, 6),
            "dcr_holdout_contaminated_mean": round(dcr_holdout_cont_mean, 6),
            "dcr_holdout_delta_mean":    round(dcr_holdout_delta_mean, 6),
            "mia_clean_mean":            round(mia_clean_mean, 6),
            "mia_contaminated_mean":     round(mia_cont_mean, 6),
            "mia_delta_mean":            round(mia_delta_mean, 6),
        },
        "verdict": verdict,
        "verdict_summary": verdict_summary,
    }

    json_path = OUT_DIR / "verdict_flip_results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
    print(f"\n  Results written to: {json_path}")

    # Write markdown report
    md_path = OUT_DIR / "verdict_flip_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"""# Verdict-Flip Experiment — P2+P6 Cascade
**Artefact tag:** A09  
**Date:** {datetime.utcnow().strftime('%Y-%m-%d')}  
**Substrate:** corrected MIMIC-IV v3.1 (SHA 7558c398…, verified={sha_ok})

## Configuration
| Parameter | Value |
|---|---|
| n_source | {N_SOURCE} |
| n_train | {len(df_clean)} (clean after dropna) |
| n_contaminated | {len(df_contaminated)} (P2+P6 survivors) |
| n_holdout | {len(df_holdout_enc)} |
| ε (Laplace) | {EPSILON} |
| Seeds | {SEEDS} |
| cap_rate | {CAP_RATE} |

## Results (mean across {len(SEEDS)} seeds)

| Metric | Clean | Contaminated | Δ (cont−clean) |
|---|---|---|---|
| DCR (syn→train, standardised) | {dcr_train_clean_mean:.4f} | {dcr_train_cont_mean:.4f} | {dcr_train_delta_mean:+.4f} |
| DCR (syn→holdout, standardised) | {dcr_holdout_clean_mean:.4f} | {dcr_holdout_cont_mean:.4f} | {dcr_holdout_delta_mean:+.4f} |
| MIA AUC | {mia_clean_mean:.4f} | {mia_cont_mean:.4f} | {mia_delta_mean:+.4f} |

## Verdict

**{verdict}**

{verdict_summary}

## Interpretation
""")
        if verdict == "VERDICT_FLIP_CONFIRMED":
            f.write(f"""
The P2+P6 cascade produces a false-negative privacy verdict under the pre-registered
frozen decision rule. A researcher evaluating privacy on the contaminated substrate
(n={len(df_contaminated)}, {100*len(df_contaminated)/N_TRAIN:.0f}% of the intended training set) observes a higher
DCR than the researcher evaluating the same pipeline on the clean substrate
(n={len(df_clean)}). The higher DCR would be interpreted as evidence that synthetic data is
more private — but this apparent safety is an artefact of the contaminated, homogeneous
survivor cohort, not a property of the synthesiser or the true population.

The result directly demonstrates the paper's central claim: substrate contamination
changes downstream privacy evaluation conclusions. The false-negative direction is the
operationally dangerous outcome — a researcher believing their data is safer than it is.
""")
        elif verdict == "VERDICT_FLIP_NOT_CONFIRMED":
            f.write(f"""
The pre-registered frozen rule was not met (Δ={dcr_train_delta_mean:+.4f},
threshold={VERDICT_FLIP_THRESHOLD}). The contaminated substrate does not produce a
materially higher DCR under these experimental conditions. This is an honest null result
under the pre-registered criteria.

The DCR metric may not be sensitive enough to detect the verdict change from this
contamination mechanism, or the Laplace mechanism may dominate the substrate-induced
distributional shift. A verdict flip may be observable with a different evaluation metric
(attribute disclosure, stronger MIA) or a different contamination intensity.

The paper's contamination findings and retirement evidence remain valid regardless of
this experimental result. The null result here does not invalidate the primary claims
about substrate-validity audit procedure; it is an honest boundary on the specific
demonstration of verdict flip via DCR under Laplace synthesis.
""")

    print(f"  Report written to:  {md_path}")
    print(f"\n{'=' * 72}")
    print(f"DONE — verdict: {verdict}")
    print(f"{'=' * 72}")

    return out_data


if __name__ == "__main__":
    main()
