"""V13 job. Usage: python v13_protocol.py <cell> <world>
Cells: adult_pat, mimic_pat. Laplace-perturbed records (NOT epsilon-DP). Design: ../../22_FROZEN_DESIGN_V13.md (read it first).
One clean pipeline and one defect injected per arm (P1, P2, P4a, P4b, P5, P6), each applied asymmetrically (members only) and symmetrically
(members, holdout and reference). P1 needs a patient identifier, so it runs on MIMIC-IV only. Data set-up, world seeds, encoding, reference policy,
attacks, release function and reference-fitted scaler are the unchanged V10 functions (../v10/v10_protocol.py)."""
import os,sys,json,time
import numpy as np,pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parent/"v10"))
import v10_protocol as v
OUT=Path(os.environ.get("V13_OUT",HERE/"results")); OUT.mkdir(exist_ok=True)
DIVS=[1.0,2.0,4.0]          # fixed after calibration on Adult worlds 1000 to 1004 (clean arm DCR AUC 0.51, 0.63, 0.83; not analysed further)
CONTROL_DIV=100.0            # near-copy positive control, clean arm only
CAP_FRAC=0.60                # P2: share of the file kept by the row cap
P4A_SD=0.5                   # P4a: uniform additive error, in standard deviations of the column (full file)
P4B_FRAC=0.08; P4B_SENT=9999999.0   # P4b: share of rows set to a sentinel
P5_Q=(0.01,0.99)             # P5: out-of-range values become NaN, then dropna on the same columns
P4_COL=dict(mimic="length_of_stay",adult="hours-per-week")
PATTERNS_BY_DS=dict(mimic=["P1","P2","P4a","P4b","P5","P6"],adult=["P2","P4a","P4b","P5","P6"])

