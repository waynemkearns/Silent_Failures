"""KDE-ratio (own implementation): an unsupervised density-ratio MIA.

This is NOT DOMIAS and is not an implementation of a Synth-MIA library attack.
Scientific dependencies: numpy and scikit-learn only; no torch/tensorflow.

Public interface: attack(mem, nonmem, synth, ref) -> (y_true, scores).
Inputs must already share a feature space standardized using ref only. The
attacker does not fit a scaler, choose features, or use candidate membership
labels. Only synth and ref enter model fitting or bandwidth selection.

Score(x) = log KDE_synth(x) - log KDE_ref(x); larger means more member-like.
Both Gaussian KDEs use the SAME bandwidth, selected by equal-weight mean
held-out log likelihood on synth and ref, with deterministic five-fold CV.
The fixed grid is geomspace(0.1, 2.0, 13) in the supplied standardized space.
This likelihood criterion estimates densities, not membership-attack power.

17 dimensions / 250 observations is a sparse density-estimation setting:
isotropic kernels can oversmooth local leakage, tails can have unstable log
ratios, reference-population mismatch can masquerade as membership, and the
finite grid can bind. Neither a high nor a chance AUC establishes a DP guarantee.

Run this file to execute five fixed-criterion controls (no output files written).
All controls use independent iid standard-Gaussian population draws, d=17 and
n=250 per set, then StandardScaler.fit(ref_raw) ONLY. No empirical criteria,
bandwidth grid, noise sizes or seeds are changed after inspecting results.
"""

from unittest.mock import patch

import numpy as np
import sklearn
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import KFold
from sklearn.neighbors import KernelDensity
from sklearn.preprocessing import StandardScaler


NAME = "KDE-ratio (own implementation)"
BANDWIDTH_GRID = tuple(float(h) for h in np.geomspace(0.1, 2.0, 13))
CV_SEED = 0
CONTROL_SEEDS = tuple(range(20))
N = 250
D = 17
POSITIVE_MIN_AUC = 0.9
NULL_MEAN_AUC_BOUNDS = (0.47, 0.53)


def _matrix(name, values, dimension=None, minimum_rows=1):
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] < 1:
        raise ValueError(f"{name} must be a 2D float array with >=1 column")
    if len(array) < minimum_rows:
        raise ValueError(f"{name} must have >= {minimum_rows} rows")
    if dimension is not None and array.shape[1] != dimension:
        raise ValueError(f"{name} must have {dimension} columns")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} contains NaN or infinity")
    return array


class KDERatio:
    """Fit on synth/ref only; score arbitrary candidates without membership labels."""

    def fit(self, synth, ref):
        synth = _matrix("synth", synth, minimum_rows=2).copy()
        ref = _matrix("ref", ref, synth.shape[1], minimum_rows=2).copy()
        self.n_features_ = synth.shape[1]
        self.n_folds_ = min(5, len(synth), len(ref))
        cv = KFold(self.n_folds_, shuffle=True, random_state=CV_SEED)
        synth_folds = list(cv.split(synth))
        ref_folds = list(cv.split(ref))
        self.cv_log_likelihoods_ = []

        for bandwidth in BANDWIDTH_GRID:
            population_means = []
            for population, folds in ((synth, synth_folds), (ref, ref_folds)):
                total_log_likelihood = 0.0
                total_validation_rows = 0
                for train, validation in folds:
                    model = KernelDensity(kernel="gaussian", metric="euclidean",
                                          bandwidth=bandwidth, atol=0, rtol=0)
                    model.fit(population[train])
                    total_log_likelihood += model.score_samples(
                        population[validation]).sum()
                    total_validation_rows += len(validation)
                population_means.append(total_log_likelihood / total_validation_rows)
            self.cv_log_likelihoods_.append(float(np.mean(population_means)))

        # First/smallest bandwidth wins an exact tie. No candidate-based fallback.
        best_index = int(np.argmax(self.cv_log_likelihoods_))
        self.bandwidth_ = BANDWIDTH_GRID[best_index]
        self.grid_boundary_ = best_index in (0, len(BANDWIDTH_GRID) - 1)
        self.synth_kde_ = KernelDensity(kernel="gaussian", metric="euclidean",
                                       bandwidth=self.bandwidth_, atol=0, rtol=0).fit(synth)
        self.ref_kde_ = KernelDensity(kernel="gaussian", metric="euclidean",
                                     bandwidth=self.bandwidth_, atol=0, rtol=0).fit(ref)
        return self

    def score(self, candidates):
        if not hasattr(self, "synth_kde_"):
            raise RuntimeError("Call fit(synth, ref) before score(candidates)")
        candidates = _matrix("candidates", candidates, self.n_features_)
        scores = (self.synth_kde_.score_samples(candidates)
                  - self.ref_kde_.score_samples(candidates))
        if not np.isfinite(scores).all():
            raise FloatingPointError("Non-finite log-density ratios; scores not replaced")
        return scores


