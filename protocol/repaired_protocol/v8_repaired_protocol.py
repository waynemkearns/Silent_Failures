"""
V8 repaired protocol (post-hoc, written 11 Oct 2026 after the diagnostic in ../mia_check).

THREAT MODEL. The attacker holds (a) the released synthetic records, (b) an auxiliary reference set of real
records from the same population that are neither members nor non-members, and (c) a candidate record whose
membership is unknown. The attacker has NO target membership labels and NO private training data when fitting.
Preprocessing boundary: the scaler is fitted on the reference set only. Categorical vocabulary has two modes (env VOCAB):
 "reference" (primary): levels fitted on the world's auxiliary reference patients (pre-arm-filtering, identical for all arms);
            levels unseen there map to code -1. This is the attacker's own information.
 "source"   (sensitivity): levels fitted on the whole credentialed canonical. This is NOT a public vocabulary; it is
            reported only to show how much the results depend on the choice.
v2 (11 Oct 2026, after external review): one feasible matched member count per world for clean_matched and contaminated;
one shared reference count per world for all arms; assertions; sizes saved.

DESIGN. Patient-disjoint: one random encounter per patient, members / non-members / reference drawn from disjoint
patients. Missingness handling is matched: the arm's preprocessing (clean dropna on labs, or P2 40% lab mask then
unscoped dropna) is applied to members, non-members and reference alike. Non-members are subsampled to the member
count. Reference size is min(250, smallest reference pool over arms) per world and is the same in every arm.
Release: Laplace-PERTURBED RECORDS (per-column scale = member-arm sample SD / eps). Not an epsilon-DP mechanism.
Attacks: Synth-MIA (commit 0981eadb) DCR, DCRDiff, Classifier. DOMIAS, LOGAN, GenLRA, DensityEstimate need torch,
which is not installable here, so they were NOT run.
Independent replicates: 10 worlds (cohort draws), one noise seed each.

CONTROLS and PASS CRITERIA, fixed before the first run:
 PLACEBO  (pseudo-members drawn from non-members, release built from true members): mean AUC within 0.47 to 0.53
          for every attack and arm, otherwise the arm/attack is not calibrated and its results are not interpreted.
 POSITIVE (eps=100, release is a near copy of the members): mean DCR-attack AUC > 0.90 in every arm, otherwise the
          protocol has no power and a null at eps=1 means nothing.
 RECORDS-ONLY (5-fold out-of-fold RF, members vs non-members, no release): mean AUC within 0.45 to 0.55 in every
          arm, otherwise cohorts still differ for reasons other than the release.
"""
import os, sys, json, types, warnings
import numpy as np, pandas as pd
from pathlib import Path
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
warnings.filterwarnings("ignore")

HERE=Path(__file__).parent; sys.path.insert(0,str(HERE))
root=str(HERE/"_vendored_synth_mia_0981eadb")
for name,path in [("synth_mia",root),("synth_mia.attackers",root+"/attackers")]:
    m=types.ModuleType(name); m.__path__=[path]; sys.modules[name]=m
from synth_mia.attackers.dcr import DCR
from synth_mia.attackers.dcr_diff import DCRDiff
from synth_mia.attackers.classifier import Classifier

LAB=["lab_creatinine","lab_glucose","lab_hematocrit","lab_hemoglobin","lab_platelet_count","lab_potassium","lab_sodium","lab_white_blood_cells"]
NUM=["age","length_of_stay","risk_score","medication_count"]+LAB
CAT=["sex","ethnicity","admission_type","deceased","is_emergency"]
FEATS=NUM+CAT
EPS_LEVELS=[1.0,10.0,30.0,100.0]
CAP=0.40; REF_CAP=250
ENC={}; VOCAB=os.environ.get("VOCAB","reference")

def encode(df):
    o=df[FEATS].copy()
    for c in CAT:
        m={v:i for i,v in enumerate(ENC[c])}
        o[c]=o[c].astype(str).map(m).fillna(-1)
    return o.fillna(0).values.astype(float)

def prep(df,arm,rng):
    if arm=="contaminated":
        d=df.copy(); m=rng.random(len(d))<CAP; d.loc[m,LAB]=np.nan
        return d.dropna()
    return df.dropna(subset=LAB)

def laplace_release(X,eps,seed):
    rng=np.random.default_rng(seed); o=X.copy()
    for i in range(o.shape[1]):
        s=X[:,i].std(ddof=1)
        if s>0: o[:,i]+=rng.laplace(0,s/eps,len(o))
    return o

def run_attacks(mem,nonmem,synth,ref,seed,kde=True):
    out={}
    for name,att in [("DCR",DCR()),("DCRDiff",DCRDiff()),("Classifier",Classifier(RandomForestClassifier,n_estimators=100,random_state=seed))]:
        y,s=att.attack(mem,nonmem,synth,ref)
        out[name]=float(roc_auc_score(y,s))
    if kde and os.environ.get("KDE")=="1":
        import kde_ratio_own
        y,sc_=kde_ratio_own.attack(mem,nonmem,synth,ref); out["KDEratio"]=float(roc_auc_score(y,sc_))
    if kde and os.environ.get("LN")=="1":
        from synth_mia.attackers.local_neighborhood import LocalNeighborhood
        from sklearn.neighbors import NearestNeighbors
        d1=NearestNeighbors(n_neighbors=2).fit(ref).kneighbors(ref)[0][:,1]
        rad=float(np.median(d1))  # radius set from ref only, never from members
        y,sc_=LocalNeighborhood(radius=rad).attack(mem,nonmem,synth,ref); out["LocalNeighborhood"]=float(roc_auc_score(y,sc_))
    return out

