"""V15 job (sensitivity test). Usage: python v15_protocol.py <cell> <world>      Cells: adult_mwem, mimic_mwem, adult_pb, mimic_pb.
Design: ../../25_FROZEN_DESIGN_V15.md (read it first).
This file changes no earlier file. It imports the frozen V14 and V14D job code unchanged and reuses its world set-up, three standard arms, encoding,
reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control and the two DP release functions (MWEM, PrivBayes-style).
Release: the same DP synthetic table as V14 and V14D at epsilon 10 (same seeds, so the f = 0 results repeat V14 and V14D exactly), then a known share f of the
released rows is replaced by real member records, copied verbatim. f runs over 0, 0.05, 0.10 and 0.25. The copy is a planted leak with a known size."""
import os,sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get("V15_OUT",HERE/"results")); OUT.mkdir(parents=True,exist_ok=True)
os.environ["V14D_OUT"]=str(OUT)   # the imported V14D module points V14_OUT at V14D_OUT; this keeps every write inside the V15 results folder
sys.path.insert(0,str(HERE.parent/"v14d"))
import numpy as np,pandas as pd
import v14d_protocol as d          # registers the PrivBayes-style release; imports v14_protocol
p=d.p; v=p.v
from sklearn.preprocessing import StandardScaler
EPS=10.0; FGRID=[0.0,0.05,0.10,0.25]; ARMS=["clean_full","clean_matched","contaminated"]

def plant(raw,mem,f,seed):
    """Replace a share f of the released rows by real member rows (verbatim). f = 0 returns the release unchanged."""
    out=raw.copy(); n=len(out); m=int(round(f*n))
    if m>0:
        rr=np.random.default_rng(seed); pos=rr.choice(n,m,replace=False); src=rr.choice(len(mem),m,replace=False); out[pos]=mem[src]
    return out

def job(cell,w):
    ds,method=cell.split("_"); t0=time.time()
    S,FEATS,pool,hold,refr,encode=p.world(ds,w); cat_idx=[FEATS.index(c) for c in S["CAT"]]
    rng=np.random.default_rng(5000+w)
    P={a:v.prep(pool,a,rng,S,ds) for a in ["clean_full","contaminated"]}
    P["clean_matched"]=P["clean_full"].sample(n=len(P["contaminated"]),random_state=w)
    key=lambda a:"contaminated" if a=="contaminated" else "clean_full"
    H={a:v.prep(hold,key(a),rng,S,ds) for a in P}; R={a:v.prep(refr,key(a),rng,S,ds) for a in P}
    n_match=min(len(P["contaminated"]),len(P["clean_full"]),len(H["contaminated"]),len(H["clean_full"])); n_ref=min(v.REF_CAP,min(len(R[a]) for a in R))
    recs=[]
    for ai,arm in enumerate(ARMS):
        mem_raw,nm_all,ref_all=encode(P[arm]),encode(H[arm]),encode(R[arm])
        n=min(len(mem_raw),len(nm_all)) if arm=="clean_full" else n_match
        assert n<=len(mem_raw) and n<=len(nm_all) and n_ref<=len(ref_all)
        rs=np.random.default_rng(w*7+1)
        mem=mem_raw[rs.permutation(len(mem_raw))[:n]]; nm=nm_all[rs.permutation(len(nm_all))[:n]]; ref=ref_all[rs.permutation(len(ref_all))[:n_ref]]
        assert len(mem)==len(nm)==n and len(ref)==n_ref
        sc=StandardScaler().fit(ref); Mem,Nm,Ref=sc.transform(mem),sc.transform(nm),sc.transform(ref); k=len(Nm)//2
        rec=dict(cell=cell,world=w,arm=arm,n_pool_prefilter=len(pool),n_pool_retained=len(P[arm]),n_hold_retained=len(H[arm]),n_ref_retained=len(R[arm]),n_members=int(n),n_ref=int(n_ref),
                 records_only_oof=v.oof_auc(Mem,Nm,w))
        syn=sc.transform(v.laplace_release(mem,100.0,w*13+100)); rec["lap_eps100"]=v.run_attacks(Mem,Nm,syn,Ref,w)   # near-copy positive control, as in V11
        base=p.RELEASE[method](mem,ref_all[:n_ref],cat_idx,EPS,w*17+int(EPS),n)                                      # same call and seed as V14 and V14D
        for f in FGRID:
            raw=plant(base,mem,f,9000+w*31+ai)
            syn=sc.transform(raw)
            rec[f"{method}_eps10_f{f:g}"]=v.run_attacks(Mem,Nm,syn,Ref,w)
            if f==0.0: rec[f"plc_{method}_eps10"]=v.run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        recs.append(rec)
    import sklearn,scipy,snsynth
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",snsynth=getattr(snsynth,"__version__","unknown"),method=method,eps=EPS,fgrid=FGRID,seconds=round(time.time()-t0))
    assert recs[1]["n_members"]==recs[2]["n_members"]
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
