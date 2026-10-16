"""V10 protocol: one (cell, world) job. Usage: python v10_protocol.py <cell> <world>
Cells: adult_laplace, adult_mst, mimic_mst. Design: ../../17_FROZEN_DESIGN_V10.md (read it first).
Same attacks, controls, matching and reference policy as V9 (../repaired_protocol/v8_repaired_protocol.py).
Releases: Laplace-perturbed records (scale = member sample SD / divisor, NOT epsilon-DP) or MST (smartnoise-synth), a DP synthesizer
with add/remove-one-record adjacency, run on publicly binned data with preprocessor_eps=0, so epsilon is the total budget."""
import os,sys,json,types,warnings,time
import numpy as np,pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.neighbors import NearestNeighbors
warnings.filterwarnings("ignore")
HERE=Path(__file__).resolve().parent; PROTO=HERE.parent/"repaired_protocol"; OUT=Path(os.environ.get("V10_OUT",HERE/"results")); OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(PROTO))
root=str(PROTO/"_vendored_synth_mia_0981eadb")
for name,path in [("synth_mia",root),("synth_mia.attackers",root+"/attackers")]:
    m=types.ModuleType(name); m.__path__=[path]; sys.modules[name]=m
from synth_mia.attackers.dcr import DCR
from synth_mia.attackers.dcr_diff import DCRDiff
from synth_mia.attackers.classifier import Classifier
from synth_mia.attackers.local_neighborhood import LocalNeighborhood
import kde_ratio_own

CAP=0.40; REF_CAP=250; NBINS=10; MST_EPS=[1.0,10.0,100.0]
MIMIC=dict(NUM=["age","length_of_stay","risk_score","medication_count"]+["lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin","lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"],
           CAT=["sex","ethnicity","admission_type","deceased","is_emergency"],
           MASK=["lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin","lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"])
ADULT=dict(NUM=["age","fnlwgt","education-num","capital-gain","capital-loss","hours-per-week"],
           CAT=["workclass","education","marital-status","occupation","relationship","race","sex","native-country","label"],
           MASK=["fnlwgt","capital-gain","capital-loss","hours-per-week"])
DEFAULT_ADULT="data/adult.csv"

def load(ds):
    if ds=="mimic":
        full=pd.read_csv(os.environ["MIMIC_CANONICAL_CSV"]); return full,MIMIC
    p=os.environ.get("ADULT_CSV",DEFAULT_ADULT); full=pd.read_csv(p).drop_duplicates().reset_index(drop=True); return full,ADULT

def prep(df,arm,rng,S,ds):
    if arm=="contaminated":
        d=df.copy()
        if ds=="adult": d=d.replace("?",np.nan)
        m=rng.random(len(d))<CAP; d.loc[m,S["MASK"]]=np.nan
        return d.dropna()
    return df.dropna(subset=S["MASK"]) if ds=="mimic" else df

def laplace_release(X,div,seed):
    rng=np.random.default_rng(seed); o=X.copy()
    for i in range(o.shape[1]):
        s=X[:,i].std(ddof=1)
        if s>0: o[:,i]+=rng.laplace(0,s/div,len(o))
    return o

def run_attacks(mem,nonmem,synth,ref,seed):
    out={}
    for name,att in [("DCR",DCR()),("DCRDiff",DCRDiff()),("Classifier",Classifier(RandomForestClassifier,n_estimators=100,random_state=seed))]:
        y,s=att.attack(mem,nonmem,synth,ref); out[name]=float(roc_auc_score(y,s))
    y,s=kde_ratio_own.attack(mem,nonmem,synth,ref); out["KDEratio"]=float(roc_auc_score(y,s))
    rad=float(np.median(NearestNeighbors(n_neighbors=2).fit(ref).kneighbors(ref)[0][:,1]))  # from ref only
    y,s=LocalNeighborhood(radius=rad).attack(mem,nonmem,synth,ref); out["LocalNeighborhood"]=float(roc_auc_score(y,s))
    return out

def oof_auc(A,B,seed):
    X=np.vstack([A,B]); y=np.r_[np.ones(len(A)),np.zeros(len(B))]; oof=np.zeros(len(y))
    for tr,te in StratifiedKFold(5,shuffle=True,random_state=seed).split(X,y):
        sc=StandardScaler().fit(X[tr]); c=RandomForestClassifier(100,random_state=seed).fit(sc.transform(X[tr]),y[tr]); oof[te]=c.predict_proba(sc.transform(X[te]))[:,1]
    return float(roc_auc_score(y,oof))

