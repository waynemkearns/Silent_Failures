"""Pre-specified analysis for V13 (see ../../22_FROZEN_DESIGN_V13.md). Prints verdicts; no free choices.
Per pattern (P1, P2, P4a, P4b, P5, P6), applied to members only (asym) or to members, holdout and reference (sym), compared with the clean arm,
paired by world, for DCR, DCRDiff and KDE-ratio at three Laplace divisors, plus the records-only baseline (descriptive)."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; CEIL=0.97
MINW=int(os.environ.get("V13_MIN_WORLDS","50")); TEST_MODE="V13_MIN_WORLDS" in os.environ
ATT=["DCR","DCRDiff","KDEratio"]; DIVS=["1","2","4"]
H=Path(__file__).resolve().parent; RES=Path(sys.argv[1]) if len(sys.argv)>1 else H/"results"
PATS={"mimic":["P1","P2","P4a","P4b","P5","P6"],"adult":["P2","P4a","P4b","P5","P6"]}

def load(cell):
    R=[]
    for f in sorted(RES.glob(f"{cell}_w*.json")): R+=json.load(open(f))["results"]
    return R
def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]); k=len(ps); run=0; out=[0]*k
    for rank,i in enumerate(order): run=max(run,min(1,ps[i]*(k-rank))); out[i]=run
    return out
def stat(d):
    n=len(d); m=float(d.mean()); se=float(d.std(ddof=1)/np.sqrt(n)); tc=stats.t.ppf(1-ALPHA,n-1)
    if se==0: se=1e-12
    p_lo=1-stats.t.cdf((m+MARGIN)/se,n-1)      # H0: d <= -margin
    p_hi=stats.t.cdf((m-MARGIN)/se,n-1)        # H0: d >= +margin
    p_up=1-stats.t.cdf((m-MARGIN)/se,n-1)      # H0: d <= +margin
    p_dn=stats.t.cdf((m+MARGIN)/se,n-1)        # H0: d >= -margin
    return dict(m=m,lo=m-tc*se,hi=m+tc*se,p_eq=max(p_lo,p_hi),p_shift=min(p_up,p_dn),dirn="up" if m>0 else "down")

for cell in ("adult_pat","mimic_pat"):
    ds=cell.split("_")[0]; print("\n"+"="*72+"\nCELL",cell,"(Laplace-perturbed records, NOT epsilon-DP)")
    R=load(cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]
    arms=sorted({r["arm"] for r in R}); print("common member count per world: min",min(g(w,"clean")["n_members"] for w in W),"median",int(np.median([g(w,"clean")["n_members"] for w in W])))
    ro=np.mean([g(w,"clean")["records_only_oof"] for w in W]); ro_ok=.45<=ro<=.55
    print(f"clean arm records-only mean {ro:.3f}","PASS" if ro_ok else "FAIL")
    inf=[]
    for a in ATT:
        pos=np.mean([g(w,"clean")["lap"]["100"][a] for w in W]); pl=[np.mean([g(w,"clean")["plc"][dv][a] for w in W]) for dv in DIVS+["100"]]
        okp=pos>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{a:9s} positive control (divisor 100) {pos:.3f} {'PASS' if okp else 'FAIL'} | clean placebo means {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'} | clean AUC by divisor",
              {dv:round(float(np.mean([g(w,'clean')['lap'][dv][a] for w in W])),3) for dv in DIVS})
        if okp and okl: inf.append(a)
    print("informative attacks:",inf)
    if not ro_ok or not inf: print("Gates not met on the clean arm: no claim about any pattern for this cell."); continue
    tests=[]
    for p in PATS[ds]:
        for f in ("asym","sym"):
            arm=f"{p}_{f}"
            for a in inf:
                for dv in DIVS:
                    cm=float(np.mean([g(w,"clean")["lap"][dv][a] for w in W]))
                    d=np.array([g(w,arm)["lap"][dv][a]-g(w,"clean")["lap"][dv][a] for w in W]); s=stat(d)
                    tests.append(dict(p=p,f=f,a=a,dv=dv,cm=cm,ceil=cm>CEIL,pos=int((d>0).sum()),**s))
    live=[t for t in tests if not t["ceil"]]
    for key,nm in (("p_eq","heq"),("p_shift","hsh")):
        hp=holm([t[key] for t in live])
        for t,h in zip(live,hp): t[nm]=h
    def verdict(t):
        if t["ceil"]: return "ceiling (clean AUC above 0.97), not tested"
        if t["hsh"]<ALPHA: return f"SHIFT beyond the margin ({t['dirn']})"
        if t["heq"]<ALPHA: return "equivalent within the margin"
        return "inconclusive"
    print(f"\nTests: {len(live)} (Holm over these, separately for equivalence and for shift). Margin +/-{MARGIN}, 90% CI of the paired mean difference, arm minus clean, n={n}")
    for p in PATS[ds]:
        for f in ("asym","sym"):
            arm=f"{p}_{f}"; rod=np.array([g(w,arm)["records_only_oof"]-g(w,"clean")["records_only_oof"] for w in W]); s=stat(rod)
            plm=float(np.mean([g(w,arm)["plc"][dv][a] for w in W for a in inf for dv in DIVS]))
            print(f"\n{arm}: records-only baseline {np.mean([g(w,arm)['records_only_oof'] for w in W]):.3f} (diff {s['m']:+.3f}, 90% CI [{s['lo']:+.3f},{s['hi']:+.3f}]); placebo mean over tests {plm:.3f}{'' if .47<=plm<=.53 else '  OUTSIDE 0.47-0.53'}; members available {int(np.median([g(w,arm)['n_mem_avail'] for w in W]))}, holdout {int(np.median([g(w,arm)['n_nm_avail'] for w in W]))} (median)")
            for t in tests:
                if t["p"]==p and t["f"]==f:
                    print(f"  {t['a']:9s} div {t['dv']:>2s}  clean {t['cm']:.3f}  diff {t['m']:+.4f} CI [{t['lo']:+.4f},{t['hi']:+.4f}]  "+verdict(t)+(f"  Holm eq {t['heq']:.3g} shift {t['hsh']:.3g}" if not t['ceil'] else ""))
    print("\nDANGER TABLE (descriptive): largest absolute mean shift in AUC over the tested attacks and divisors, and the records-only shift. Sorted by distance-attack shift.")
    rows=[]
    for p in PATS[ds]:
        for f in ("asym","sym"):
            ts=[t for t in live if t["p"]==p and t["f"]==f]
            if not ts: continue
            b=max(ts,key=lambda t:abs(t["m"])); rod=np.mean([g(w,f"{p}_{f}")["records_only_oof"]-g(w,"clean")["records_only_oof"] for w in W])
            rows.append((abs(b["m"]),f"{p}_{f}",b,rod,sum(1 for t in ts if t["hsh"]<ALPHA),len(ts)))
    for _,arm,b,rod,k,m in sorted(rows,reverse=True): print(f"  {arm:10s} max |shift| {abs(b['m']):.3f} ({b['a']}, div {b['dv']}, {b['m']:+.3f})  records-only shift {rod:+.3f}  tests with SHIFT beyond margin {k}/{m}")