def setup(ds,w):
    full,S=v.load(ds); full=full.copy(); full["_pos"]=np.arange(len(full)); FEATS=S["NUM"]+S["CAT"]
    uniq=(full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id") if ds=="mimic" else full.sample(frac=1,random_state=1000+w)).reset_index(drop=True)
    pool,hold,refr=uniq.iloc[:1000],uniq.iloc[1000:2000],uniq.iloc[2000:3000]
    ENC={c:sorted(refr[c].astype(str).unique()) for c in S["CAT"]}
    def encode(df):
        o=df[FEATS].copy()
        for c in S["CAT"]: o[c]=o[c].astype(str).map({x:i for i,x in enumerate(ENC[c])}).fillna(-1)
        return o.fillna(0).values.astype(float)
    return dict(ds=ds,w=w,full=full,S=S,encode=encode,raw=dict(pool=pool,hold=hold,ref=refr))

def clean_prep(df,c): return v.prep(df,"clean_full",None,c["S"],c["ds"])

def defect(pat,part,df,c):
    """Apply one defect to a raw part ('pool','hold','ref'), then the clean preparation. P6 is the V8 mask-and-unscoped-dropna contamination."""
    ds,S,w,full=c["ds"],c["S"],c["w"],c["full"]; pid=dict(pool=0,hold=1,ref=2)[part]
    if pat=="P2":   # hardcoded row cap: keep the part of the file that comes first, by original file position
        k=int(round(CAP_FRAC*len(df))); return clean_prep(df.nsmallest(k,"_pos"),c)
    if pat=="P1":   # row reduction by file position instead of a random or explicit choice, within patient
        first=full.drop_duplicates("patient_id",keep="first").set_index("patient_id")
        d=first.loc[df["patient_id"].values].reset_index(); return clean_prep(d,c)
    if pat=="P4a":  # uniform additive error in a derived column
        col=P4_COL[ds]; d=df.copy(); d[col]=d[col]+P4A_SD*float(full[col].std()); return clean_prep(d,c)
    if pat=="P4b":  # sentinel values in a derived column, an extreme-outlier cluster
        col=P4_COL[ds]; d=df.copy(); r=np.random.default_rng(9100+w*10+pid); d.loc[r.random(len(d))<P4B_FRAC,col]=P4B_SENT; return clean_prep(d,c)
    if pat=="P5":   # silent exclusion: out-of-range becomes NaN, then the NaN rows are dropped
        q=full[S["MASK"]].quantile(list(P5_Q)); d=df.copy()
        for col in S["MASK"]: d.loc[(d[col]<q.loc[P5_Q[0],col])|(d[col]>q.loc[P5_Q[1],col]),col]=np.nan
        return clean_prep(d.dropna(subset=S["MASK"]),c)
    raise ValueError(pat)

def build_arms(c):
    """Returns {arm: (members_df, nonmembers_df, reference_df)}. Same random stream as V12 for the contaminated arm."""
    S,ds,w=c["S"],c["ds"],c["w"]; R=c["raw"]
    rng=np.random.default_rng(5000+w)
    Pc=v.prep(R["pool"],"contaminated",rng,S,ds); Hc=v.prep(R["hold"],"contaminated",rng,S,ds); Rc=v.prep(R["ref"],"contaminated",rng,S,ds)
    clean=(clean_prep(R["pool"],c),clean_prep(R["hold"],c),clean_prep(R["ref"],c))
    arms={"clean":clean}
    for pat in PATTERNS_BY_DS[ds]:
        D=(Pc,Hc,Rc) if pat=="P6" else tuple(defect(pat,p,R[p],c) for p in ("pool","hold","ref"))
        arms[pat+"_sym"]=D; arms[pat+"_asym"]=(D[0],clean[1],clean[2])
    return arms

def sample_arm(c,mem_df,nm_df,ref_df,n,n_ref):
    w=c["w"]; enc=c["encode"]; mem_raw,nm_all,ref_all=enc(mem_df),enc(nm_df),enc(ref_df)
    assert n<=len(mem_raw) and n<=len(nm_all) and n_ref<=len(ref_all)
    rs=np.random.default_rng(w*7+1)
    mem=mem_raw[rs.permutation(len(mem_raw))[:n]]; nm=nm_all[rs.permutation(len(nm_all))[:n]]; ref=ref_all[rs.permutation(len(ref_all))[:n_ref]]
    sc=StandardScaler().fit(ref)
    return dict(mem=mem,sc=sc,Mem=sc.transform(mem),Nm=sc.transform(nm),Ref=sc.transform(ref))

def attack3(mem,nm,syn,ref):
    out={}
    for name,att in [("DCR",v.DCR()),("DCRDiff",v.DCRDiff())]:
        y,s=att.attack(mem,nm,syn,ref); out[name]=float(v.roc_auc_score(y,s))
    y,s=v.kde_ratio_own.attack(mem,nm,syn,ref); out["KDEratio"]=float(v.roc_auc_score(y,s)); return out

def job(cell,w):
    ds=cell.split("_")[0]; t0=time.time(); c=setup(ds,w); arms=build_arms(c)
    n=min(min(len(m),len(h)) for m,h,r in arms.values()); n_ref=min(v.REF_CAP,min(len(r) for m,h,r in arms.values()))
    assert n>=100 and n_ref>=100,(n,n_ref)
    recs=[]
    for name,(m,h,r) in arms.items():
        d=sample_arm(c,m,h,r,n,n_ref); k=n//2
        rec=dict(cell=cell,world=w,arm=name,n_members=int(n),n_ref=int(n_ref),n_mem_avail=len(m),n_nm_avail=len(h),n_ref_avail=len(r),records_only_oof=v.oof_auc(d["Mem"],d["Nm"],w),lap={},plc={})
        for dv in DIVS+([CONTROL_DIV] if name=="clean" else []):
            syn=d["sc"].transform(v.laplace_release(d["mem"],dv,w*13+int(dv)))
            rec["lap"][f"{dv:g}"]=attack3(d["Mem"],d["Nm"],syn,d["Ref"])
            rec["plc"][f"{dv:g}"]=attack3(d["Nm"][:k],d["Nm"][k:2*k],syn,d["Ref"])
        recs.append(rec)
    import sklearn,scipy
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",seconds=round(time.time()-t0))
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
