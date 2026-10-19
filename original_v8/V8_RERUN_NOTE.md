V8 rerun, on the PC.
Script: for_chairs/A09/a09_v8_control_run.py, unchanged (copied to a scratch folder so the evidence folder was not written to). Input: <LOCAL_PATH> Python 3.10, pandas 2.3.3, scikit-learn 1.7.2.
Result: all 119 fields of the output JSON equal the stored for_chairs/A09/v8_control_results.json, except date_run.
Net DCR (contaminated minus clean_full) +0.1549; size effect +0.1903, selection effect -0.0354. MIA AUC net +0.3468 (paper +0.346 is a rounded-difference; +0.347 is the unrounded value).
