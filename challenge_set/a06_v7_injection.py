"""
V7 — Out-of-Taxonomy Injection: Categorical Code Collapse
Part B Investigation — Silent Failures in Preprocessing

PURPOSE
-------
Test whether the two-component P1–P9 audit procedure detects a contamination class
that is genuinely outside the nine-pattern taxonomy. V7 injects a categorical code
collapse: icd_code='250.00' (diabetes mellitus) is silently remapped to '410.00'
(acute myocardial infarction) for a proportion of records. This simulates a
preprocessing mapping-table error where two semantically distinct diagnosis
categories are assigned the same output code.

ORTHOGONALITY ARGUMENT (why V7 is outside P1–P9)
-------------------------------------------------
P1  — Unsorted groupby: no groupby operation, no row-ordering dependency.
P2  — Row caps: no nrows= or .head(N) constraint; all records retained.
P3  — Dead merges: no merge result variable; no join operation performed.
P4  — Formula bugs: no arithmetic formula, no type mismatch; icd_code remains
      a valid string column containing valid ICD codes; no numeric range violation.
P5  — Silent exclusion: no NaN is produced; the collapsed code '410.00' is a
      valid ICD string; pd.cut / .map / .isin NaN production does not occur.
P6  — Unscoped dropna: no NaN introduced, so dropna() drops zero rows.
P7  — Output file protection: no write-call guard or path issue.
P8  — Documentation drift: no comment injected asserting handled behaviour.
P9  — Cross-domain parameter inheritance: no constant copied cross-domain.

The contamination type is a CODE MAPPING ERROR: a many-to-one mapping applied
to a categorical column that produces internally-consistent but semantically
corrupted output. The resulting column is fully populated with valid, non-null
ICD codes; no numeric column is affected; no record is dropped.

DETECTION PREDICTION (before running)
--------------------------------------
Two-component procedure expected to MISS V7 because:
  Static code inspection: P1–P9 signatures scan for sort-before-groupby,
    nrows literals, dead merge variables, numeric range violations, NaN-producing
    maps, unscoped dropna, missing write guards, remediation-keyword comments,
    cross-domain constants. None of these signatures apply to a categorical
    mapping operation that produces valid output strings.
  Substrate verification: range plausibility checks scan numeric columns only;
    NaN-rate profiles show zero NaN (column fully populated);
    Tukey outlier_frac applies to numeric columns only;
    rank/σ empirical check is specific to numeric columns.
  Neither component has a check for categorical distribution shift.

EXPECTED OUTCOME: B-MISSED — the procedure produces a clean report on V7.
This is a reportable honest boundary: it empirically demonstrates the procedure's
scope limit for categorical mapping errors, supporting §3.1's existing "not a
closed taxonomy" statement with evidence rather than assertion.

Seed:    42  (same as V1–V6 harness, for within-harness comparability)
Dataset: synthetic MIMIC-like canonical, n=1,998 records, 9 columns
         generated identically to phase4_controlled_injection.py

Run:  python v7_out_of_taxonomy_injection.py
Output: v7_results.json (same directory)

Date:   2026-06-15
"""

import json
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import LocalOutlierFactor

warnings.filterwarnings("ignore")

RANDOM = 42
N_ROWS = 2000
COLLAPSE_FRACTION = 0.30   # 30% of '250.00' records remapped to '410.00'

OUT_DIR  = Path(__file__).parent
OUT_FILE = OUT_DIR / "v7_results.json"


# ──────────────────────────────────────────────────────────────────────────────
# 1. CLEAN CANONICAL — identical to phase4_controlled_injection.py
# ──────────────────────────────────────────────────────────────────────────────

def make_clean_canonical(n: int = N_ROWS, seed: int = RANDOM) -> pd.DataFrame:
    """Generate the same MIMIC-like synthetic canonical used in V1–V6."""
    rng = np.random.default_rng(seed)

    n_subjects = n // 3
    n = n_subjects * 3
    subject_ids = np.repeat(np.arange(1, n_subjects + 1), 3)
    hadm_ids    = np.arange(1, n + 1)
    seq_nums    = np.tile([1, 2, 3], n_subjects)

    ages             = rng.integers(18, 107, size=n).astype(float)
    length_of_stay   = rng.gamma(shape=2, scale=4, size=n).clip(0, 90)
    diagnosis_count  = rng.integers(1, 26, size=n).astype(float)
    medication_count = rng.integers(0, 51, size=n).astype(float)
    total_charges    = rng.lognormal(mean=10, sigma=1.2, size=n).clip(100, 200_000)
    icd_codes = rng.choice(
        ['410.00', '250.00', '428.0', '427.31', '486', '038.9', '414.01', '401.9'],
        size=n
    )

    df = pd.DataFrame({
        'subject_id':       subject_ids,
        'hadm_id':          hadm_ids,
        'seq_num':          seq_nums,
        'age':              ages,
        'length_of_stay':   np.round(length_of_stay, 1),
        'diagnosis_count':  diagnosis_count,
        'medication_count': medication_count,
        'total_charges':    np.round(total_charges, 2),
        'icd_code':         icd_codes,
    })

    df = df.sort_values(['subject_id', 'hadm_id', 'seq_num']).reset_index(drop=True)
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 2. V7 INJECTION — categorical code collapse
# ──────────────────────────────────────────────────────────────────────────────

