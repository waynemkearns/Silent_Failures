"""Pre-specified analysis for V16 (see ../../26_FROZEN_DESIGN_V16.md). Prints verdicts; no free choices.
Release: MWEM or PrivBayes-style at epsilon 1. Cells adult_mwem, mimic_mwem, adult_pb, mimic_pb; three standard arms; minimum 30 worlds per cell. Each cell has its own Holm families.
Part B (verbatim rows planted, share f = 0.05, 0.10, 0.25): detection contrast on the clean_matched arm, AUC at f minus AUC at f = 0, paired by world, per informative attack.
Part A (noisy copies of members planted, noise divisor d = 4, 2, 1, share f = 0.05, 0.10, 0.25, 0.50): the same contrast for each (d, f).
  'detected' if the Holm-adjusted one-sided p for 'increase > 0' is below 0.05; 'beyond the margin' if the Holm-adjusted one-sided p for 'increase > 0.03' is below 0.05.
Part B2 (epsilon comparison): the Part B gain at epsilon 1 minus the V15 gain at epsilon 10, paired by world, equivalence within +/-0.03 (needs the V15 results).
Secondary (descriptive): contaminated minus clean_matched at f = 0 and in Part B."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; MINW=int(os.environ.get("V16_MIN_WORLDS","30")); TEST_MODE="V16_MIN_WORLDS" in os.environ
STD=["clean_full","clean_matched","contaminated"]; ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]
FV=["0.05","0.1","0.25"]; FN=["0.05","0.1","0.25","0.5"]; DN=["4","2","1"]
H=Path(__file__).resolve().parent; RES=Path(sys.argv[1]) if len(sys.argv)>1 else H/"results"
RES15=Path(os.environ.get("V16_V15_RES",H.parent/"v15"/"results"))
def load(d,cell):
    R=[]
    for f in sorted(d.glob(f"{cell}_w*.json")): R+=json.load(open(f))["results"]
    return R
def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]); k=len(ps); run=0; out=[0]*k
    for rank,i in enumerate(order): run=max(run,min(1,ps[i]*(k-rank))); out[i]=run
    return out
def ci(d):
    n=len(d); m=float(d.mean()); se=max(float(d.std(ddof=1)/np.sqrt(n)),1e-12); tc=stats.t.ppf(1-ALPHA,n-1); return m,se,m-tc*se,m+tc*se,n
def p_gt(m,se,n,thr): return float(1-stats.t.cdf((m-thr)/se,n-1))
def p_eq(m,se,n): return float(max(1-stats.t.cdf((m+MARGIN)/se,n-1),stats.t.cdf((m-MARGIN)/se,n-1)))
def p_sh(m,se,n): return float(min(1-stats.t.cdf((m-MARGIN)/se,n-1),stats.t.cdf((m+MARGIN)/se,n-1)))
def verdict(a0,aM): return "BEYOND the 0.03 margin" if aM<ALPHA else ("detected (increase > 0)" if a0<ALPHA else "not detected")
for cell in ("adult_mwem","mimic_mwem","adult_pb","mimic_pb"):
    method=cell.split("_")[1]; kB=lambda f:f"{method}_eps1_f{f}"; kA=lambda dv,f:f"{method}_eps1_nc_d{dv}_f{f}"
    print("\n"+"="*72+"\nCELL",cell,f"({'MWEM' if method=='mwem' else 'PrivBayes-style'} release at epsilon 1)")
    R=load(RES,cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in STD]; ro_ok=all(.45<=x<=.55 for x in ro)
    print("records-only means (clean_full, clean_matched, contaminated)",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    inf=[]
    for a in ATT:
        pos=[np.mean([g(w,arm)["lap_eps100"][a] for w in W]) for arm in STD]; pl=[np.mean([g(w,arm)[f"plc_{method}_eps1"][a] for w in W]) for arm in STD]
        okp=min(pos)>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{a:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means (f=0) {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: inf.append(a)
    print("informative attacks:",inf)
    print("Mean AUC by arm, Part B shares (all attacks, descriptive):")
    for arm in STD:
        for f in ["0"]+FV: print(f"  {arm:14s} f {f:>4s}",{a:round(float(np.mean([g(w,arm)[kB(f)][a] for w in W])),3) for a in ATT})
    if not ro_ok or not inf: print("Gates not met: no claim for this cell."); continue
    def contrast(keys,labels,title):
        T=[]
        for a in inf:
            for k,lab in zip(keys,labels):
                d=np.array([g(w,"clean_matched")[k][a]-g(w,"clean_matched")[kB("0")][a] for w in W]); m,se,lo,hi,nn=ci(d); T.append((a,lab,m,lo,hi,p_gt(m,se,nn,0.0),p_gt(m,se,nn,MARGIN)))
        h0=holm([t[5] for t in T]); hM=holm([t[6] for t in T]); first0={}; firstM={}
        print(f"\n{title}, clean_matched arm: AUC at the planted release minus AUC at f=0, paired, 90% CI, Holm over {len(T)} tests, n={n}")
        for t,a0,aM in zip(T,h0,hM):
            print(f"  {t[0]:10s} {t[1]:14s} diff {t[2]:+.4f} CI [{t[3]:+.4f},{t[4]:+.4f}] Holm p(>0) {a0:.3g} p(>0.03) {aM:.3g} -> {verdict(a0,aM)}")
        return T,h0,hM
    TB,h0B,hMB=contrast([kB(f) for f in FV],[f"f {f}" for f in FV],"PART B (verbatim rows, epsilon 1)")
    for a in inf:
        d0=[t[1] for t,x in zip(TB,h0B) if t[0]==a and x<ALPHA]; dM=[t[1] for t,x in zip(TB,hMB) if t[0]==a and x<ALPHA]
        print(f"  {a:10s} smallest verbatim share detected: {d0[0] if d0 else 'none in grid'}; smallest beyond the margin: {dM[0] if dM else 'none in grid'}")
    keysA=[kA(dv,f) for dv in DN for f in FN]; labsA=[f"d {dv} f {f}" for dv in DN for f in FN]
    TA,h0A,hMA=contrast(keysA,labsA,"PART A (noisy copies of members, Laplace noise SD/d)")
    print("\nPART A floor summary (per attack and noise divisor: smallest share detected / smallest share beyond the margin):")
    for a in inf:
        for dv in DN:
            d0=[t[1].split()[-1] for t,x in zip(TA,h0A) if t[0]==a and t[1].startswith(f"d {dv} ") and x<ALPHA]
            dM=[t[1].split()[-1] for t,x in zip(TA,hMA) if t[0]==a and t[1].startswith(f"d {dv} ") and x<ALPHA]
            print(f"  {a:10s} d {dv}: detected from f {d0[0] if d0 else 'none in grid'}; beyond the margin from f {dM[0] if dM else 'none in grid'}")
    # B2 epsilon comparison
    if RES15.exists() and list(RES15.glob(f"{cell}_w*.json")):
        R15=load(RES15,cell); i15={(r["world"],r["arm"]):r for r in R15}; W15=[w for w in W if (w,"clean_matched") in i15]
        if len(W15)>=MINW:
            Q=[]
            for a in inf:
                for f in FV:
                    d=np.array([(g(w,"clean_matched")[kB(f)][a]-g(w,"clean_matched")[kB("0")][a])-(i15[(w,"clean_matched")][f"{method}_eps10_f{f}"][a]-i15[(w,"clean_matched")][f"{method}_eps10_f0"][a]) for w in W15])
                    m,se,lo,hi,nn=ci(d); Q.append((a,f,m,lo,hi,p_eq(m,se,nn),p_sh(m,se,nn)))
            he=holm([q[5] for q in Q]); hs=holm([q[6] for q in Q])
            print(f"\nPART B2 (epsilon comparison), clean_matched: gain at epsilon 1 minus gain at epsilon 10 (V15), paired by world, margin +/-{MARGIN}, 90% CI, Holm over {len(Q)} tests, n={len(W15)}")
            for q,a_,b_ in zip(Q,he,hs):
                print(f"  {q[0]:10s} f {q[1]:>4s} diff {q[2]:+.4f} CI [{q[3]:+.4f},{q[4]:+.4f}] -> {'DIFFERENT beyond the margin' if b_<ALPHA else ('equivalent within the margin' if a_<ALPHA else 'inconclusive')}")
        else: print("\nPART B2: fewer than the minimum number of V15 worlds in common; not run.")
    else: print("\nPART B2: V15 results not found; not run.")
    S=[]
    for f in ["0"]+FV:
        for a in inf:
            d=np.array([g(w,"contaminated")[kB(f)][a]-g(w,"clean_matched")[kB(f)][a] for w in W]); m,se,lo,hi,nn=ci(d); S.append((f,a,m,lo,hi,p_eq(m,se,nn),p_sh(m,se,nn)))
    he=holm([s[5] for s in S]); hs=holm([s[6] for s in S])
    print(f"\nSECONDARY: contaminated minus clean_matched at each verbatim share f, margin +/-{MARGIN}, 90% CI, Holm over {len(S)} tests")
    for s,a_,b_ in zip(S,he,hs):
        print(f"  f {s[0]:>4s} {s[1]:10s} diff {s[2]:+.4f} CI [{s[3]:+.4f},{s[4]:+.4f}] -> {'SHIFT beyond the margin' if b_<ALPHA else ('equivalent within the margin' if a_<ALPHA else 'inconclusive')}")
