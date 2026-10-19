"""Does the submitted DCR size effect survive new cohort draws? Uses the submitted DCR definition (arm-fitted scaler,
Laplace noise at eps=1 on all 17 encoded columns, mean distance from release to its own members), shared public
encoding, over the same 10 patient-disjoint worlds as v8_repaired_protocol.py. Descriptive only."""
import os, numpy as np, pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.neighbors import NearestNeighbors
LAB=["lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin","lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"]
NUM=["age","length_of_stay","risk_score","medication_count"]+LAB; CAT=["sex","ethnicity","admission_type","deceased","is_emergency"]; FE=NUM+CAT
full=pd.read_csv(Path(os.environ["MIMIC_CANONICAL_CSV"])); ENC={c:LabelEncoder().fit(full[c].astype(str)) for c in CAT}
def enc(df):
    o=df[FE].copy()
    for c in CAT: o[c]=ENC[c].transform(o[c].astype(str))
    return o.fillna(0)
def lap(e,eps,seed):
    rng=np.random.default_rng(seed); o=e.copy().values.astype(float)
    for i in range(o.shape[1]):
        s=e.iloc[:,i].std()
        if s>0: o[:,i]+=rng.laplace(0,s/eps,len(o))
    return o
def dcr(syn,ref): return float(NearestNeighbors(n_neighbors=1).fit(ref).kneighbors(syn)[0].mean())
rows=[]
for w in range(10):
    uniq=full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id").reset_index(drop=True)
    pool=uniq.iloc[:1000]; rng=np.random.default_rng(5000+w)
    cf=pool.dropna(subset=LAB); d=pool.copy(); d.loc[rng.random(len(d))<0.4,LAB]=np.nan; ct=d.dropna(); mt=cf.sample(n=len(ct),random_state=w)
    r={}
    for name,df in [("full",cf),("matched",mt),("cont",ct)]:
        e=enc(df); sc=StandardScaler().fit(e); X=sc.transform(e); r[name]=np.mean([dcr(sc.transform(lap(e,1.0,s)),X) for s in [0,1,2,3,42]])
    rows.append(r)
R=pd.DataFrame(rows); print(R.round(3).to_string())
for a,b,l in [("matched","full","matched-full (size)"),("cont","matched","cont-matched (selection)"),("cont","full","cont-full (total)")]:
    v=(R[a]-R[b]).values; print(f"{l:26s} mean {v.mean():+.3f}  2.5-97.5 pct [{np.percentile(v,2.5):+.3f},{np.percentile(v,97.5):+.3f}]  worlds>0: {(v>0).sum()}/10")
