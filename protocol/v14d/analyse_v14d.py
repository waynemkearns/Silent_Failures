"""Pre-specified analysis for V14D, Part D (see ../../24_FROZEN_DESIGN_V14D.md). Prints verdicts; no free choices.
PrivBayes-style synthesizer (DataSynthesizer 0.1.13, publicly binned data) at epsilon 1 and 10 on Adult and MIMIC-IV, three standard arms, minimum 30 worlds per cell.
Each cell is analysed on its own, with its own Holm family.
Primary contrast: contaminated minus clean_matched (selection effect), paired by world, for each informative attack and epsilon.
Secondary, descriptive: clean_matched minus clean_full (size effect)."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; MINW=int(os.environ.get("V14_MIN_WORLDS","30")); TEST_MODE="V14_MIN_WORLDS" in os.environ
STD=["clean_full","clean_matched","contaminated"]; ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]; METHODS={"pb":["1","10"]}
H=Path(__file__).resolve().parent; RES=Path(sys.argv[1]) if len(sys.argv)>1 else H/"results"
def load(cell):
    R=[]
    for f in sorted(RES.glob(f"{cell}_w*.json")): R+=json.load(open(f))["results"]
    return R
def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]); k=len(ps); run=0; out=[0]*k
    for rank,i in enumerate(order): run=max(run,min(1,ps[i]*(k-rank))); out[i]=run
    return out
def stat(d):
    n=len(d); m=float(d.mean()); se=max(float(d.std(ddof=1)/np.sqrt(n)),1e-12); tc=stats.t.ppf(1-ALPHA,n-1)
    p_eq=max(1-stats.t.cdf((m+MARGIN)/se,n-1),stats.t.cdf((m-MARGIN)/se,n-1)); p_sh=min(1-stats.t.cdf((m-MARGIN)/se,n-1),stats.t.cdf((m+MARGIN)/se,n-1))
    return dict(m=m,lo=m-tc*se,hi=m+tc*se,p_eq=p_eq,p_sh=p_sh)
for cell in ("adult_pb","mimic_pb"):
    method=cell.split("_")[1]; EPS=METHODS[method]
    print("\n"+"="*72+"\nCELL",cell,f"({method.upper()}, publicly binned data; epsilon {' and '.join(EPS)})")
    R=load(cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in STD]; ro_ok=all(.45<=x<=.55 for x in ro)
    print("records-only means (clean_full, clean_matched, contaminated)",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    inf=[]
    for a in ATT:
        pos=[np.mean([g(w,arm)["lap_eps100"][a] for w in W]) for arm in STD]; pl=[np.mean([g(w,arm)[f"plc_{method}_eps{e}"][a] for w in W]) for arm in STD for e in EPS]
        okp=min(pos)>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{a:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: inf.append(a)
    print("informative attacks:",inf)
    print(method.upper(),"mean AUC by arm and epsilon (all attacks, descriptive):")
    for arm in STD:
        for e in EPS: print(f"  {arm:14s} eps {e:>2s}",{a:round(float(np.mean([g(w,arm)[f'{method}_eps{e}'][a] for w in W])),3) for a in ATT})
    if not ro_ok or not inf: print("Gates not met: no equivalence claim for this cell."); continue
    tests=[]
    for e in EPS:
        for a in inf:
            d=np.array([g(w,"contaminated")[f"{method}_eps{e}"][a]-g(w,"clean_matched")[f"{method}_eps{e}"][a] for w in W]); tests.append((e,a,stat(d),int((d>0).sum())))
    he=holm([t[2]["p_eq"] for t in tests]); hs=holm([t[2]["p_sh"] for t in tests])
    print(f"\nPRIMARY: contaminated minus clean_matched, margin +/-{MARGIN}, 90% CI, Holm over {len(tests)} tests, n={n}")
    for t,a_,b_ in zip(tests,he,hs):
        s=t[2]; v="SHIFT beyond the margin" if b_<ALPHA else ("equivalent within the margin" if a_<ALPHA else "inconclusive")
        print(f"  eps {t[0]:>2s} {t[1]:10s} diff {s['m']:+.4f} CI [{s['lo']:+.4f},{s['hi']:+.4f}] Holm eq {a_:.3g} shift {b_:.3g} -> {v}; positive in {t[3]}/{n}")
    print("SECONDARY (descriptive): clean_matched minus clean_full")
    for e in EPS:
        for a in inf:
            d=np.array([g(w,"clean_matched")[f"{method}_eps{e}"][a]-g(w,"clean_full")[f"{method}_eps{e}"][a] for w in W]); print(f"  eps {e:>2s} {a:10s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
