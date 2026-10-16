"""V12 job. Usage: python v12_protocol.py <cell> <world>
Cells: adult_asym, mimic_asym   Laplace-perturbed records. Part A (asymmetric preparation arm) and Part B (scaler isolation).
       adult_mstasym, mimic_mstasym   MST release (smartnoise-synth), asymmetric preparation arm only (Part C).
Design: ../../21_FROZEN_DESIGN_V12.md (read it first). The data set-up, seeds, preparation, encoding, attacks and releases are the
unchanged V10 functions (../v10/v10_protocol.py). The three standard arms reproduce V10 exactly; one new arm is added."""
import os,sys,json,time
import numpy as np
from pathlib import Path
from sklearn.preprocessing import StandardScaler
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parent/"v10"))
import v10_protocol as v
OUT=Path(os.environ.get("V12_OUT",HERE/"results")); OUT.mkdir(exist_ok=True)
STD=["clean_full","clean_matched","contaminated"]; MM="contaminated_mismatched"
MST_EPS12=[1.0,10.0]

def setup(ds,w):
    full,S=v.load(ds); FEATS=S["NUM"]+S["CAT"]
    uniq=(full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id") if ds=="mimic" else full.sample(frac=1,random_state=1000+w)).reset_index(drop=True)
    pool,hold,refr=uniq.iloc[:1000],uniq.iloc[1000:2000],uniq.iloc[2000:3000]
    ENC={c:sorted(refr[c].astype(str).unique()) for c in S["CAT"]}
    def encode(df):
        o=df[FEATS].copy()
        for c in S["CAT"]: o[c]=o[c].astype(str).map({x:i for i,x in enumerate(ENC[c])}).fillna(-1)
        return o.fillna(0).values.astype(float)
    cat_idx=[FEATS.index(c) for c in S["CAT"]]
    rng=np.random.default_rng(5000+w)
    P={a:v.prep(pool,a,rng,S,ds) for a in ["clean_full","contaminated"]}
    P["clean_matched"]=P["clean_full"].sample(n=len(P["contaminated"]),random_state=w)
    key=lambda a:"contaminated" if a=="contaminated" else "clean_full"
    Hd={a:v.prep(hold,key(a),rng,S,ds) for a in P}; Rd={a:v.prep(refr,key(a),rng,S,ds) for a in P}
    n_match=min(len(P["contaminated"]),len(P["clean_full"]),len(Hd["contaminated"]),len(Hd["clean_full"])); n_ref=min(v.REF_CAP,min(len(Rd[a]) for a in Rd))
    return dict(full=full,S=S,encode=encode,cat_idx=cat_idx,P=P,H=Hd,R=Rd,n_match=n_match,n_ref=n_ref,w=w)

def arm_data(c,arm):
    """Same sampling steps and seeds as V10. MM = members from the contaminated pool, holdout and reference prepared as the clean arm."""
    w=c["w"]; enc=c["encode"]
    mk,nk,rk=("contaminated","clean_full","clean_full") if arm==MM else (arm,arm,arm)
    mem_raw,nm_all,ref_all=enc(c["P"][mk]),enc(c["H"][nk]),enc(c["R"][rk])
    n=min(len(mem_raw),len(nm_all)) if arm=="clean_full" else c["n_match"]; n_ref=c["n_ref"]
    assert n<=len(mem_raw) and n<=len(nm_all) and n_ref<=len(ref_all)
    rs=np.random.default_rng(w*7+1)
    mem=mem_raw[rs.permutation(len(mem_raw))[:n]]; nm=nm_all[rs.permutation(len(nm_all))[:n]]; ref=ref_all[rs.permutation(len(ref_all))[:n_ref]]
    assert len(mem)==len(nm)==n and len(ref)==n_ref
    sc=StandardScaler().fit(ref)
    return dict(mem=mem,nm=nm,ref=ref,ref_all=ref_all,n=n,n_ref=n_ref,sc=sc,Mem=sc.transform(mem),Nm=sc.transform(nm),Ref=sc.transform(ref),
                n_pool_retained=len(c["P"][mk]),n_hold_retained=len(c["H"][nk]),n_ref_retained=len(c["R"][rk]))

def attack3(mem,nm,syn,ref):
    out={}
    for name,att in [("DCR",v.DCR()),("DCRDiff",v.DCRDiff())]:
        y,s=att.attack(mem,nm,syn,ref); out[name]=float(v.roc_auc_score(y,s))
    y,s=v.kde_ratio_own.attack(mem,nm,syn,ref); out["KDEratio"]=float(v.roc_auc_score(y,s)); return out

def head(cell,w,arm,d):
    return dict(cell=cell,world=w,arm=arm,n_pool_retained=d["n_pool_retained"],n_hold_retained=d["n_hold_retained"],n_ref_retained=d["n_ref_retained"],
                n_members=int(d["n"]),n_ref=int(d["n_ref"]),fake_mst=os.environ.get("V10_FAKE_MST")=="1",records_only_oof=v.oof_auc(d["Mem"],d["Nm"],w))

def job_laplace(cell,w):
    ds=cell.split("_")[0]; t0=time.time(); c=setup(ds,w); recs=[]
    fixed=None
    for arm in STD+[MM]:
        d=arm_data(c,arm); rec=head(cell,w,arm,d); k=len(d["Nm"])//2
        for dv in (1.0,100.0):
            syn=d["sc"].transform(v.laplace_release(d["mem"],dv,w*13+int(dv)))
            rec[f"lap_eps{dv:g}"]=v.run_attacks(d["Mem"],d["Nm"],syn,d["Ref"],w)
            rec[f"plc_lap_eps{dv:g}"]=v.run_attacks(d["Nm"][:k],d["Nm"][k:2*k],syn,d["Ref"],w)
        if arm in STD:   # Part B: scaler isolation at divisor 1. S2 (reference-fitted) is the lap_eps1 result above.
            if fixed is None:
                fs=c["full"].sample(min(20000,len(c["full"])),random_state=1); fixed=StandardScaler().fit(c["encode"](fs))
            raw=v.laplace_release(d["mem"],1.0,w*13+1); sc_out={}
            for sname,sc in [("S1",StandardScaler().fit(d["mem"])),("S3",fixed)]:
                sc_out[sname]=attack3(sc.transform(d["mem"]),sc.transform(d["nm"]),sc.transform(raw),sc.transform(d["ref"]),)
            rec["scaler"]=sc_out
        recs.append(rec)
    save(cell,w,recs,t0)

def job_mst(cell,w):
    ds=cell.split("_")[0]; t0=time.time(); c=setup(ds,w)
    log=OUT/f"progress_{cell}_w{w}.log"
    def note(s):
        with open(log,"a") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+s+"\n")
    note("job started"); d=arm_data(c,MM); rec=head(cell,w,MM,d); k=len(d["Nm"])//2
    syn=d["sc"].transform(v.laplace_release(d["mem"],100.0,w*13+100)); rec["lap_eps100"]=v.run_attacks(d["Mem"],d["Nm"],syn,d["Ref"],w)
    for i,e in enumerate(MST_EPS12,1):
        t=time.time(); note(f"MST fit {i} of {len(MST_EPS12)}, epsilon {e:g}, started")
        syn=d["sc"].transform(v.mst_release(d["mem"],d["ref_all"][:d["n_ref"]],c["cat_idx"],e,w*17+int(e),d["n"]))
        rec[f"mst_eps{e:g}"]=v.run_attacks(d["Mem"],d["Nm"],syn,d["Ref"],w); rec[f"plc_mst_eps{e:g}"]=v.run_attacks(d["Nm"][:k],d["Nm"][k:2*k],syn,d["Ref"],w)
        note(f"MST fit {i} done in {time.time()-t:.0f} s")
    save(cell,w,[rec],t0); note("job finished")

def save(cell,w,recs,t0):
    import sklearn,scipy,pandas as pd
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",seconds=round(time.time()-t0))
    try:
        import snsynth; meta["snsynth"]=getattr(snsynth,"__version__","unknown")
    except Exception: pass
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__":
    cell,w=sys.argv[1],int(sys.argv[2])
    (job_mst if "mst" in cell else job_laplace)(cell,w)