def attack(mem, nonmem, synth, ref):
    """Synth-MIA-style interface; fits only on synth/ref, returns mem then nonmem.

    mem/nonmem are evaluation arrays, not fit inputs. Returned labels describe
    their supplied grouping; they are constructed only after model fitting.
    """
    model = KDERatio().fit(synth, ref)
    mem = _matrix("mem", mem, model.n_features_)
    nonmem = _matrix("nonmem", nonmem, model.n_features_)
    candidates = np.vstack((mem, nonmem))
    scores = model.score(candidates)
    y_true = np.concatenate((np.ones(len(mem), dtype=np.int64),
                             np.zeros(len(nonmem), dtype=np.int64)))
    return y_true, scores


def _population_sets(seed, kind):
    rng = np.random.default_rng(seed)
    members = rng.normal(size=(N, D))
    nonmembers = rng.normal(size=(N, D))
    reference = rng.normal(size=(N, D))
    if kind == "positive":
        synthetic = members + rng.normal(0, 0.02, size=(N, D))
    elif kind == "no_leak":
        synthetic = rng.normal(size=(N, D))
    elif kind == "placebo":
        # The release leaks the TRUE members, but both evaluation groups below
        # are disjoint real non-members. Pseudo-members are sampled from a
        # separate non-member pool, without replacement, independently of scores.
        synthetic = members + rng.normal(0, 0.02, size=(N, D))
        pool = rng.normal(size=(2 * N, D))
        permutation = rng.permutation(2 * N)
        members = pool[permutation[:N]]
        nonmembers = pool[permutation[N:]]
    elif kind == "laplace":
        # Integration example, not a claimed DP mechanism/calibrated epsilon.
        synthetic = members + rng.laplace(0, 0.25, size=(N, D))
    else:
        raise ValueError(kind)
    scaler = StandardScaler().fit(reference)
    return tuple(scaler.transform(a) for a in
                 (members, nonmembers, synthetic, reference))


def _auc_summary(kind):
    aucs = []
    bandwidths = []
    for seed in CONTROL_SEEDS:
        mem, nonmem, synth, ref = _population_sets(seed, kind)
        # Use the public function under test. Separate fit records bandwidth
        # diagnostics without introducing an alternative scoring path.
        y, scores = attack(mem, nonmem, synth, ref)
        aucs.append(float(roc_auc_score(y, scores)))
        bandwidths.append(KDERatio().fit(synth, ref).bandwidth_)
    aucs = np.asarray(aucs)
    return aucs, bandwidths


