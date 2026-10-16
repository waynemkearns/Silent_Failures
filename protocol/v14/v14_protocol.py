"""V14 job. Usage: python v14_protocol.py <cell> <world>      or      python v14_protocol.py gan <adult|mimic>
Cells: adult_mwem, mimic_mwem (Part A) and adult_aim, mimic_aim (Part C). Design: ../../23_FROZEN_DESIGN_V14.md (read it first).
Same set-up as V10/V11 (three standard arms, same worlds, seeds, encoding, reference-fitted scaler, attacks, placebo, records-only baseline).
Release: MWEM (smartnoise-synth), a differentially private marginal-based synthesizer, run on publicly binned data exactly as the V11 MST release
(bin edges from the attacker's reference, preprocessor_eps=0, so epsilon is the total budget). Columns are modelled in groups of 3 (split_factor=3).
Part C uses AIM (smartnoise-synth), a correlation-aware DP synthesizer, at epsilon 1 only, with the same binning and the same arms.
The 'gan' mode is a feasibility smoke test of DPCTGAN: it fits and samples, records time and errors, and computes no attack and makes no claim."""
import os,sys,json,time,warnings
import numpy as np,pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parent/"v10"))
import v10_protocol as v
OUT=Path(os.environ.get("V14_OUT",HERE/"results")); OUT.mkdir(exist_ok=True)
METHODS={"mwem":[1.0,10.0],"aim":[1.0]}; SPLIT_FACTOR=3; GAN_EPOCHS=20; GAN_EPS=10.0

def bin_release_input(mem,ref,cat_idx):
    d=mem.shape[1]; num_idx=[i for i in range(d) if i not in cat_idx]; cols={}; centers={}
    for i in num_idx:
        edges=np.unique(np.quantile(ref[:,i],np.linspace(0,1,v.NBINS+1)[1:-1]))
        b_ref=np.searchsorted(edges,ref[:,i]); cs=[ref[b_ref==k,i].mean() if (b_ref==k).any() else ref[:,i].mean() for k in range(len(edges)+1)]
        cols[i]=np.searchsorted(edges,mem[:,i]); centers[i]=np.array(cs)
    for i in cat_idx: cols[i]=(mem[:,i]+1).astype(int)
    return pd.DataFrame({f"c{i}":cols[i] for i in range(d)}),num_idx,centers

def decode(S,d,n,num_idx,centers):
    out=np.zeros((n,d))
    for i in range(d):
        x=np.asarray(S[f"c{i}"]).astype(int)
        out[:,i]=centers[i][np.clip(x,0,len(centers[i])-1)] if i in num_idx else x-1
    return out

def mwem_release(mem,ref,cat_idx,eps,seed,n):
    D,num_idx,centers=bin_release_input(mem,ref,cat_idx)
    from snsynth import Synthesizer
    np.random.seed(seed); syn=Synthesizer.create("mwem",epsilon=eps,split_factor=SPLIT_FACTOR,verbose=False)
    syn.fit(D,categorical_columns=list(D.columns),preprocessor_eps=0.0); S=syn.sample(n)
    return decode(S,mem.shape[1],n,num_idx,centers)

def aim_release(mem,ref,cat_idx,eps,seed,n):
    D,num_idx,centers=bin_release_input(mem,ref,cat_idx)
    from snsynth import Synthesizer
    np.random.seed(seed); syn=Synthesizer.create("aim",epsilon=eps,verbose=False)
    syn.fit(D,categorical_columns=list(D.columns),preprocessor_eps=0.0); S=syn.sample(n)
    return decode(S,mem.shape[1],n,num_idx,centers)

RELEASE={"mwem":mwem_release,"aim":aim_release}

