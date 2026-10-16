"""Pre-specified analysis for V12 (see ../../21_FROZEN_DESIGN_V12.md). Prints verdicts; no free choices.
Part A: asymmetric preparation, Laplace-perturbed records, adult_asym and mimic_asym (minimum 100 worlds).
Part B: scaler isolation, same files, descriptive only.
Part C: asymmetric preparation, MST, adult_mstasym and mimic_mstasym (minimum 30 worlds), compared with the V11 results of the same worlds."""
import json,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05
STD=["clean_full","clean_matched","contaminated"]; MM="contaminated_mismatched"
ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]; ATT3=["DCR","DCRDiff","KDEratio"]
H=Path(__file__).resolve().parent; RES=Path(sys.argv[1]) if len(sys.argv)>1 else H/"results"; V10RES=H.parent/"v10"/"results"

def load(res,cell):
    R=[]
    for f in sorted(res.glob(f"{cell}_w*.json")): R+=json.load(open(f))["results"]
    return R
def getter(R): return lambda w,a:next(r for r in R if r["world"]==w and r["arm"]==a)

def gates(R,W,g,plc_keys,label):
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in STD]; ro_ok=all(.45<=x<=.55 for x in ro)
    print(f"{label} records-only means (clean_full, clean_matched, contaminated)",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    informative=[]
    for att in ATT:
        pos=[np.mean([g(w,a)["lap_eps100"][att] for w in W]) for a in STD]
        pl=[np.mean([g(w,a)[k][att] for w in W]) for a in STD for k in plc_keys]
        okp=min(pos)>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{att:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: informative.append(att)
    print("informative attacks:",informative); return ro_ok,informative

def contrast(d):
    n=len(d); m=d.mean(); se=d.std(ddof=1)/np.sqrt(n); tc=stats.t.ppf(1-ALPHA,n-1)
    return m,m-tc*se,m+tc*se,1-stats.t.cdf((m-MARGIN)/se,n-1),int((d>0).sum())

def holm(ps):
    order=sorted(range(len(ps)),key=lambda i:ps[i]); k=len(ps); run=0; out=[0]*k
    for rank,i in enumerate(order): run=max(run,min(1,ps[i]*(k-rank))); out[i]=run
    return out

def verdict(lo,hi,hp):
    if hp<ALPHA: return "SHIFT larger than the margin"
    if lo>0: return "positive shift, not shown larger than the margin"
    if hi<-MARGIN: return "NEGATIVE shift larger than the margin"
    return "no shift shown"

def describe_mm(R,W,g,tests,plc_keys):
    print(f"Mismatched arm, descriptive (members from the contaminated pool, holdout and reference prepared as clean), n={len(W)}")
    print("  records-only mean:",f"{np.mean([g(w,MM)['records_only_oof'] for w in W]):.3f}")
    for t in tests:
        print(f"  {t:10s} mean AUC by attack:",{a:round(float(np.mean([g(w,MM)[t][a] for w in W])),3) for a in ATT})
    for k in plc_keys:
        print(f"  {k:14s} placebo mean AUC:",{a:round(float(np.mean([g(w,MM)[k][a] for w in W])),3) for a in ATT})
    print("  positive control lap_eps100:",{a:round(float(np.mean([g(w,MM)['lap_eps100'][a] for w in W])),3) for a in ATT})

# ---------- Part A and B ----------
for cell in ("adult_asym","mimic_asym"):
    print("\n"+"="*70+"\nCELL",cell,"(Laplace-perturbed records; Part A and Part B)")
    R=load(RES,cell)
    if any(r.get("fake_mst") for r in R): print("REFUSED: fake results present"); continue
    W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,"(minimum 100)")
    if n<100: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    g=getter(R); plc=["plc_lap_eps1","plc_lap_eps100"]
    ro_ok,inf=gates(R,W,g,plc,"standard arms")
    describe_mm(R,W,g,["lap_eps1"],["plc_lap_eps1","plc_lap_eps100"])
    print("  records-only, mismatched minus contaminated (matched):",f"{np.mean([g(w,MM)['records_only_oof']-g(w,'contaminated')['records_only_oof'] for w in W]):+.3f}")
    if not ro_ok or not inf: print("Part A: gates not met on the standard arms; no claim about the shift for this cell.")
    else:
        print(f"PART A: mismatched minus contaminated (matched), lap_eps1, H0: difference <= +{MARGIN}, one-sided, Holm over {len(inf)} attacks, 90% CI")
        res=[]
        for att in inf:
            d=np.array([g(w,MM)["lap_eps1"][att]-g(w,"contaminated")["lap_eps1"][att] for w in W]); res.append((att,)+contrast(d))
        hp=holm([r[4] for r in res])
        for r,h in zip(res,hp): print(f"lap_eps1   {r[0]:12s} diff {r[1]:+.4f} 90% CI [{r[2]:+.4f},{r[3]:+.4f}] Holm p {h:.4f} -> {verdict(r[2],r[3],h)}; positive in {r[5]}/{n}")
        print("Secondary (descriptive) mismatched minus clean_matched:")
        for att in inf:
            d=np.array([g(w,MM)["lap_eps1"][att]-g(w,"clean_matched")["lap_eps1"][att] for w in W]); print(f"lap_eps1   {att:12s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
    print("PART B (descriptive, no gates): scaler isolation at divisor 1, three attacks. Size = clean_matched minus clean_full. Selection = contaminated minus clean_matched.")
    print("  S1 arm-fitted on members (submitted), S2 reference-fitted (repaired), S3 fixed (20,000 rows of the full file, same encoder). Mean diff, 90% CI, positive count.")
    for att in ATT3:
        for lab,(a,b) in (("size",("clean_matched","clean_full")),("selection",("contaminated","clean_matched"))):
            out=[]
            for s in ("S1","S2","S3"):
                val=lambda w,x:(g(w,x)["lap_eps1"][att] if s=="S2" else g(w,x)["scaler"][s][att])
                d=np.array([val(w,a)-val(w,b) for w in W]); m,lo,hi,_,pos=contrast(d); out.append(f"{s} {m:+.4f} [{lo:+.4f},{hi:+.4f}] {pos}/{n}")
            print(f"  {att:9s} {lab:9s} "+" | ".join(out))

# ---------- Part C ----------
for cell,base in (("adult_mstasym","adult_mst"),("mimic_mstasym","mimic_mst")):
    print("\n"+"="*70+"\nCELL",cell,"(MST, epsilon 1 and 10; compared with V11 cell",base+")")
    A=load(RES,cell); B=load(V10RES,base)
    if any(r.get("fake_mst") for r in A+B): print("REFUSED: fake-MST results present"); continue
    WA={r["world"] for r in A}; WB={r["world"] for r in B}
    if len(WB)<30: print(f"V11 cell {base} has only {len(WB)} worlds (minimum 30): no gates, no claim"); continue
    ga=getter(A); gb=getter(B); WBs=sorted(WB); print(f"V11 worlds {len(WBs)}, V12 worlds {len(WA)}")
    ro_ok,inf=gates(B,WBs,gb,["plc_mst_eps1","plc_mst_eps10","plc_mst_eps100"],"V11 standard arms")
    W=sorted(WA&WB); n=len(W); print("worlds with both V11 and V12 results:",n,"(minimum 30)")
    if n<30: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    tests=["mst_eps1","mst_eps10"]; plc=["plc_mst_eps1","plc_mst_eps10"]
    describe_mm(A,W,ga,tests,plc)
    if not ro_ok or not inf: print("Gates not met in the V11 cell; no claim about the shift."); continue
    print(f"PART C: mismatched minus contaminated (matched, from V11), H0: difference <= +{MARGIN}, one-sided, Holm over {len(inf)*len(tests)} tests, 90% CI, n={n}")
    res=[]
    for t in tests:
        for att in inf:
            d=np.array([ga(w,MM)[t][att]-gb(w,"contaminated")[t][att] for w in W]); res.append((t,att)+contrast(d))
    hp=holm([r[5] for r in res])
    for r,h in zip(res,hp): print(f"{r[0]:10s} {r[1]:12s} diff {r[2]:+.4f} 90% CI [{r[3]:+.4f},{r[4]:+.4f}] Holm p {h:.4f} -> {verdict(r[3],r[4],h)}; positive in {r[6]}/{n}")
    print("Secondary (descriptive) mismatched minus clean_matched (V11):")
    for t in tests:
        for att in inf:
            d=np.array([ga(w,MM)[t][att]-gb(w,"clean_matched")[t][att] for w in W]); print(f"{t:10s} {att:12s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
