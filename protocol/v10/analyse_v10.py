"""Pre-specified analysis for V10 (see ../../17_FROZEN_DESIGN_V10.md). Prints verdicts; no free choices."""
import json,glob,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; ARMS=["clean_full","clean_matched","contaminated"]
ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]
CELLS={"adult_laplace":dict(min_worlds=100,tests=["lap_eps1"],plc=["plc_lap_eps1","plc_lap_eps100"]),
       "adult_mst":dict(min_worlds=30,tests=["mst_eps1","mst_eps10","mst_eps100"],plc=["plc_mst_eps1","plc_mst_eps10","plc_mst_eps100"]),
       "mimic_mst":dict(min_worlds=30,tests=["mst_eps1","mst_eps10","mst_eps100"],plc=["plc_mst_eps1","plc_mst_eps10","plc_mst_eps100"])}
RES=Path(sys.argv[1]) if len(sys.argv)>1 else Path(__file__).parent/"results"
for cell,spec in CELLS.items():
    print("\n"+"="*70+"\nCELL",cell)
    R=[]
    for f in sorted(RES.glob(f"{cell}_w*.json")):
        d=json.load(open(f)); R+=d["results"]
    if any(r.get("fake_mst") for r in R): print("REFUSED: fake-MST results present"); continue
    W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,"(minimum",spec["min_worlds"],")")
    st=RES/f"{cell}_STATUS.txt"
    if st.exists(): print("status file:",st.read_text().strip())
    if n<spec["min_worlds"]: print("INSUFFICIENT WORLDS: no equivalence claim for this cell"); continue
    g=lambda w,a:next(r for r in R if r["world"]==w and r["arm"]==a)
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in ARMS]; ro_ok=all(.45<=x<=.55 for x in ro)
    print("records-only means",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    informative=[]
    for att in ATT:
        pos=[np.mean([g(w,a)["lap_eps100"][att] for w in W]) for a in ARMS]
        pl=[np.mean([g(w,a)[k][att] for w in W]) for a in ARMS for k in spec["plc"]]
        okp=min(pos)>0.80; okl=all(.47<=x<=.53 for x in pl)
        print(f"{att:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'}")
        if okp and okl: informative.append(att)
    print("informative attacks:",informative)
    if not ro_ok or not informative: print("No equivalence claim possible for this cell."); continue
    pairs=[(att,t) for t in spec["tests"] for att in informative]; res=[]
    for att,t in pairs:
        d=np.array([g(w,"contaminated")[t][att]-g(w,"clean_matched")[t][att] for w in W]); m=d.mean(); se=d.std(ddof=1)/np.sqrt(n)
        p=max(1-stats.t.cdf((m+MARGIN)/se,n-1),stats.t.cdf((m-MARGIN)/se,n-1)); tc=stats.t.ppf(1-ALPHA,n-1)
        res.append(dict(att=att,t=t,m=m,lo=m-tc*se,hi=m+tc*se,p=p,pos=int((d>0).sum())))
    order=sorted(range(len(res)),key=lambda i:res[i]["p"]); k=len(res); run=0
    for rank,i in enumerate(order): run=max(run,min(1,res[i]["p"]*(k-rank))); res[i]["holm"]=run
    print(f"EQUIVALENCE contaminated minus clean_matched, margin +/-{MARGIN}, n={n}")
    for r in res:
        v="EQUIVALENT within margin" if r["holm"]<ALPHA else ("DIFFERENCE larger than margin" if (r["lo"]>MARGIN or r["hi"]<-MARGIN) else "NOT shown equivalent")
        print(f"{r['t']:10s} {r['att']:12s} diff {r['m']:+.4f} 90% CI [{r['lo']:+.4f},{r['hi']:+.4f}] Holm p {r['holm']:.4f} -> {v}; positive in {r['pos']}/{n}")
    print("Secondary (descriptive) matched minus full:")
    for att,t in pairs:
        d=np.array([g(w,"clean_matched")[t][att]-g(w,"clean_full")[t][att] for w in W]); print(f"{t:10s} {att:12s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
