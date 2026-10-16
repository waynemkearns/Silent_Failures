"""V17 job (does a pipeline slip hide a planted leak, or raise a false alarm?). Usage: python v17_protocol.py <cell> <world>      Cells: adult_c, mimic_c.
Design: ../../27_FROZEN_DESIGN_V17.md (read it first).
This file changes no earlier file. It imports the frozen V13 code unchanged (world set-up, the clean pipeline and the injected slips P1, P2, P4a, P4b, P5, P6, each asymmetric and symmetric,
encoding, reference-fitted scaler, attacks) and the frozen V14D PrivBayes-style release. For every arm of a world it releases one PrivBayes-style table at epsilon 10 from that arm's members
(reference for the binning from that arm's reference), then replaces a share f of the released rows by real member rows of that arm, verbatim (the V15 rule), f = 0, 0.10, 0.25. One more variant replaces 25% by noisy copies of members (Laplace noise SD/4, as in V16 Part A).
The same attacks are run on every arm. The clean arm also gets the near-copy positive control (Laplace, divisor 100) as in V13."""
import os,sys,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get("V17_OUT",HERE/"results")); OUT.mkdir(parents=True,exist_ok=True)
os.environ["V14D_OUT"]=str(OUT); os.environ["V13_OUT"]=str(OUT)   # keeps every write of the imported modules inside the V17 results folder
sys.path.insert(0,str(HERE.parent/"v13")); sys.path.insert(0,str(HERE.parent/"v14d"))
import numpy as np,pandas as pd
import v13_protocol as q
import v14d_protocol as d          # registers the PrivBayes-style release
v=q.v; RELEASE=d.p.RELEASE["pb"]
EPS=10.0; FGRID=[0.0,0.10,0.25]; NC_D=4.0; NC_F=0.25   # verbatim shares; one noisy-copy point (noise SD/4, share 0.25)

def plant(raw,mem,f,seed):
    """Same rule as V15: replace a share f of the released rows by real member rows (verbatim). f = 0 returns the release unchanged."""
    out=raw.copy(); n=len(out); m=int(round(f*n))
    if m>0:
        rr=np.random.default_rng(seed); pos=rr.choice(n,m,replace=False); src=rr.choice(len(mem),m,replace=False); out[pos]=mem[src]
    return out

def job(cell,w):
    ds=cell.split("_")[0]; t0=time.time(); c=q.setup(ds,w); arms=q.build_arms(c); S=c["S"]; FEATS=S["NUM"]+S["CAT"]; cat_idx=[FEATS.index(x) for x in S["CAT"]]
    n=min(min(len(m),len(h)) for m,h,r in arms.values()); n_ref=min(v.REF_CAP,min(len(r) for m,h,r in arms.values()))
    assert n>=100 and n_ref>=100,(n,n_ref)
    recs=[]
    for ai,(name,(m,h,r)) in enumerate(arms.items()):
        dd=q.sample_arm(c,m,h,r,n,n_ref); k=n//2; sc=dd["sc"]; refraw=sc.inverse_transform(dd["Ref"])
        rec=dict(cell=cell,world=w,arm=name,n_members=int(n),n_ref=int(n_ref),n_mem_avail=len(m),n_nm_avail=len(h),n_ref_avail=len(r),records_only_oof=v.oof_auc(dd["Mem"],dd["Nm"],w),pb={},plc={})
        base=RELEASE(dd["mem"],refraw,cat_idx,EPS,w*17+int(EPS),n)
        for f in FGRID:
            syn=sc.transform(plant(base,dd["mem"],f,9000+w*31+ai))
            rec["pb"][f"{f:g}"]=q.attack3(dd["Mem"],dd["Nm"],syn,dd["Ref"])
            if f==0.0: rec["plc"]["0"]=q.attack3(dd["Nm"][:k],dd["Nm"][k:2*k],syn,dd["Ref"])
        noisy=v.laplace_release(dd["mem"],NC_D,w*13+200+int(NC_D))      # every member row perturbed once (noise SD/4 per column); planted rows are drawn from it
        syn=sc.transform(plant(base,noisy,NC_F,12000+w*31+ai+100*int(NC_D))); rec["pb"][f"nc_d{NC_D:g}_f{NC_F:g}"]=q.attack3(dd["Mem"],dd["Nm"],syn,dd["Ref"])
        if name=="clean":
            syn=sc.transform(v.laplace_release(dd["mem"],100.0,w*13+100)); rec["lap100"]=q.attack3(dd["Mem"],dd["Nm"],syn,dd["Ref"])
        recs.append(rec)
    import sklearn,scipy,snsynth
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",method="pb",eps=EPS,fgrid=FGRID,seconds=round(time.time()-t0))
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
