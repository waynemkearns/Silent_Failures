# Executed pattern table, P1 to P9 (15 Oct 2026, cloud run, toy data)

Each example below was run. `patterns.py` runs all nine on small made-up tables and prints the outputs as JSON. It was run on Pandas 1.5.3, 2.0.3, 2.3.3 and 3.0.6 (Python 3.11; numpy 1.26.4 for the first two, 2.4.6 for the last two), with all warnings switched on. **All nine outputs are identical on all four versions, and no warning was raised.** The failures are not version quirks. They come from what the calls do by design.

What this shows and does not show. These are mechanism demonstrations on toy tables. They are not evidence of how often a pattern occurs, and the numbers are not the paper's case-study numbers. The right-hand column is the conclusion the pattern puts at risk, in plain words; it was checked against Section 3.1 (the pattern catalogue) of `main_r10_CLEAN.tex` on 15 Oct 2026; each row agrees with the catalogue text.

| Pattern | Plain definition | Three-line example | Output (identical on all four versions) | Conclusion at risk |
|---|---|---|---|---|
| P1 Positional selection | A group of rows is reduced to one by position, with no sort on a meaningful key. | `d.groupby("adm")["icd"].first()` then the same on `d.iloc[::-1]`, then after `d.sort_values(["adm","seq_num"])` | As stored: adm 1 gets I10, adm 2 gets J18. Rows reversed: N18 and I50. Sorted on seq_num: E11 and I50. | That each record carries the value the study intends, e.g. the primary diagnosis. |
| P2 Row cap | A hardcoded read limit silently keeps a fraction of the table. | `pd.read_csv(f, nrows=1000)` on a 200,000-row file | 1,000 rows read, 0.5 percent. No error. | That the evaluated data is the full table. |
| P3 Dead merge | A join whose result never reaches the output. | `a.merge(b, on="k")` with 600 rows each and two repeated keys; result never used | An unused 180,000-row intermediate. The output columns are only `k`, `x`. | None for the numbers; it is a resource and reviewability risk. |
| P4 Formula bug | A derived or coded value is wrong and enters scaling. | missing income coded 9999999 stays in the column; `inc.std()` | Std 4,194,976.6 with the sentinel, 7,245.7 without. Ratio 579. | That distances and scaled features reflect the real values. |
| P5 Silent exclusion | A binning or mapping turns out-of-range values into NaN without error. | `pd.cut(age, bins=[0, 30, 60, 100])` on ages 25, 40, 67, 102, -1, 55 | 102 and -1 become NaN. No error. | That every record reaches the next step. |
| P6 Unscoped dropna | `dropna()` with no `subset` removes a record for a NaN in any column. | `p.dropna()` versus `p.dropna(subset=["age"])` where `lab_a` is NaN in 6 of 10 rows | 4 rows left, against 10 when scoped to `age`. No count is reported. | That the same records are kept for members and holdout, and that the number dropped is known. |
| P7 Implicit output mutation | A canonical file is overwritten with no guard or trace. | `df.to_csv("canonical.csv")` run twice with different data | File hash e9d27c03d1cb after run 1, 3e50571ba5d0 after run 2. No warning. | That the file in hand is the one behind a reported result. |
| P8 Documentation drift | A comment says something is handled that the code does not do. | a comment "sentinel values (9999999) already handled upstream" above a function that returns its input | 1 sentinel remains after the function. | That the pipeline does what its documentation says. |
| P9 Parameter inheritance | A constant validated in one domain is reused in another. | `SAMPLE_N = 50000` (kept for a 6,000,000-row source) applied to a 2,000,000-row table | 2.5 percent of rows kept, against 0.83 percent in the source domain. | That a setting tested in one domain holds in the next. |

## Files
`patterns.py`, and `out_pandas_1.5.3.json`, `out_pandas_2.0.3.json`, `out_pandas_2.3.3.json`, `out_pandas_3.0.6.json` in the same folder.

## Limits
Toy tables, one run per version, one machine. The P3, P7, P8 and P9 rows show that the situation arises and goes unflagged, not that any result changes. P3 and P7 to P9 are the assurance patterns, so their right-hand column is about reviewability, not about the numbers.
