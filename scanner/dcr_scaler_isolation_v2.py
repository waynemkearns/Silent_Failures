"""Isolate why the DCR size effect (+0.17 under an arm-fitted scaler) disappears under a reference-fitted scaler.
Same 10 worlds, same arms, same release (Laplace-perturbed records, eps=1, 5 noise seeds), same DCR (release to own members).
Only the scaler used to standardise before measuring distance changes:
 S1 arm-fitted (submitted)  S2 reference-fitted, 250 rows, arm-processed (repaired protocol)  S3 one fixed scaler fitted on 20,000 canonical rows."""
import os, json, hashlib, sys, numpy as np, pandas as pd, sklearn
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
S3=StandardScaler().fit(enc(full.sample(20000,random_state=1)).values)
def prep(df,arm,rng):
    if arm=="cont":
        d=df.copy(); d.loc[rng.random(len(d))<0.4,LAB]=np.nan; return d.dropna()
    return df.dropna(subset=LAB)
rows=[]
for w in range(10):
    uniq=full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id").reset_index(drop=True)
    pool,refr=uniq.iloc[:1000],uniq.iloc[2000:3000]; rng=np.random.default_rng(5000+w)
    cf=pool.dropna(subset=LAB); ct=prep(pool,"cont",rng); mt=cf.sample(n=len(ct),random_state=w)
    arms={"full":(cf,prep(refr,"clean",rng)),"matched":(mt,prep(refr,"clean",rng)),"cont":(ct,prep(refr,"cont",rng))}
    r={}
    for name,(m,rf) in arms.items():
        e=enc(m); X=e.values; ref=enc(rf).values[:250]
        for sname,sc in [("S1",StandardScaler().fit(X)),("S2",StandardScaler().fit(ref)),("S3",S3)]:
            r[(name,sname)]=np.mean([dcr(sc.transform(lap(e,1.0,s)),sc.transform(X)) for s in [0,1,2,3,42]])
    rows.append(r)
R=pd.DataFrame(rows)
for s in ["S1","S2","S3"]:
    v=(R[("matched",s)]-R[("full",s)]).values; u=(R[("cont",s)]-R[("matched",s)]).values
    print(f"{s}: size (matched-full) {v.mean():+.3f} [{np.percentile(v,2.5):+.3f},{np.percentile(v,97.5):+.3f}] pos {int((v>0).sum())}/10 | selection (cont-matched) {u.mean():+.3f} [{np.percentile(u,2.5):+.3f},{np.percentile(u,97.5):+.3f}]  | mean DCR full/matched/cont {R[('full',s)].mean():.3f}/{R[('matched',s)].mean():.3f}/{R[('cont',s)].mean():.3f}")

# v2 addition (12 Oct 2026): save per-world values so the table can be rechecked without rerunning.
out={"script":"dcr_scaler_isolation_v2.py","input":os.environ["MIMIC_CANONICAL_CSV"],
     "input_sha256":hashlib.sha256(open(os.environ["MIMIC_CANONICAL_CSV"],"rb").read()).hexdigest(),
     "versions":{"numpy":np.__version__,"pandas":pd.__version__,"sklearn":sklearn.__version__,"python":sys.version.split()[0]},
     "worlds":[{"world":w,**{f"{a}_{sc}":float(R[(a,sc)].iloc[w]) for a in ("full","matched","cont") for sc in ("S1","S2","S3")}} for w in range(len(R))],
     "summary":{sc:{"size_matched_minus_full":[float(x) for x in (R[("matched",sc)]-R[("full",sc)]).values],
                    "selection_cont_minus_matched":[float(x) for x in (R[("cont",sc)]-R[("matched",sc)]).values]} for sc in ("S1","S2","S3")}}
dest=Path(__file__).resolve().parent/"dcr_scaler_isolation_worlds.json"; dest.write_text(json.dumps(out,indent=1)); print("saved",dest)
