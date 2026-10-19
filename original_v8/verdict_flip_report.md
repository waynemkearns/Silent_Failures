# Verdict-Flip Experiment — P2+P6 Cascade
**Artefact tag:** A09  
**Date:** 2026-07-22  
**Substrate:** corrected MIMIC-IV v3.1 (SHA 7558c398…, verified=True)

## Configuration
| Parameter | Value |
|---|---|
| n_source | 2000 |
| n_train | 740 (clean after dropna) |
| n_contaminated | 251 (P2+P6 survivors) |
| n_holdout | 751 |
| ε (Laplace) | 1.0 |
| Seeds | [0, 1, 2, 3, 42] |
| cap_rate | 0.4 |

## Results (mean across 5 seeds)

| Metric | Clean | Contaminated | Δ (cont−clean) |
|---|---|---|---|
| DCR (syn→train, standardised) | 4.1270 | 4.2583 | +0.1313 |
| DCR (syn→holdout, standardised) | 4.2961 | 4.3574 | +0.0613 |
| MIA AUC | 0.5821 | 0.7199 | +0.1378 |

## Verdict

**VERDICT_FLIP_CONFIRMED**

Contaminated substrate produces DCR=4.2583 vs clean DCR=4.1270 (Δ=+0.1313). The contaminated substrate appears MORE PRIVATE than the clean substrate (false-negative privacy verdict). Exceeds threshold=0.05.

## Interpretation

The P2+P6 cascade produces a false-negative privacy verdict under the pre-registered
frozen decision rule. A researcher evaluating privacy on the contaminated substrate
(n=251, 25% of the intended training set) observes a higher
DCR than the researcher evaluating the same pipeline on the clean substrate
(n=740). The higher DCR would be interpreted as evidence that synthetic data is
more private — but this apparent safety is an artefact of the contaminated, homogeneous
survivor cohort, not a property of the synthesiser or the true population.

The result directly demonstrates the paper's central claim: substrate contamination
changes downstream privacy evaluation conclusions. The false-negative direction is the
operationally dangerous outcome — a researcher believing their data is safer than it is.