def inject_v7_categorical_collapse(df: pd.DataFrame, rng,
                                   fraction: float = COLLAPSE_FRACTION) -> pd.DataFrame:
    """
    V7 — Categorical collapse (out-of-taxonomy).

    Silently remap icd_code='250.00' (diabetes mellitus) → '410.00'
    (acute myocardial infarction) for a randomly-selected fraction of records.

    Effect in canonical:
      - icd_code column remains fully populated (zero NaN)
      - All values are valid ICD codes (no out-of-range strings)
      - The count of '250.00' decreases; the count of '410.00' increases
      - No numeric column is modified
      - No record is dropped

    No other column is affected.
    """
    df = df.copy()
    diabetes_idx = df.index[df['icd_code'] == '250.00'].tolist()
    n_to_collapse = int(len(diabetes_idx) * fraction)
    if n_to_collapse == 0:
        return df  # nothing to collapse at this fraction
    collapse_idx = rng.choice(diabetes_idx, size=n_to_collapse, replace=False)
    df.loc[collapse_idx, 'icd_code'] = '410.00'
    return df


# ──────────────────────────────────────────────────────────────────────────────
# 3. AUDIT PROCEDURE — identical component signatures to V1–V6
# ──────────────────────────────────────────────────────────────────────────────

def detect_p1(df: pd.DataFrame) -> dict:
    has_p1_column = 'primary_icd' in df.columns and 'primary_icd_mismatch' in df.columns
    mismatch_rate = float(df['primary_icd_mismatch'].mean()) if has_p1_column else 0.0
    detected = has_p1_column and mismatch_rate > 0.01
    return {
        'pattern': 'P1', 'detected': detected,
        'evidence': f'primary_icd_mismatch_rate={mismatch_rate:.3f}'
                    if has_p1_column else 'no_groupby_derived_cols',
        'severity': 'CRITICAL' if (detected and mismatch_rate > 0.1)
                    else ('HIGH' if detected else 'NONE'),
    }


def detect_p2(df: pd.DataFrame) -> dict:
    nan_counts  = df.isnull().sum()
    suspicious  = nan_counts[nan_counts > 0]
    detected    = len(suspicious) > 0
    first_col   = suspicious.index[0] if detected else None
    nan_frac    = float(suspicious.iloc[0] / len(df)) if detected else 0.0
    return {
        'pattern': 'P2', 'detected': detected,
        'evidence': f'{first_col}: {nan_frac:.1%} NaN' if detected else 'no_unexpected_NaN',
        'severity': 'CRITICAL' if nan_frac > 0.2 else
                    ('HIGH' if nan_frac > 0.05 else ('MEDIUM' if detected else 'NONE')),
    }


def detect_p3(df: pd.DataFrame) -> dict:
    analysis_cols = {'age', 'length_of_stay', 'diagnosis_count', 'medication_count',
                     'total_charges', 'icd_code'}
    id_cols       = {'subject_id', 'hadm_id', 'seq_num'}
    dead_cols = [c for c in df.columns
                 if c not in analysis_cols and c not in id_cols
                 and 'mismatch' not in c and 'primary_icd' not in c
                 and 'correct' not in c]
    detected = len(dead_cols) > 0
    return {
        'pattern': 'P3', 'detected': detected,
        'evidence': f'dead_columns={dead_cols}' if detected else 'no_dead_columns',
        'severity': 'MEDIUM' if detected else 'NONE',
    }


