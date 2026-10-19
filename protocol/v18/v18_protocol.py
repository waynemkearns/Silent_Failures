"""V18 job (DP GAN, with a non-private GAN reference). Usage: python v18_protocol.py <cell> <world>      Cells: adult_gan, mimic_gan.
Design: ../../28_FROZEN_DESIGN_V18.md (read it first).
This file changes no earlier file. It imports the frozen V14 job code unchanged and reuses its world set-up, three standard arms, encoding,
reference-fitted scaler, attacks, placebo, records-only baseline, near-copy positive control and the public binning used for every DP release since V11.
Three releases per arm, all on the same publicly binned member table:
  dpctgan_eps1, dpctgan_eps10: DPCTGAN (smartnoise-synth), a GAN trained with DP-SGD on the discriminator, preprocessor_eps=0, batch size 64,
    epoch cap 300 (library default), all other settings at library defaults. The library stops training once its own accountant reports that the
    target epsilon is spent; it checks at the start of each epoch, so the spent value can exceed the target by up to one epoch. Each fit records the
    epochs trained, whether the budget stopped it, and the spent epsilon recomputed with the library's own accountant.
  ctgan_nodp: CTGAN (the ctgan package), NOT differentially private, library defaults (batch 500, 300 epochs). A reference showing what the
    attacks see on a GAN that learns the table. It makes no privacy claim.
Two additions over V14: (1) a planted-row sensitivity test as in V15 (a share f of the released rows replaced by real member rows, f = 0, 0.05,
0.10, 0.25, for every release), and (2) a fidelity check on the binned release: mean total variation distance (TVD) against the members over single
columns (one-way) and over all column pairs (two-way). The deciding comparison point is the same library with the same seed and zero training
steps (an untrained generator), because both libraries draw rows from the exact category frequencies and so beat a uniform draw without learning.
The non-members and an independent uniform draw over each column's bins are reported as further comparison points."""
import os,sys,json,time,math,random,itertools
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get("V18_OUT",HERE/"results")); OUT.mkdir(parents=True,exist_ok=True)
os.environ["V14_OUT"]=str(OUT)   # keeps every write by the imported V14 module inside the V18 results folder
sys.path.insert(0,str(HERE.parent/"v14"))
PKGS=os.environ.get("V18_PKGS")   # folder holding the ctgan package and its pure-Python dependencies, appended after site-packages
if PKGS and Path(PKGS).is_dir(): sys.path.append(PKGS)
import numpy as np,pandas as pd
import v14_protocol as p          # imports v10_protocol as p.v
v=p.v
from sklearn.preprocessing import StandardScaler
EPS=[1.0,10.0]; FGRID=[0.0,0.05,0.10,0.25]; ARMS=["clean_full","clean_matched","contaminated"]
RELEASES=["dpctgan_eps1","dpctgan_eps10","ctgan_nodp"]
BATCH=64; EPOCH_CAP=int(os.environ.get("V18_TEST_EPOCHS","300")); SIGMA=5.0
CT_EPOCHS=int(os.environ.get("V18_TEST_EPOCHS","300")); CT_BATCH=500
TEST_MODE="V18_TEST_EPOCHS" in os.environ   # code testing only: flagged in every result file and refused by the analysis
THREADS=int(os.environ.get("THREADS","2"))

def plant(raw,mem,f,seed):
    """Replace a share f of the released rows by real member rows (verbatim). f = 0 returns the release unchanged. Same rule as V15."""
    out=raw.copy(); n=len(out); m=int(round(f*n))
    if m>0:
        rr=np.random.default_rng(seed); pos=rr.choice(n,m,replace=False); src=rr.choice(len(mem),m,replace=False); out[pos]=mem[src]
    return out