def mst_release(mem,ref,cat_idx,eps,seed,n):
    """MST on publicly binned data. Bin edges come from the attacker's reference set. preprocessor_eps=0, so eps is the total budget."""
    d=mem.shape[1]; num_idx=[i for i in range(d) if i not in cat_idx]; cols={}; centers={}
    for i in num_idx:
        edges=np.unique(np.quantile(ref[:,i],np.linspace(0,1,NBINS+1)[1:-1]))
        b_ref=np.searchsorted(edges,ref[:,i]); cs=[ref[b_ref==k,i].mean() if (b_ref==k).any() else ref[:,i].mean() for k in range(len(edges)+1)]
        cols[i]=np.searchsorted(edges,mem[:,i]); centers[i]=np.array(cs)
    for i in cat_idx: cols[i]=(mem[:,i]+1).astype(int)
    D=pd.DataFrame({f"c{i}":cols[i] for i in range(d)})
    if os.environ.get("V10_FAKE_MST")=="1":   # pipeline test only; results are flagged and refused by the analysis
        rs=np.random.default_rng(seed); S=D.sample(n,replace=True,random_state=seed).reset_index(drop=True)
    else:
        from snsynth import Synthesizer
        np.random.seed(seed); syn=Synthesizer.create("mst",epsilon=eps,verbose=False)
        syn.fit(D,categorical_columns=list(D.columns),preprocessor_eps=0.0); S=syn.sample(n)
    out=np.zeros((n,d))
    for i in range(d):
        v=np.asarray(S[f"c{i}"]).astype(int)
        out[:,i]=centers[i][np.clip(v,0,len(centers[i])-1)] if i in num_idx else v-1
    return out

def job(cell,w):
    ds=cell.split("_")[0]; kind=cell.split("_")[1]; t0=time.time()
    full,S=load(ds); FEATS=S["NUM"]+S["CAT"]
    uniq=(full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id") if ds=="mimic" else full.sample(frac=1,random_state=1000+w)).reset_index(drop=True)
    pool,hold,refr=uniq.iloc[:1000],uniq.iloc[1000:2000],uniq.iloc[2000:3000]
    ENC={c:sorted(refr[c].astype(str).unique()) for c in S["CAT"]}
    def encode(df):
        o=df[FEATS].copy()
        for c in S["CAT"]: o[c]=o[c].astype(str).map({v:i for i,v in enumerate(ENC[c])}).fillna(-1)
        return o.fillna(0).values.astype(float)
    cat_idx=[FEATS.index(c) for c in S["CAT"]]
    rng=np.random.default_rng(5000+w)
    P={a:prep(pool,a,rng,S,ds) for a in ["clean_full","contaminated"]}
    P["clean_matched"]=P["clean_full"].sample(n=len(P["contaminated"]),random_state=w)
    key=lambda a:"contaminated" if a=="contaminated" else "clean_full"
    H={a:prep(hold,key(a),rng,S,ds) for a in P}; R={a:prep(refr,key(a),rng,S,ds) for a in P}
    n_match=min(len(P["contaminated"]),len(P["clean_full"]),len(H["contaminated"]),len(H["clean_full"])); n_ref=min(REF_CAP,min(len(R[a]) for a in R))
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
                 fake_mst=os.environ.get("V10_FAKE_MST")=="1",records_only_oof=oof_auc(Mem,Nm,w))
        if kind=="laplace":
            for dv in (1.0,100.0):
                syn=sc.transform(laplace_release(mem,dv,w*13+int(dv)))
                rec[f"lap_eps{dv:g}"]=run_attacks(Mem,Nm,syn,Ref,w); rec[f"plc_lap_eps{dv:g}"]=run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        else:
            syn=sc.transform(laplace_release(mem,100.0,w*13+100)); rec["lap_eps100"]=run_attacks(Mem,Nm,syn,Ref,w)   # near-copy positive control
            for e in MST_EPS:
                syn=sc.transform(mst_release(mem,ref_all[:n_ref],cat_idx,e,w*17+int(e),n))
                rec[f"mst_eps{e:g}"]=run_attacks(Mem,Nm,syn,Ref,w); rec[f"plc_mst_eps{e:g}"]=run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
        recs.append(rec)
    import sklearn,scipy
    meta=dict(numpy=np.__version__,pandas=pd.__version__,sklearn=sklearn.__version__,scipy=scipy.__version__,vendored="synth-mia 0981eadb",seconds=round(time.time()-t0))
    try:
        import snsynth; meta["snsynth"]=getattr(snsynth,"__version__","unknown")
    except Exception: pass
    assert recs[1]["n_members"]==recs[2]["n_members"]
    tmp=OUT/f"{cell}_w{w}.json.tmp"; tmp.write_text(json.dumps(dict(meta=meta,results=recs),indent=1)); tmp.replace(OUT/f"{cell}_w{w}.json")
    print(cell,w,"ok",meta["seconds"],"s",flush=True)

if __name__=="__main__": job(sys.argv[1],int(sys.argv[2]))