def detect_p4(df: pd.DataFrame) -> dict:
    findings = []
    if 'age' in df.columns:
        age_min, age_max = df['age'].min(), df['age'].max()
        if age_max > 150 or age_min < 0:
            findings.append(f'age range [{age_min:.0f}, {age_max:.0f}] implausible')
    if 'length_of_stay' in df.columns:
        los_max = df['length_of_stay'].max()
        if los_max > 365:
            findings.append(f'length_of_stay max={los_max:.0f} implausible')
    if 'total_charges' in df.columns:
        sentinel_count = (df['total_charges'] >= 9_000_000).sum()
        if sentinel_count > 0:
            sentinel_frac = sentinel_count / len(df)
            findings.append(f'total_charges sentinel (>=9M): {sentinel_count} rows ({sentinel_frac:.1%})')
    detected = len(findings) > 0
    return {
        'pattern': 'P4', 'detected': detected,
        'evidence': '; '.join(findings) if findings else 'all_ranges_plausible',
        'severity': 'CRITICAL' if any('sentinel' in f or 'age' in f for f in findings)
                    else ('HIGH' if detected else 'NONE'),
    }


def detect_p4_invariance(df: pd.DataFrame) -> dict:
    """Tukey outlier fraction + StandardScaler std for numeric contamination columns."""
    results = {}
    for col in ['age', 'total_charges']:
        if col not in df.columns:
            continue
        vals = df[col].dropna().values
        scaler = StandardScaler()
        scaler.fit_transform(vals.reshape(-1, 1))

        mean_ = float(scaler.mean_[0])
        std_  = float(scaler.scale_[0])

        q1_ = float(np.percentile(vals, 25))
        q3_ = float(np.percentile(vals, 75))
        iqr_ = q3_ - q1_
        upper_fence = q3_ + 3.0 * iqr_ if iqr_ > 0 else q3_ * 10
        lower_fence = q1_ - 3.0 * iqr_ if iqr_ > 0 else 0.0

        outlier_frac = float(np.mean((vals > upper_fence) | (vals < lower_fence)))
        invariance_broken = outlier_frac > 0.01

        results[col] = {
            'mean': round(mean_, 2),
            'std': round(std_, 2),
            'iqr': round(iqr_, 2),
            'upper_tukey_fence': round(upper_fence, 2),
            'outlier_fraction': round(outlier_frac, 4),
            'invariance_broken': invariance_broken,
        }
    return results


def detect_p5(df: pd.DataFrame) -> dict:
    if 'age' not in df.columns:
        return {'pattern': 'P5', 'detected': False, 'evidence': 'age column missing',
                'severity': 'NONE'}
    age_bins  = pd.cut(df['age'], bins=[0, 18, 30, 45, 60, 75, 120])
    nan_count = int(age_bins.isna().sum())
    nan_frac  = nan_count / len(df)
    detected  = nan_count > 0
    return {
        'pattern': 'P5', 'detected': detected,
        'evidence': f'age_bin NaN: {nan_count} rows ({nan_frac:.1%})',
        'severity': 'HIGH' if nan_frac > 0.05 else ('MEDIUM' if detected else 'NONE'),
    }


def detect_p6(df: pd.DataFrame) -> dict:
    n_before = len(df)
    n_after  = len(df.dropna())
    n_dropped = n_before - n_after
    drop_frac = n_dropped / n_before
    detected  = n_dropped > 0
    return {
        'pattern': 'P6', 'detected': detected,
        'evidence': f'dropna would remove {n_dropped} rows ({drop_frac:.1%})',
        'severity': 'CRITICAL' if drop_frac > 0.1 else
                    ('HIGH' if drop_frac > 0.02 else ('MEDIUM' if detected else 'NONE')),
    }


def detect_p7(out_path: Path) -> dict:
    overwrite_risk = out_path.exists()
    return {
        'pattern': 'P7', 'detected': overwrite_risk,
        'evidence': f'output path {out_path} exists — overwrite risk'
                    if overwrite_risk else 'output path clear',
        'severity': 'MEDIUM' if overwrite_risk else 'NONE',
    }


def detect_p8(comments: list) -> dict:
    drift_keywords = ['already handled', 'cleaned', 'validated', 'fixed', 'corrected']
    drifted  = [c for c in comments if any(kw in c.lower() for kw in drift_keywords)]
    detected = len(drifted) > 0
    return {
        'pattern': 'P8', 'detected': detected,
        'evidence': f'drifted_comments={drifted}' if detected else 'no_drift_comments',
        'severity': 'HIGH' if detected else 'NONE',
    }


def detect_p9(constants: dict) -> dict:
    inheritance_keywords = ['from insurance', 'from health', 'from mimic', 'same as',
                            'proven size', 'worked for']
    inherited = [(k, v) for k, v in constants.items()
                 if isinstance(v, str) and any(kw in v.lower() for kw in inheritance_keywords)]
    detected = len(inherited) > 0
    return {
        'pattern': 'P9', 'detected': detected,
        'evidence': f'inherited_constants={inherited}' if detected else
                    'no_cross_domain_inheritance',
        'severity': 'MEDIUM' if detected else 'NONE',
    }