def _fit_isolation_test():
    mem, nonmem, synth, ref = _population_sets(123, "positive")
    candidates = np.vstack((mem, nonmem))
    permutation = np.random.default_rng(456).permutation(len(candidates))
    changed = candidates[permutation]
    # Repartitioning the permuted rows changes many membership labels assigned
    # by the interface, while retaining the same records and fitting datasets.
    fit_inputs = []
    original_fit = KernelDensity.fit

    def audited_fit(estimator, X, *args, **kwargs):
        fit_inputs.append(np.asarray(X).copy())
        return original_fit(estimator, X, *args, **kwargs)

    allowed = [synth, ref]
    cv = KFold(5, shuffle=True, random_state=CV_SEED)
    for population in (synth, ref):
        allowed.extend(population[train] for train, _ in cv.split(population))

    with patch.object(KernelDensity, "fit", new=audited_fit):
        y, original_scores = attack(mem, nonmem, synth, ref)
        new_y, changed_scores = attack(changed[:N], changed[N:], synth, ref)
        # Also alter candidate VALUES, checking that every fit still receives
        # only allowed synth/ref training arrays; this catches more than a
        # mere label shuffle. AUC for these artificial candidates is irrelevant.
        attack(mem + 7.0, nonmem - 5.0, synth, ref)

    recovered_scores = np.empty_like(changed_scores)
    recovered_scores[permutation] = changed_scores
    max_difference = float(np.max(np.abs(original_scores - recovered_scores)))
    labels_changed = int(np.count_nonzero(new_y != y[permutation]))
    allowed_only = all(any(np.array_equal(X, permitted) for permitted in allowed)
                       for X in fit_inputs)
    expected_calls = 3 * (len(BANDWIDTH_GRID) * 2 * 5 + 2)
    passed = (max_difference == 0.0 and labels_changed > 0 and allowed_only
              and len(fit_inputs) == expected_calls)
    return passed, max_difference, labels_changed, len(fit_inputs), allowed_only


def run_tests():
    print(NAME)
    print(f"numpy={np.__version__}; scikit-learn={sklearn.__version__}")
    print(f"All tests: d={D}; n_mem=n_nonmem=n_synth=n_ref={N}; scaler fit on ref only")
    print(f"Bandwidth grid={np.asarray(BANDWIDTH_GRID).round(6).tolist()}; CV folds=5; CV seed={CV_SEED}")
    print("Fixed criteria: positive every-seed AUC > 0.90; placebo/no-leak mean AUC in [0.47,0.53]")
    print("Fit isolation: exact score equality and all fit inputs allowed; integration: labels/shapes/finite only")
    outcomes = []
    for number, kind in ((1, "positive"), (2, "placebo"), (3, "no_leak")):
        aucs, bandwidths = _auc_summary(kind)
        if kind == "positive":
            passed = bool(np.all(aucs > POSITIVE_MIN_AUC))
        else:
            passed = bool(NULL_MEAN_AUC_BOUNDS[0] <= aucs.mean() <= NULL_MEAN_AUC_BOUNDS[1])
        outcomes.append(passed)
        print(f"TEST {number} {kind}: {'PASS' if passed else 'FAIL'}; seeds=0..19; "
              f"mean AUC={aucs.mean():.6f}; SD(ddof=1)={aucs.std(ddof=1):.6f}; "
              f"min={aucs.min():.6f}; max={aucs.max():.6f}")
        print(f"  per-seed AUC={aucs.round(6).tolist()}")
        print(f"  selected bandwidths={np.round(bandwidths, 6).tolist()}")

    passed, difference, changed_labels, fit_calls, allowed_only = _fit_isolation_test()
    outcomes.append(passed)
    print(f"TEST 4 fit isolation: {'PASS' if passed else 'FAIL'}; "
          f"max score difference={difference:.12g}; relabelled rows={changed_labels}; "
          f"audited KDE fit calls={fit_calls}; synth/ref-only inputs={allowed_only}")

    mem, nonmem, synth, ref = _population_sets(20261011, "laplace")
    y, scores = attack(mem, nonmem, synth, ref)
    model = KDERatio().fit(synth, ref)
    expected_y = np.concatenate((np.ones(N, dtype=np.int64), np.zeros(N, dtype=np.int64)))
    passed = bool(y.shape == (2*N,) and scores.shape == (2*N,)
                  and np.array_equal(y, expected_y) and np.isfinite(scores).all())
    outcomes.append(passed)
    print(f"TEST 5 Gaussian/Laplace integration: {'PASS' if passed else 'FAIL'}; "
          f"seed=20261011; Gaussian data shape=(250,17); Laplace scale=0.25 before ref-only scaling; "
          f"no clipping; y/scores shape={scores.shape}; AUC={roc_auc_score(y, scores):.6f}; "
          f"bandwidth={model.bandwidth_:.6f}; grid boundary={model.grid_boundary_}; finite={np.isfinite(scores).all()}")
    failures = [i+1 for i, passed in enumerate(outcomes) if not passed]
    print(f"FAILED TESTS: {failures if failures else 'none'}")
    return not failures


if __name__ == "__main__":
    raise SystemExit(0 if run_tests() else 1)
