"""Pre-specified analysis for V17 (see ../../27_FROZEN_DESIGN_V17.md). Prints verdicts; no free choices.
Question: when one pipeline slip (P1, P2, P4a, P4b, P5, P6, asymmetric or symmetric) is injected, does the audit still flag a planted leak, and does it raise a false alarm when there is none?
Release: PrivBayes-style at epsilon 10, then a planted leak: verbatim member rows at share 0.10 and 0.25, noisy copies (Laplace noise SD/4) at share 0.25, or nothing (f = 0).
Cells adult_c and mimic_c; minimum 30 worlds per cell; each cell has its own Holm families. A verdict per arm, variant and informative attack is made from the mean AUC over worlds minus 0.5:
  FLAGGED if one-sided 'AUC - 0.5 > 0.03' (Holm); INVERTED if one-sided 'AUC - 0.5 < -0.03' (Holm); clear if equivalence within +/-0.03 (Holm); otherwise inconclusive."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; MINW=int(os.environ.get("V17_MIN_WORLDS","30")); TEST_MODE="V17_MIN_WORLDS" in os.environ
ATT=["DCR","DCRDiff","KDEratio"]; VARS=["0","0.1","0.25","nc_d4_f0.25"]; LEAK=VARS[1:]
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
    n=len(d); m=float(d.mean()); se=max(float(d.std(ddof=1)/np.sqrt(n)),1e-12); return m,se,n
def p_flag(m,se,n): return float(1-stats.t.cdf((m-MARGIN)/se,n-1))
def p_inv(m,se,n): return float(stats.t.cdf((m+MARGIN)/se,n-1))
def p_clr(m,se,n): return float(max(1-stats.t.cdf((m+MARGIN)/se,n-1),stats.t.cdf((m-MARGIN)/se,n-1)))
def ci90(d):
    n=len(d); m=float(d.mean()); se=max(float(d.std(ddof=1)/np.sqrt(n)),1e-12); tc=stats.t.ppf(1-ALPHA,n-1); return m-tc*se,m+tc*se
for cell in ("adult_c","mimic_c"):
    print("\n"+"="*72+"\nCELL",cell,"(PrivBayes-style release at epsilon 10 with a planted leak; Laplace near-copy positive control on the clean arm)")
    R=load(cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]; ARMS=sorted({r["arm"] for r in R},key=lambda a:(a!="clean",a))
    ro=float(np.mean([g(w,"clean")["records_only_oof"] for w in W])); ro_ok=.45<=ro<=.55; print(f"clean arm records-only mean {ro:.3f}","PASS" if ro_ok else "FAIL")
    inf=[]
    for a in ATT:
        pos=float(np.mean([g(w,"clean")["lap100"][a] for w in W])); pl=float(np.mean([g(w,"clean")["plc"]["0"][a] for w in W])); okp=pos>0.80; okl=.47<=pl<=.53
        print(f"{a:9s} positive control (Laplace divisor 100) {pos:.3f} {'PASS' if okp else 'FAIL'} | placebo mean at f=0 {pl:.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: inf.append(a)
    print("informative attacks:",inf)
    if not ro_ok or not inf: print("Gates not met: no claim for this cell."); continue
    keys=[(arm,var,a) for a in inf for arm in ARMS for var in VARS]; Z=[]
    for arm,var,a in keys:
        auc=np.array([g(w,arm)["pb"][var][a] for w in W]); m,se,nn=stat(auc-0.5); Z.append((m,se,nn,float(auc.mean())))
    hf=holm([p_flag(*z[:3]) for z in Z]); hi=holm([p_inv(*z[:3]) for z in Z]); hc=holm([p_clr(*z[:3]) for z in Z])
    V={}
    for k,z,a1,a2,a3 in zip(keys,Z,hf,hi,hc): V[k]="FLAGGED" if a1<ALPHA else ("INVERTED" if a2<ALPHA else ("clear" if a3<ALPHA else "inconclusive")); 
    MEAN={k:z[3] for k,z in zip(keys,Z)}
    print(f"\nVERDICT GRID (mean AUC over {n} worlds; verdict from Holm-corrected tests against the 0.03 margin around 0.5; {len(keys)} tests per family)")
    for a in inf:
        print(f"\n  attack {a}")
        print("  "+"arm".ljust(10)+"".join(v.ljust(24) for v in VARS))
        for arm in ARMS: print("  "+arm.ljust(10)+"".join(f"{MEAN[(arm,v,a)]:.3f} {V[(arm,v,a)]}".ljust(24) for v in VARS))
    print("\nOUTCOMES for pattern arms (clean verdict is the reference)")
    for a in inf:
        sens={v:V[("clean",v,a)]=="FLAGGED" for v in LEAK}; print(f"\n  attack {a}: clean arm flags the leak at"," ".join(f"{v}={'yes' if s else 'NO'}" for v,s in sens.items()))
        for arm in ARMS[1:]:
            out=[]
            for v in LEAK:
                if not sens[v]: out.append(f"{v}: not interpretable (clean arm does not flag)"); continue
                out.append(f"{v}: "+("leak kept" if V[(arm,v,a)]=="FLAGGED" else f"LEAK MISSED ({V[(arm,v,a)]})"))
            fa=("FALSE ALARM" if (V[("clean","0",a)]!="FLAGGED" and V[(arm,"0",a)]=="FLAGGED") else "no false alarm")
            print(f"    {arm:9s} f0: {fa} | "+" | ".join(out))
    print("\nPAIRED SHIFT (descriptive): arm minus clean AUC at the same variant, 90% CI")
    for a in inf:
        for arm in ARMS[1:]:
            parts=[]
            for v in VARS:
                d=np.array([g(w,arm)["pb"][v][a]-g(w,"clean")["pb"][v][a] for w in W]); lo,hi=ci90(d); parts.append(f"{v} {d.mean():+.3f} [{lo:+.3f},{hi:+.3f}]")
            print(f"  {a:9s} {arm:9s} "+"; ".join(parts))
    print("\nPER-WORLD FLAG RATE (descriptive): share of worlds with AUC above 0.53")
    for a in inf:
        for arm in ARMS: print(f"  {a:9s} {arm:9s} "+" ".join(f"{v}:{np.mean([g(w,arm)['pb'][v][a]>0.53 for w in W]):.2f}" for v in VARS))
    print("\nRECORDS-ONLY BASELINE by arm (mean over worlds; above 0.55 is a separate alarm that the audit reports on its own)")
    print("  "+" ".join(f"{arm}:{np.mean([g(w,arm)['records_only_oof'] for w in W]):.3f}" for arm in ARMS))
    print("PLACEBO mean at f=0 by arm and attack (flag if outside 0.47 to 0.53):")
    for a in inf: print("  "+a.ljust(9)+" ".join(f"{arm}:{np.mean([g(w,arm)['plc']['0'][a] for w in W]):.3f}" for arm in ARMS))