def oof_auc(A,B,seed):
    X=np.vstack([A,B]); y=np.r_[np.ones(len(A)),np.zeros(len(B))]; oof=np.zeros(len(y))
    for tr,te in StratifiedKFold(5,shuffle=True,random_state=seed).split(X,y):
        sc=StandardScaler().fit(X[tr]); c=RandomForestClassifier(100,random_state=seed).fit(sc.transform(X[tr]),y[tr])
        oof[te]=c.predict_proba(sc.transform(X[te]))[:,1]
    return float(roc_auc_score(y,oof))

def main():
    lo,hi=[int(x) for x in os.environ.get("WORLDS","0-9").split("-")]
    full=pd.read_csv(Path(os.environ["MIMIC_CANONICAL_CSV"]))
    if VOCAB=="source":
        for c in CAT: ENC[c]=sorted(full[c].astype(str).unique())
    results=[]
    for w in range(lo,hi+1):
        uniq=full.sample(frac=1,random_state=1000+w).drop_duplicates("patient_id").reset_index(drop=True)
        pool,hold,refr=uniq.iloc[:1000],uniq.iloc[1000:2000],uniq.iloc[2000:3000]
        rng=np.random.default_rng(5000+w)
        P={a:prep(pool,a,rng) for a in ["clean_full","contaminated"]}
        n_cont=len(P["contaminated"])
        P["clean_matched"]=P["clean_full"].sample(n=n_cont,random_state=w)
        H={a:prep(hold,"contaminated" if a=="contaminated" else "clean_full",rng) for a in P}
        R={a:prep(refr,"contaminated" if a=="contaminated" else "clean_full",rng) for a in P}
        if VOCAB=="reference":
            for c in CAT: ENC[c]=sorted(refr[c].astype(str).unique())
        n_match=min(len(P["contaminated"]),len(P["clean_full"]),len(H["contaminated"]),len(H["clean_full"]))
        n_ref=min(REF_CAP,min(len(R[a]) for a in R))
        for arm in ["clean_full","clean_matched","contaminated"]:
            mem_raw=encode(P[arm]); nm_all=encode(H[arm]); ref_all=encode(R[arm])
            n=min(len(mem_raw),len(nm_all)) if arm=="clean_full" else n_match
            assert n<=len(mem_raw) and n<=len(nm_all) and n_ref<=len(ref_all)
            rs=np.random.default_rng(w*7+1)
            mem=mem_raw[rs.permutation(len(mem_raw))[:n]]; nm=nm_all[rs.permutation(len(nm_all))[:n]]
            ref=ref_all[rs.permutation(len(ref_all))[:n_ref]]
            assert len(mem)==len(nm)==n and len(ref)==n_ref
            sc=StandardScaler().fit(ref)
            Mem,Nm,Ref=sc.transform(mem),sc.transform(nm),sc.transform(ref)
            rec={"world":w,"arm":arm,"vocab":VOCAB,"n_pool_prefilter":int(len(pool)),"n_pool_retained":int(len(P[arm])),"n_hold_retained":int(len(H[arm])),"n_ref_retained":int(len(R[arm])),"n_members":int(n),"n_ref":int(len(ref)),"records_only_oof":oof_auc(Mem,Nm,w)}
            for eps in EPS_LEVELS:
                syn=sc.transform(laplace_release(mem,eps,w*13+int(eps)))
                rec[f"eps{eps:g}"]=run_attacks(Mem,Nm,syn,Ref,w,kde=eps in (1.0,100.0))
                if eps==1.0 or eps==100.0:
                    k=len(Nm)//2   # placebo: pseudo-members and non-members both drawn from non-members
                    rec[f"placebo_eps{eps:g}"]=run_attacks(Nm[:k],Nm[k:2*k],syn,Ref,w)
                    # DCR descriptive: mean distance from release to its own members, in reference-scaled space
                    from scipy.spatial import cKDTree
                    rec[f"dcr_release_to_members_eps{eps:g}"]=float(cKDTree(Mem).query(syn,k=1)[0].mean())
            results.append(rec)
        r3=[r for r in results if r["world"]==w]
        assert r3[1]["n_members"]==r3[2]["n_members"] and len({r["n_ref"] for r in r3})==1
        print("world",w,"done",[(r["arm"],r["n_members"],r["n_ref"]) for r in r3],flush=True)
    import hashlib,sklearn,scipy
    meta={"vocab":VOCAB,"canonical_sha256_prefix":hashlib.sha256(open(os.environ["MIMIC_CANONICAL_CSV"],"rb").read()).hexdigest()[:8],
          "numpy":np.__version__,"pandas":pd.__version__,"sklearn":sklearn.__version__,"scipy":scipy.__version__,"vendored":"synth-mia 0981eadb"}
    json.dump({"meta":meta,"results":results},open(HERE/f"v2{os.environ.get('TAG','')}_{VOCAB}_worlds_{lo}_{hi}.json","w"),indent=1)
main()
