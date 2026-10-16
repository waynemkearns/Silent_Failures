"""Pre-specified analysis for V15 (see ../../25_FROZEN_DESIGN_V15.md). Prints verdicts; no free choices.
Sensitivity test: a known share f of the released rows is replaced by real member records, on MWEM and PrivBayes-style releases at epsilon 10.
Cells adult_mwem, mimic_mwem, adult_pb, mimic_pb; three standard arms; minimum 30 worlds per cell. Each cell has its own Holm families.
Detection contrast (primary), clean_matched arm: AUC at share f minus AUC at share 0, paired by world, for each informative attack and each f > 0.
  'detected' if the Holm-adjusted one-sided p for 'increase > 0' is below 0.05; 'beyond the margin' if the Holm-adjusted one-sided p for 'increase > 0.03' is below 0.05.
Secondary: contaminated minus clean_matched at each f (equivalence within +/-0.03, Holm over attacks x f), and the AUC gain per unit f."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; MINW=int(os.environ.get("V15_MIN_WORLDS","30")); TEST_MODE="V15_MIN_WORLDS" in os.environ
STD=["clean_full","clean_matched","contaminated"]; ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]; FGRID=["0.05","0.1","0.25"]
H=Path(__file__).resolve().parent; RES=Path(sys.argv[1]) if len(sys.argv)>1 else H/"results"
def load(cell):
    R=[]
    for f in sorted(RES.glob(f"{cell}_w*.json")): R+=json.load(open(f))["results"]
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
for cell in ("adult_mwem","mimic_mwem","adult_pb","mimic_pb"):
    method=cell.split("_")[1]; key=lambda f:f"{method}_eps10_f{f}"
    print("\n"+"="*72+"\nCELL",cell,f"({'MWEM' if method=='mwem' else 'PrivBayes-style'} release at epsilon 10, share f of rows replaced by real member records)")
    R=load(cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in STD]; ro_ok=all(.45<=x<=.55 for x in ro)
    print("records-only means (clean_full, clean_matched, contaminated)",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    inf=[]
    for a in ATT:
        pos=[np.mean([g(w,arm)["lap_eps100"][a] for w in W]) for arm in STD]; pl=[np.mean([g(w,arm)[f"plc_{method}_eps10"][a] for w in W]) for arm in STD]
        okp=min(pos)>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{a:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means (f=0) {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: inf.append(a)
    print("informative attacks:",inf)
    print("Mean AUC by arm and share f (all attacks, descriptive):")
    for arm in STD:
        for f in ["0"]+FGRID: print(f"  {arm:14s} f {f:>4s}",{a:round(float(np.mean([g(w,arm)[key(f)][a] for w in W])),3) for a in ATT})
    if not ro_ok or not inf: print("Gates not met: no sensitivity claim for this cell."); continue
    T=[]
    for a in inf:
        for f in FGRID:
            d=np.array([g(w,"clean_matched")[key(f)][a]-g(w,"clean_matched")[key("0")][a] for w in W]); m,se,lo,hi,nn=ci(d); T.append((a,f,m,lo,hi,p_gt(m,se,nn,0.0),p_gt(m,se,nn,MARGIN)))
    h0=holm([t[5] for t in T]); hM=holm([t[6] for t in T])
    print(f"\nPRIMARY (detection), clean_matched arm: AUC at share f minus AUC at f=0, paired, 90% CI, Holm over {len(T)} tests, n={n}")
    first0={}; firstM={}
    for t,a0,aM in zip(T,h0,hM):
        v="BEYOND the 0.03 margin" if aM<ALPHA else ("detected (increase > 0)" if a0<ALPHA else "not detected")
        print(f"  {t[0]:10s} f {t[1]:>4s} diff {t[2]:+.4f} CI [{t[3]:+.4f},{t[4]:+.4f}] Holm p(>0) {a0:.3g} p(>0.03) {aM:.3g} -> {v}; gain per unit f {t[2]/float(t[1]):.2f}")
        if a0<ALPHA: first0.setdefault(t[0],t[1])
        if aM<ALPHA: firstM.setdefault(t[0],t[1])
    for a in inf: print(f"  {a:10s} smallest share detected: {first0.get(a,'none in grid')}; smallest share beyond the margin: {firstM.get(a,'none in grid')}")
    S=[]
    for f in ["0"]+FGRID:
        for a in inf:
            d=np.array([g(w,"contaminated")[key(f)][a]-g(w,"clean_matched")[key(f)][a] for w in W]); m,se,lo,hi,nn=ci(d); S.append((f,a,m,lo,hi,p_eq(m,se,nn),p_sh(m,se,nn)))
    he=holm([s[5] for s in S]); hs=holm([s[6] for s in S])
    print(f"\nSECONDARY: contaminated minus clean_matched at each share f, margin +/-{MARGIN}, 90% CI, Holm over {len(S)} tests")
    for s,a_,b_ in zip(S,he,hs):
        v="SHIFT beyond the margin" if b_<ALPHA else ("equivalent within the margin" if a_<ALPHA else "inconclusive")
        print(f"  f {s[0]:>4s} {s[1]:10s} diff {s[2]:+.4f} CI [{s[3]:+.4f},{s[4]:+.4f}] -> {v}")
