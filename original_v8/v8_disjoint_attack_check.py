"""
Read-only diagnostic on the V8 MIA (PoPETs 2027.2 paper 7). Reuses the arm construction, Laplace step and
seeds of for_chairs/A09/a09_v8_control_run.py unchanged. Two encoding modes:
  as_submitted    : encode() fits a new LabelEncoder on each frame (as in the submitted code)
  shared_encoding : one LabelEncoder per categorical column, fitted once on the full canonical
Attacks:
  A_orig     RF on members(1) vs synthetic(0); AUC members vs holdout (as submitted)
  A_placebo  same, but both groups are non-members (two disjoint halves of the holdout)
  B_disjoint RF on auxiliary real records never used as members or holdout (1) vs synthetic (0)
  C_dist     score = -distance to nearest synthetic record
"""
import os, json, warnings, numpy as np, pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

LAB=["lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin","lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"]
NUM=["age","length_of_stay","risk_score","medication_count"]+LAB
CAT=["sex","ethnicity","admission_type","deceased","is_emergency"]
SEEDS=[0,1,2,3,42]; EPS=1.0; SS=42; CAP=0.40
ENC={}

def encode(df,feats):
    out=df[feats].copy()
    for c in CAT:
        if c in out.columns: out[c]=LabelEncoder().fit_transform(out[c].astype(str))
    return out.fillna(0)

def encode_fixed(df,feats):
    out=df[feats].copy()
    for c in CAT:
        if c in out.columns: out[c]=ENC[c].transform(out[c].astype(str))
    return out.fillna(0)

def add_laplace(enc,eps,seed):
    rng=np.random.default_rng(seed); o=enc.copy().values.astype(float)
    for i in range(o.shape[1]):
        s=enc.iloc[:,i].std()
        if s>0: o[:,i]+=rng.laplace(0,s/eps,len(o))
    return o

def rf_attack(real,syn,seed):
    rng=np.random.default_rng(seed); n=min(len(syn),len(real))
    idx=rng.choice(len(syn),n,replace=False)
    X=np.vstack([real,syn[idx]]); y=np.hstack([np.ones(len(real)),np.zeros(n)])
    return RandomForestClassifier(100,random_state=seed).fit(X,y)

def auc(a,b):
    return float(roc_auc_score(np.r_[np.ones(len(a)),np.zeros(len(b))],np.r_[a,b]))

def main():
    full=pd.read_csv(Path(os.environ["MIMIC_CANONICAL_CSV"]))
    full=full.drop(columns=["encounter_date","discharge_date","patient_id","encounter_id"],errors="ignore")
    for c in CAT: ENC[c]=LabelEncoder().fit(full[c].astype(str))
    src_idx=full.sample(n=2000,random_state=SS).index
    src=full.loc[src_idx].reset_index(drop=True)
    pool=src.iloc[:1000].copy(); hold_raw=src.iloc[1000:2000].copy()
    aux_all=full.drop(index=src_idx).sample(n=5000,random_state=7).dropna(subset=LAB).reset_index(drop=True)
    clean_full=pool.dropna(subset=LAB).reset_index(drop=True)
    cap=np.random.default_rng(SS).random(len(pool))<CAP
    cp=pool.copy(); cp.loc[cap,LAB]=np.nan
    contam=cp.dropna().reset_index(drop=True)
    matched=clean_full.sample(n=len(contam),random_state=SS).reset_index(drop=True)
    arms={"clean_full":clean_full,"clean_matched":matched,"contaminated":contam}
    feats=[c for c in NUM+CAT if c in clean_full.columns]
    hold=hold_raw.dropna(subset=LAB).reset_index(drop=True)
    print({k:len(v) for k,v in arms.items()},"holdout",len(hold),flush=True)
    allres={}
    for mode,fn in [m for m in [("as_submitted",encode),("shared_encoding",encode_fixed)] if m[0]==os.environ.get("MODE",m[0])]:
        res={a:{k:[] for k in ["A_orig","A_placebo","B_disjoint","C_dist"]} for a in arms}
        for seed in SEEDS:
            for name,df in arms.items():
                enc=fn(df,feats); sc=StandardScaler().fit(enc)
                X=sc.transform(enc); H=sc.transform(fn(hold,feats))
                syn=sc.transform(add_laplace(enc,EPS,seed)); n=len(X)
                clf=rf_attack(X,syn,seed)
                res[name]["A_orig"].append(auc(clf.predict_proba(X)[:,1],clf.predict_proba(H)[:,1]))
                perm=np.random.default_rng(seed+100).permutation(len(H))
                h1=H[perm[:n]]; h2=H[perm[n:2*n]] if len(H)>=2*n else H[perm[n:]]
                cp_=rf_attack(h1,syn,seed)
                res[name]["A_placebo"].append(auc(cp_.predict_proba(h1)[:,1],cp_.predict_proba(h2)[:,1]))
                aux=sc.transform(fn(aux_all.iloc[:n],feats))
                cb=rf_attack(aux,syn,seed)
                res[name]["B_disjoint"].append(auc(cb.predict_proba(X)[:,1],cb.predict_proba(H)[:,1]))
                nn=NearestNeighbors(n_neighbors=1).fit(syn)
                res[name]["C_dist"].append(auc(-nn.kneighbors(X)[0][:,0],-nn.kneighbors(H)[0][:,0]))
        summ={a:{k:{"mean":round(float(np.mean(v)),4),"sd":round(float(np.std(v)),4),"values":[round(x,4) for x in v]} for k,v in d.items()} for a,d in res.items()}
        allres[mode]=summ
        print("\nMODE:",mode)
        print(f"{'arm':14s} {'A_orig':>8s} {'A_placebo':>10s} {'B_disjoint':>11s} {'C_dist':>8s}")
        for a,d in summ.items():
            print(f"{a:14s} {d['A_orig']['mean']:8.3f} {d['A_placebo']['mean']:10.3f} {d['B_disjoint']['mean']:11.3f} {d['C_dist']['mean']:8.3f}",flush=True)
    json.dump({"arm_sizes":{k:len(v) for k,v in arms.items()},"holdout_n":len(hold),"results":allres},open(f"v8_disjoint_attack_results_{os.environ.get('MODE','both')}.json","w"),indent=1)
main()