def spent_epsilon(n_train,epochs_trained):
    """Spent epsilon for the discriminator, recomputed with the library's own settings: sample rate batch/n, noise multiplier 5,
    delta = 1/(n*sqrt(n)), two optimiser steps per batch (cross-entropy loss), the same RDP orders as the library."""
    from opacus import privacy_analysis as pa
    q=min(BATCH/n_train,1.0); steps=2*max(n_train//BATCH,1)*epochs_trained
    if steps==0: return 0.0
    alphas=[1+x/10.0 for x in range(1,100)]+list(range(12,64)); delta=1/(n_train*math.sqrt(n_train))
    return float(pa.get_privacy_spent(alphas,pa.compute_rdp(q,SIGMA,steps,alphas),delta)[0])

def _codes(T,cols,levels):
    return {c:np.clip(np.asarray(T[c]).astype(int),0,L-1) for c,L in zip(cols,levels)}

def tvd1(A,B,levels):
    """Mean over columns of the total variation distance between the one-way distributions of two binned tables."""
    cols=list(A.columns); a=_codes(A,cols,levels); b=_codes(B,cols,levels); out=[]
    for c,L in zip(cols,levels):
        out.append(0.5*float(np.abs(np.bincount(a[c],minlength=L)/len(A)-np.bincount(b[c],minlength=L)/len(B)).sum()))
    return float(np.mean(out))

def tvd2(A,B,levels):
    """Mean over all column pairs of the total variation distance between the two-way distributions of two binned tables."""
    cols=list(A.columns); a=_codes(A,cols,levels); b=_codes(B,cols,levels); L=dict(zip(cols,levels)); out=[]
    for c1,c2 in itertools.combinations(cols,2):
        k=L[c1]*L[c2]
        ha=np.bincount(a[c1]*L[c2]+a[c2],minlength=k)/len(A); hb=np.bincount(b[c1]*L[c2]+b[c2],minlength=k)/len(B)
        out.append(0.5*float(np.abs(ha-hb).sum()))
    return float(np.mean(out))

def dpctgan_release(D,eps,seed,n,epochs=None):
    import torch
    from snsynth import Synthesizer
    torch.set_num_threads(THREADS); torch.manual_seed(seed); np.random.seed(seed); random.seed(seed); t0=time.time()
    cap=EPOCH_CAP if epochs is None else epochs
    syn=Synthesizer.create("dpctgan",epsilon=eps,verbose=False,epochs=cap,batch_size=BATCH,cuda=False)
    syn.fit(D,categorical_columns=list(D.columns),preprocessor_eps=0.0); S=syn.sample(n)
    ep=len(syn.loss_d_list)
    info=dict(epochs_trained=ep,stopped_by_budget=bool(len(syn.epsilon_list)>ep),epoch_cap=cap,batch_size=BATCH,sigma=SIGMA,
              eps_target=eps,eps_spent=spent_epsilon(len(D),ep),fit_seconds=round(time.time()-t0,1))
    return S.reindex(columns=D.columns).astype(int),info

def ctgan_release(D,seed,n,epochs=None):
    import torch
    from ctgan import CTGAN
    torch.set_num_threads(THREADS); torch.manual_seed(seed); np.random.seed(seed); random.seed(seed); t0=time.time()
    ep=CT_EPOCHS if epochs is None else epochs
    m=CTGAN(epochs=ep,batch_size=CT_BATCH,verbose=False,enable_gpu=False)
    m.fit(D.astype(str),discrete_columns=list(D.columns)); S=m.sample(n)
    info=dict(epochs_trained=ep,batch_size=CT_BATCH,differentially_private=False,fit_seconds=round(time.time()-t0,1))
    return S.reindex(columns=D.columns).astype(int),info

def job(cell,w):
    ds,method=cell.split("_"); assert method=="gan"; t0=time.time()
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
        syn=sc.transform(v.laplace_release(mem,100.0,w*13+100)); rec["lap_eps100"]=v.run_attacks(Mem,Nm,syn,Ref,w)   # near-copy positive control, as in V11 to V17
        # binned member table (the release input), and the fidelity comparison points on the same public bins
        Dm,num_idx,centers=p.bin_release_input(mem,ref_all[:n_ref],cat_idx); Dn,_,_=p.bin_release_input(nm,ref_all[:n_ref],cat_idx)
        base_levels=[int(max(Dm[c].max(),Dn[c].max()))+1 for c in Dm.columns]
        ur=np.random.default_rng(7000+w*31+ai); Du=pd.DataFrame({c:ur.integers(0,L,n) for c,L in zip(Dm.columns,base_levels)})
        rec["tvd1_nonmembers"]=tvd1(Dm,Dn,base_levels); rec["tvd2_nonmembers"]=tvd2(Dm,Dn,base_levels)
        rec["tvd1_uniform"]=tvd1(Dm,Du,base_levels); rec["tvd2_uniform"]=tvd2(Dm,Du,base_levels)
        for rel in RELEASES:
            if rel.startswith("dpctgan"):
                e=float(rel.split("eps")[1]); Sb,info=dpctgan_release(Dm,e,w*17+int(e),n)
                Su,_=dpctgan_release(Dm,e,w*17+int(e),n,epochs=0)     # same library, same seed and initial weights, zero training
            else:
                Sb,info=ctgan_release(Dm,w*17+3,n)
                Su,_=ctgan_release(Dm,w*17+3,n,epochs=0)
            rec[f"{rel}_fit"]=info
            lev=[max(L,int(Sb[c].max())+1,int(Su[c].max())+1) for c,L in zip(Dm.columns,base_levels)]
            rec[f"tvd1_{rel}"]=tvd1(Dm,Sb.clip(lower=0),lev); rec[f"tvd2_{rel}"]=tvd2(Dm,Sb.clip(lower=0),lev)
            rec[f"tvd1_untrained_{rel}"]=tvd1(Dm,Su.clip(lower=0),lev); rec[f"tvd2_untrained_{rel}"]=tvd2(Dm,Su.clip(lower=0),lev)
            raw=p.decode(Sb,mem.shape[1],n,num_idx,centers)
            for f in FGRID:
                syn=sc.transform(plant(raw,mem,f,9000+w*31+ai))
                rec[f"{rel}_f{f:g}"]=v.run_attacks(Mem,Nm,syn,Ref,w)
                if f==0.0: rec[f"plc_{rel}"]=v.run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        recs.append(rec)
    import sklearn,scipy,torch,opacus,importlib.metadata as md
    def ver(x):
        try: return md.version(x)
        except Exception: return "unknown"
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,torch=torch.__version__,opacus=opacus.__version__,
              smartnoise_synth=ver("smartnoise-synth"),ctgan=ver("ctgan"),rdt=ver("rdt"),vendored="synth-mia 0981eadb",releases=RELEASES,eps=EPS,fgrid=FGRID,
              dpctgan_epoch_cap=EPOCH_CAP,dpctgan_batch=BATCH,ctgan_epochs=CT_EPOCHS,ctgan_batch=CT_BATCH,test_mode=TEST_MODE,seconds=round(time.time()-t0))
    assert recs[1]["n_members"]==recs[2]["n_members"]
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
