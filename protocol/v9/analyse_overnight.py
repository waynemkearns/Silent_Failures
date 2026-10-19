"""Pre-specified analysis for the V9 powered design (see ../16_FROZEN_DESIGN_V9.md). Prints a verdict; no free choices."""
import json,glob,sys,numpy as np
from scipy import stats
MARGIN=0.03; ALPHA=0.05; ARMS=["clean_full","clean_matched","contaminated"]
ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]
R=[]
for f in sorted(glob.glob(str(__import__('pathlib').Path(__file__).parent/"results"/"v2_ov_reference_worlds_*.json"))): R+=json.load(open(f))["results"]
W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n)
g=lambda w,a:next(r for r in R if r["world"]==w and r["arm"]==a)
# Control gates (fixed in advance)
print("\nCONTROLS")
ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in ARMS]; print("records-only means",np.round(ro,3),"PASS" if all(.45<=x<=.55 for x in ro) else "FAIL")
informative=[]
for att in ATT:
    pos=[np.mean([g(w,a)["eps100"][att] for w in W]) for a in ARMS]
    pl=[np.mean([g(w,a)[k][att] for w in W]) for a in ARMS for k in ("placebo_eps1","placebo_eps100")]
    ok_pos=min(pos)>0.80; ok_pl=all(.47<=x<=.53 for x in pl)
    print(f"{att:18s} positive(eps100) min-arm mean {min(pos):.3f} {'PASS' if ok_pos else 'FAIL'} | placebo means {min(pl):.3f}-{max(pl):.3f} {'PASS' if ok_pl else 'FAIL'}")
    if ok_pos and ok_pl: informative.append(att)
print("informative attacks (both controls pass):",informative)
# Primary: contaminated minus matched at eps 1, TOST with Holm over informative attacks
print(f"\nEQUIVALENCE (contaminated minus clean_matched, eps 1, margin +/-{MARGIN}, n={n} paired worlds)")
res=[]
for att in informative:
    d=np.array([g(w,"contaminated")["eps1"][att]-g(w,"clean_matched")["eps1"][att] for w in W]); m=d.mean(); se=d.std(ddof=1)/np.sqrt(n)
    p_lo=1-stats.t.cdf((m+MARGIN)/se,n-1); p_hi=stats.t.cdf((m-MARGIN)/se,n-1); p=max(p_lo,p_hi); res.append((att,m,se,p,d))
order=sorted(range(len(res)),key=lambda i:res[i][3]); k=len(res)
holm={}
run=0
for rank,i in enumerate(order):
    run=max(run,min(1,res[i][3]*(k-rank))); holm[i]=run
for i,(att,m,se,p,d) in enumerate(res):
    ci=(m-stats.t.ppf(1-ALPHA,n-1)*se,m+stats.t.ppf(1-ALPHA,n-1)*se)
    verdict="EQUIVALENT within margin" if holm[i]<ALPHA else "NOT shown equivalent"
    print(f"{att:18s} diff {m:+.4f} 90% CI [{ci[0]:+.4f},{ci[1]:+.4f}] TOST p {p:.4f} Holm p {holm[i]:.4f} -> {verdict}; positive in {(d>0).sum()}/{n}")
if not informative: print("No attack passed both controls: the protocol cannot support an equivalence claim.")
print("\nSecondary (descriptive): matched minus full at eps 1")
for att in informative:
    d=np.array([g(w,"clean_matched")["eps1"][att]-g(w,"clean_full")["eps1"][att] for w in W]); print(f"{att:18s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