# ──────────────────────────────────────────────────────────────────────────────
# 4. ADDITIONAL SUBSTRATE CHECKS — beyond V1–V6 harness
#    These are applied to V7 to probe whether any check catches the collapse.
# ──────────────────────────────────────────────────────────────────────────────

def substrate_categorical_distribution(clean_df: pd.DataFrame,
                                       v7_df: pd.DataFrame) -> dict:
    """
    Compare icd_code value counts between clean and V7 canonical.
    This check is NOT part of the P1–P9 procedure — it is an additional
    probe to confirm the injection is present and to quantify its effect.
    It is labelled EXTRA (outside procedure scope).
    """
    clean_vc = clean_df['icd_code'].value_counts()
    v7_vc    = v7_df['icd_code'].value_counts()
    all_codes = clean_vc.index.union(v7_vc.index)
    diff = {
        code: {
            'clean_count': int(clean_vc.get(code, 0)),
            'v7_count':    int(v7_vc.get(code, 0)),
            'delta':       int(v7_vc.get(code, 0)) - int(clean_vc.get(code, 0)),
        }
        for code in all_codes
        if clean_vc.get(code, 0) != v7_vc.get(code, 0)
    }
    return {
        'check': 'categorical_distribution_comparison',
        'scope': 'EXTRA — not part of P1–P9 procedure',
        'detected_by_extra_check': len(diff) > 0,
        'changed_codes': diff,
    }


def substrate_nan_profile(df: pd.DataFrame) -> dict:
    """Full NaN profile — part of substrate verification."""
    return {
        'check': 'nan_profile',
        'per_column': {col: int(df[col].isna().sum()) for col in df.columns},
        'total_nan': int(df.isna().sum().sum()),
    }


def substrate_numeric_range(df: pd.DataFrame) -> dict:
    """Domain range plausibility for all numeric columns."""
    checks = {}
    bounds = {
        'age': (0, 200), 'length_of_stay': (0, 365),
        'diagnosis_count': (0, 100), 'medication_count': (0, 200),
        'total_charges': (0, 10_000_000),
    }
    for col, (lo, hi) in bounds.items():
        if col not in df.columns:
            continue
        out_of_range = int(((df[col] < lo) | (df[col] > hi)).sum())
        checks[col] = {
            'min': float(df[col].min()), 'max': float(df[col].max()),
            'out_of_range_count': out_of_range,
            'plausible': out_of_range == 0,
        }
    return {'check': 'range_plausibility', 'columns': checks}


