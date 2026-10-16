"""Executed toy examples for P1 to P9. Prints one JSON object. Run under each Pandas version."""
import json, os, sys, hashlib, tempfile, io, warnings
warnings.simplefilter("always")
_W=[]
_orig=warnings.showwarning
def _sw(m,c,f,l,file=None,line=None): _W.append(f"{c.__name__}: {m}")
warnings.showwarning=_sw
import numpy as np, pandas as pd
out = {"pandas": pd.__version__, "numpy": np.__version__, "python": sys.version.split()[0]}

# P1 positional selection: one primary diagnosis per admission, chosen by position (first), no sort on seq_num
rows = [(1,3,"I10"),(1,1,"E11"),(1,2,"N18"),(2,2,"J18"),(2,1,"I50")]  # (admission, seq_num, icd)
d = pd.DataFrame(rows, columns=["adm","seq_num","icd"])
first_pos = d.groupby("adm")["icd"].first().to_dict()
first_pos_shuffled = d.iloc[::-1].groupby("adm")["icd"].first().to_dict()
first_sorted = d.sort_values(["adm","seq_num"]).groupby("adm")["icd"].first().to_dict()
out["P1"] = {"first_as_stored": first_pos, "first_after_reordering_rows": first_pos_shuffled, "first_after_sort_on_seq_num": first_sorted}

# P2 row cap
tmp = tempfile.mkdtemp(); f = os.path.join(tmp, "labs.csv")
pd.DataFrame({"id": range(200000), "lab": np.arange(200000) % 7}).to_csv(f, index=False)
capped = pd.read_csv(f, nrows=1000)
out["P2"] = {"rows_in_file": 200000, "rows_read": len(capped), "fraction_read": round(len(capped)/200000, 4)}

# P3 dead merge: result never used except in a print
a = pd.DataFrame({"k": [1]*300 + [2]*300, "x": range(600)})
b = pd.DataFrame({"k": [1]*300 + [2]*300, "y": range(600)})
tmp_merge = a.merge(b, on="k")
out["P3"] = {"rows_a": len(a), "rows_b": len(b), "rows_in_unused_merge": len(tmp_merge), "columns_reaching_output": list(a.columns)}

# P4 formula bug: missing coded as 9999999 stays in a column that is then scaled
inc = pd.Series([40000, 52000, 61000, 47000, 9999999, 58000, 9999999, 43000, 50000, 55000], dtype=float)
clean = inc[inc < 9999999]
out["P4"] = {"std_with_sentinel": round(float(inc.std()), 1), "std_without": round(float(clean.std()), 1), "ratio": round(float(inc.std()/clean.std()), 1)}

# P5 silent exclusion: pd.cut converts out-of-range values to NaN, no error
age = pd.Series([25, 40, 67, 102, -1, 55])
cut = pd.cut(age, bins=[0, 30, 60, 100])
out["P5"] = {"input": age.tolist(), "bins": [str(x) for x in cut.tolist()], "n_nan": int(cut.isna().sum())}

# P6 unscoped dropna: NaN created upstream in one column removes whole records
p = pd.DataFrame({"id": range(10), "age": range(30, 40), "lab_a": [np.nan]*6 + [1.0]*4, "note": ["x"]*10})
out["P6"] = {"rows_before": len(p), "rows_after_dropna": len(p.dropna()), "rows_after_dropna_subset_age": len(p.dropna(subset=["age"]))}

def _rd(p):
    with open(p,"rb") as fh: return fh.read()
# P7 implicit overwrite: second run replaces the file with no trace
tmp = tempfile.mkdtemp(); g = os.path.join(tmp, "canonical.csv")
pd.DataFrame({"v": [1, 2, 3]}).to_csv(g, index=False); h1 = hashlib.sha256(_rd(g)).hexdigest()[:12]
pd.DataFrame({"v": [9, 9, 9]}).to_csv(g, index=False); h2 = hashlib.sha256(_rd(g)).hexdigest()[:12]
out["P7"] = {"hash_after_run_1": h1, "hash_after_run_2": h2, "warnings_seen_in_whole_script": None}

# P8 documentation drift: comment says sentinels handled, code does not
def prep(df):
    # sentinel values (9999999) already handled upstream
    return df
q = prep(pd.DataFrame({"inc": [50000, 9999999]}))
out["P8"] = {"comment_claims": "sentinels handled", "sentinels_remaining": int((q["inc"] == 9999999).sum())}

# P9 parameter inherited from another domain: sample size and bins validated elsewhere
SAMPLE_N = 50000  # validated for claims data of about 6 million rows
cen = pd.DataFrame({"x": np.arange(2_000_000)})
s = cen.sample(n=min(SAMPLE_N, len(cen)), random_state=0)
out["P9"] = {"table_rows": len(cen), "sample_rows": len(s), "fraction_kept": round(len(s)/len(cen), 3),
             "fraction_kept_in_source_domain": round(SAMPLE_N/6_000_000, 4)}

out["P7"]["warnings_seen_in_whole_script"]=len(_W); out["warnings_text"]=_W[:5]
print(json.dumps(out, sort_keys=True))
