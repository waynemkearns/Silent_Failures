"""V19 job (a second DP GAN: DP-CTGAN on current opacus). Usage: python v19_protocol.py <cell> <world>      Cells: adult_gan2, mimic_gan2.
Design: ../../29_FROZEN_DESIGN_V19.md (read it first).
This file changes no earlier file. It imports the frozen V14 job code (worlds, arms, encoding, scaler, attacks, placebo, records-only baseline,
near-copy positive control, public binning) and the frozen V18 helpers (planted rows, one-way and two-way TVD), unchanged.
Releases per arm, on the same publicly binned member table: dpctgan2_eps1 (noise multiplier 5) and dpctgan2_eps10 (noise multiplier 1), from
dp_ctgan_opacus.py in this folder (batch 64, clipping norm 1, epoch cap 300, training stops before the budget is exceeded). For each, an untrained
generator from the same code, seed and initial weights is the fidelity comparison point.
opacus 1.5.2 is loaded from the folder in V19_PKGS, placed first on the path, so it shadows the opacus 0.14 used by V14 and V18 in this process
only. The ctgan package comes from V18_PKGS, as in V18."""
import os,sys,json,time,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
PK19=os.environ.get("V19_PKGS")
if PK19 and Path(PK19).is_dir(): sys.path.insert(0,PK19)
OUT=Path(os.environ.get("V19_OUT",HERE/"results")); OUT.mkdir(parents=True,exist_ok=True)
os.environ["V18_OUT"]=str(OUT); os.environ["V14_OUT"]=str(OUT)   # keeps every write by the imported modules inside the V19 results folder
sys.path.insert(1,str(HERE.parent/"v18")); sys.path.insert(1,str(HERE))
import numpy as np,pandas as pd
import v18_protocol as e18          # imports v14_protocol as e18.p and v10_protocol as e18.v; appends V18_PKGS for ctgan
p=e18.p; v=e18.v
from sklearn.preprocessing import StandardScaler
FGRID=[0.0,0.05,0.10,0.25]; ARMS=["clean_full","clean_matched","contaminated"]
SETTINGS={"dpctgan2_eps1":dict(epsilon=1.0,sigma=5.0),"dpctgan2_eps10":dict(epsilon=10.0,sigma=1.0)}
BATCH=64; CLIP=1.0; EPOCH_CAP=int(os.environ.get("V19_TEST_EPOCHS","300"))
TEST_MODE="V19_TEST_EPOCHS" in os.environ   # code testing only: flagged in every result file and refused by the analysis
THREADS=int(os.environ.get("THREADS","2"))

def release(D,epsilon,sigma,seed,n,max_epochs):
    import torch
    from dp_ctgan_opacus import DPCTGANModern
    torch.set_num_threads(THREADS); torch.manual_seed(seed); np.random.seed(seed); random.seed(seed); t0=time.time()
    m=DPCTGANModern(epsilon=epsilon,sigma=sigma,clip=CLIP,max_epochs=max_epochs,batch_size=BATCH); m.fit(D.astype(str),discrete_columns=list(D.columns)); S=m.sample(n)
    info=dict(steps=int(m.steps),epochs_trained=int(m.epochs_trained),steps_per_epoch=int(m.steps_per_epoch) if hasattr(m,"steps_per_epoch") else None,
              stopped_by_budget=bool(m.stopped_by_budget),epoch_cap=max_epochs,batch_size=BATCH,sigma=sigma,clip=CLIP,eps_target=epsilon,eps_spent=float(m.eps_spent),
              fit_seconds=round(time.time()-t0,1))
    return S.reindex(columns=D.columns).astype(int),info

def job(cell,w):
    ds,method=cell.split("_"); assert method=="gan2"; t0=time.time()
    import opacus; assert opacus.__version__.startswith("1.5"), "opacus 1.5 not loaded ("+opacus.__version__+"): check V19_PKGS"
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
                 test_mode=TEST_MODE,records_only_oof=v.oof_auc(Mem,Nm,w))
        syn=sc.transform(v.laplace_release(mem,100.0,w*13+100)); rec["lap_eps100"]=v.run_attacks(Mem,Nm,syn,Ref,w)   # near-copy positive control, as in V11 to V18
        Dm,num_idx,centers=p.bin_release_input(mem,ref_all[:n_ref],cat_idx); Dn,_,_=p.bin_release_input(nm,ref_all[:n_ref],cat_idx)
        base_levels=[int(max(Dm[c].max(),Dn[c].max()))+1 for c in Dm.columns]
        ur=np.random.default_rng(7000+w*31+ai); Du=pd.DataFrame({c:ur.integers(0,L,n) for c,L in zip(Dm.columns,base_levels)})
        rec["tvd1_nonmembers"]=e18.tvd1(Dm,Dn,base_levels); rec["tvd2_nonmembers"]=e18.tvd2(Dm,Dn,base_levels)
        rec["tvd1_uniform"]=e18.tvd1(Dm,Du,base_levels); rec["tvd2_uniform"]=e18.tvd2(Dm,Du,base_levels)
        for rel,s in SETTINGS.items():
            seed=w*17+int(s["epsilon"])+100
            Sb,info=release(Dm,s["epsilon"],s["sigma"],seed,n,EPOCH_CAP)
            Su,_=release(Dm,s["epsilon"],s["sigma"],seed,n,0)              # same code, same seed and initial weights, zero training
            rec[f"{rel}_fit"]=info
            lev=[max(L,int(Sb[c].max())+1,int(Su[c].max())+1) for c,L in zip(Dm.columns,base_levels)]
            rec[f"tvd1_{rel}"]=e18.tvd1(Dm,Sb.clip(lower=0),lev); rec[f"tvd2_{rel}"]=e18.tvd2(Dm,Sb.clip(lower=0),lev)
            rec[f"tvd1_untrained_{rel}"]=e18.tvd1(Dm,Su.clip(lower=0),lev); rec[f"tvd2_untrained_{rel}"]=e18.tvd2(Dm,Su.clip(lower=0),lev)
            raw=p.decode(Sb,mem.shape[1],n,num_idx,centers)
            for f in FGRID:
                syn=sc.transform(e18.plant(raw,mem,f,9000+w*31+ai))
                rec[f"{rel}_f{f:g}"]=v.run_attacks(Mem,Nm,syn,Ref,w)
                if f==0.0: rec[f"plc_{rel}"]=v.run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        recs.append(rec)
    import sklearn,scipy,torch,opacus,importlib.metadata as md
    def ver(x):
        try: return md.version(x)
        except Exception: return "unknown"
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,torch=torch.__version__,opacus=opacus.__version__,opacus_file=opacus.__file__,
              ctgan=ver("ctgan"),vendored="synth-mia 0981eadb",settings=SETTINGS,batch=BATCH,clip=CLIP,epoch_cap=EPOCH_CAP,fgrid=FGRID,test_mode=TEST_MODE,seconds=round(time.time()-t0))
    assert recs[1]["n_members"]==recs[2]["n_members"]
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