# ──────────────────────────────────────────────────────────────────────────────
# 5. MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("V7 — Out-of-Taxonomy Injection: Categorical Code Collapse")
    print("Part B Investigation — Silent Failures in Preprocessing")
    print("=" * 70)

    rng   = np.random.default_rng(RANDOM)
    clean = make_clean_canonical(N_ROWS, RANDOM)

    # ── Inject V7 ────────────────────────────────────────────────────────────
    v7_df = inject_v7_categorical_collapse(clean, rng, COLLAPSE_FRACTION)

    n_250_clean = int((clean['icd_code'] == '250.00').sum())
    n_250_v7    = int((v7_df['icd_code'] == '250.00').sum())
    n_410_clean = int((clean['icd_code'] == '410.00').sum())
    n_410_v7    = int((v7_df['icd_code'] == '410.00').sum())
    n_collapsed = n_250_clean - n_250_v7

    print(f"\n[Injection] '250.00' records: {n_250_clean} -> {n_250_v7}")
    print(f"[Injection] '410.00' records: {n_410_clean} -> {n_410_v7}")
    print(f"[Injection] Records remapped: {n_collapsed} ({n_collapsed/len(v7_df):.1%} of canonical)")

    # ── P1–P9 procedure (identical to V1–V6 harness) ─────────────────────────
    print("\n--- Running full two-component P1–P9 audit procedure on V7 ---")

    out_path   = OUT_DIR / "dummy_canonical.csv"   # simulate existence check
    comments   = []   # no injected comments (V7 is a pure data-level error)
    constants  = {}   # no injected constants

    p1 = detect_p1(v7_df)
    p2 = detect_p2(v7_df)
    p3 = detect_p3(v7_df)
    p4 = detect_p4(v7_df)
    p4_inv = detect_p4_invariance(v7_df)
    p5 = detect_p5(v7_df)
    p6 = detect_p6(v7_df)
    p7 = detect_p7(out_path)
    p8 = detect_p8(comments)
    p9 = detect_p9(constants)

    all_detections = [p1, p2, p3, p4, p5, p6, p7, p8, p9]
    detected_patterns = [d['pattern'] for d in all_detections if d['detected']]

    for det in all_detections:
        flag = "DETECTED" if det['detected'] else "clean"
        print(f"  {det['pattern']}: {flag} | evidence: {det['evidence']}")

    # ── Additional substrate checks ──────────────────────────────────────────
    cat_dist  = substrate_categorical_distribution(clean, v7_df)
    nan_prof  = substrate_nan_profile(v7_df)
    rng_check = substrate_numeric_range(v7_df)

    print(f"\n[Extra check] Categorical distribution shift detected: "
          f"{cat_dist['detected_by_extra_check']}")
    if cat_dist['detected_by_extra_check']:
        for code, delta in cat_dist['changed_codes'].items():
            print(f"  '{code}': {delta['clean_count']} -> {delta['v7_count']} "
                  f"(delta={delta['delta']:+d})")

    # ── Outcome classification ────────────────────────────────────────────────
    v7_detected_by_procedure = len(detected_patterns) > 0

    print("\n" + "=" * 70)
    print("OUTCOME CLASSIFICATION")
    print("=" * 70)
    if v7_detected_by_procedure:
        outcome = "B-DETECTED"
        print(f"  B-DETECTED — procedure flagged: {detected_patterns}")
    else:
        outcome = "B-MISSED"
        print(f"  B-MISSED — full P1–P9 inspection returned CLEAN on V7")
        print(f"  The categorical code collapse is invisible to both")
        print(f"  static code inspection and substrate verification.")
        print(f"  This is an honest boundary: the procedure has no coverage")
        print(f"  for categorical mapping errors producing valid output strings.")

    print()
    print(f"  P7 status: {p7['evidence']}")
    print(f"  (P7 fires if dummy_canonical.csv already exists — pipeline-level,")
    print(f"   not related to V7 contamination.)")

    # ── Save results ─────────────────────────────────────────────────────────
    output = {
        "script":        "v7_out_of_taxonomy_injection.py",
        "timestamp":     datetime.utcnow().isoformat(),
        "seed":          RANDOM,
        "n_rows":        len(v7_df),
        "contamination": {
            "type":        "categorical_code_collapse",
            "description": "icd_code='250.00' (diabetes mellitus) → '410.00' "
                           "(acute MI) for {:.0%} of affected records".format(COLLAPSE_FRACTION),
            "collapse_fraction": COLLAPSE_FRACTION,
            "records_remapped":  n_collapsed,
            "pct_of_canonical":  round(n_collapsed / len(v7_df), 4),
            "source_code_before": "250.00",
            "source_code_after":  "410.00",
        },
        "orthogonality": {
            "P1": "no groupby, no row-order dependency",
            "P2": "no nrows cap, all records retained",
            "P3": "no dead merge, no join operation",
            "P4": "no arithmetic formula, no type mismatch, no numeric range violation",
            "P5": "no NaN produced; collapsed code is a valid ICD string",
            "P6": "no NaN introduced, dropna() drops zero rows",
            "P7": "no write-call guard issue introduced by injection",
            "P8": "no remediation comment injected",
            "P9": "no cross-domain constant injected",
        },
        "procedure_results": {d['pattern']: d for d in all_detections},
        "p4_invariance": p4_inv,
        "detected_patterns": detected_patterns,
        "outcome": outcome,
        "procedure_detected_v7": v7_detected_by_procedure,
        "extra_checks": {
            "categorical_distribution": cat_dist,
            "nan_profile": nan_prof,
            "range_plausibility": rng_check,
        },
        "injection_stats": {
            "icd_250_before": n_250_clean,
            "icd_250_after":  n_250_v7,
            "icd_410_before": n_410_clean,
            "icd_410_after":  n_410_v7,
            "records_collapsed": n_collapsed,
        },
        "note": (
            "B-MISSED is the correctly expected outcome and is a usable finding. "
            "It empirically demonstrates the P1–P9 procedure's coverage boundary: "
            "categorical mapping errors that produce valid, non-null output strings "
            "are invisible to both static code inspection (which scans for numeric "
            "formula errors, NaN-producing maps, and code-level signatures) and "
            "substrate verification (which checks numeric ranges, NaN rates, and "
            "Tukey outlier fractions on numeric columns). This confirms §3.1's "
            "'not a closed taxonomy' claim with direct evidence."
        ),
    }

    OUT_FILE.write_text(json.dumps(output, indent=2, default=str))
    print(f"\n  Results saved: {OUT_FILE.name}")
    print("=" * 70)

    return output


if __name__ == "__main__":
    main()