def world(ds,w):
    full,S=v.load(ds); FEATS=S["NUM"]+S["CAT"]
    uniq=(full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id") if ds=="mimic" else full.sample(frac=1,random_state=1000+w)).reset_index(drop=True)
    pool,hold,refr=uniq.iloc[:1000],uniq.iloc[1000:2000],uniq.iloc[2000:3000]
    ENC={c:sorted(refr[c].astype(str).unique()) for c in S["CAT"]}
    def encode(df):
        o=df[FEATS].copy()
        for c in S["CAT"]: o[c]=o[c].astype(str).map({x:i for i,x in enumerate(ENC[c])}).fillna(-1)
        return o.fillna(0).values.astype(float)
    return S,FEATS,pool,hold,refr,encode

def job(cell,w):
    ds,method=cell.split("_"); t0=time.time(); EPS=METHODS[method]
    S,FEATS,pool,hold,refr,encode=world(ds,w); cat_idx=[FEATS.index(c) for c in S["CAT"]]
    rng=np.random.default_rng(5000+w)
    P={a:v.prep(pool,a,rng,S,ds) for a in ["clean_full","contaminated"]}
    P["clean_matched"]=P["clean_full"].sample(n=len(P["contaminated"]),random_state=w)
    key=lambda a:"contaminated" if a=="contaminated" else "clean_full"
    H={a:v.prep(hold,key(a),rng,S,ds) for a in P}; R={a:v.prep(refr,key(a),rng,S,ds) for a in P}
    n_match=min(len(P["contaminated"]),len(P["clean_full"]),len(H["contaminated"]),len(H["clean_full"])); n_ref=min(v.REF_CAP,min(len(R[a]) for a in R))
    recs=[]
    for arm in ["clean_full","clean_matched","contaminated"]:
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
        for e in EPS:
            syn=sc.transform(RELEASE[method](mem,ref_all[:n_ref],cat_idx,e,w*17+int(e),n))
            rec[f"{method}_eps{e:g}"]=v.run_attacks(Mem,Nm,syn,Ref,w); rec[f"plc_{method}_eps{e:g}"]=v.run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        recs.append(rec)
    import sklearn,scipy,snsynth
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",snsynth=getattr(snsynth,"__version__","unknown"),split_factor=SPLIT_FACTOR,method=method,seconds=round(time.time()-t0))
    assert recs[1]["n_members"]==recs[2]["n_members"]
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

def gan_smoke(ds):
    """Feasibility only. DPCTGAN on the clean_full members of world 0. Records versions, time and any error. No attack, no claim."""
    t0=time.time(); rec=dict(kind="gan_smoke",dataset=ds,epochs=GAN_EPOCHS,epsilon=GAN_EPS,ok=False)
    try:
        import torch; rec["torch"]=torch.__version__; rec["cuda"]=bool(torch.cuda.is_available())
        try:
            import opacus; rec["opacus"]=opacus.__version__
        except Exception as e: rec["opacus"]="import failed: "+repr(e)[:150]
        import snsynth; rec["snsynth"]=getattr(snsynth,"__version__","unknown")
        S,FEATS,pool,hold,refr,encode=world(ds,0); cat_idx=[FEATS.index(c) for c in S["CAT"]]
        P=v.prep(pool,"clean_full",None,S,ds); mem=encode(P); ref=encode(v.prep(refr,"clean_full",None,S,ds))
        D,num_idx,centers=bin_release_input(mem,ref,cat_idx); rec["rows"]=int(len(D))
        from snsynth import Synthesizer
        np.random.seed(0); syn=Synthesizer.create("dpctgan",epsilon=GAN_EPS,verbose=False,epochs=GAN_EPOCHS,batch_size=64,cuda=False)
        syn.fit(D,categorical_columns=list(D.columns),preprocessor_eps=0.0); S2=syn.sample(len(D)); rec["sample_shape"]=list(S2.shape); rec["ok"]=True
    except Exception as e: rec["error"]=(type(e).__name__+": "+str(e))[:400]
    rec["seconds"]=round(time.time()-t0,1); (OUT/f"gan_smoke_{ds}.json").write_text(json.dumps(rec,indent=1)); print("gan smoke",ds,rec,flush=True)

if __name__=="__main__":
    if sys.argv[1]=="gan": gan_smoke(sys.argv[2])
    else: job(sys.argv[1],int(sys.argv[2]))
