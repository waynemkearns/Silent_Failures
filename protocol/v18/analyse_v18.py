"""Pre-specified analysis for V18 (see ../../28_FROZEN_DESIGN_V18.md). Prints verdicts; no free choices.
Releases: dpctgan_eps1, dpctgan_eps10 (DPCTGAN, smartnoise-synth) and ctgan_nodp (CTGAN, NOT differentially private, a reference).
Adult and MIMIC-IV, three standard arms, minimum 30 worlds per cell. Each cell is analysed on its own, with its own Holm families.
Informative attacks are decided per release: positive control above 0.80 in every arm, and that release's placebo means within 0.47 to 0.53.
Fidelity (decides how the primary verdict is read): clean_matched arm, two-way TVD of the trained release minus two-way TVD of the same
  library with the same seed and zero training steps, paired by world, one-sided test of 'trained release closer', Holm over the three releases.
  If not shown for a release, its equivalence verdict is labelled UNINFORMATIVE. Both libraries draw rows from exact category frequencies, so an
  untrained generator already beats a uniform draw; the uniform draw, the non-members and one-way TVD are reported but do not decide.
Primary (DP releases): contaminated minus clean_matched at f = 0, paired by world, equivalence within +/-0.03 (TOST, 90% CI),
  Holm over attacks x the two DPCTGAN releases.
Reference (CTGAN, not DP): the same contrast, in its own Holm family, reported as a reference only.
Secondary (detection, as V15): clean_matched arm, AUC at planted share f minus AUC at f = 0, Holm over attacks x shares, per release.
Descriptive: DPCTGAN training record, size contrast, mean AUC tables."""
import json,os,sys,numpy as np
from pathlib import Path
from scipy import stats
MARGIN=0.03; ALPHA=0.05; MINW=int(os.environ.get("V18_MIN_WORLDS","30")); TEST_MODE="V18_MIN_WORLDS" in os.environ
STD=["clean_full","clean_matched","contaminated"]; ATT=["DCR","DCRDiff","KDEratio","Classifier","LocalNeighborhood"]
DPREL=["dpctgan_eps1","dpctgan_eps10"]; REL=DPREL+["ctgan_nodp"]; FGRID=["0.05","0.1","0.25"]
NAME={"dpctgan_eps1":"DPCTGAN eps 1","dpctgan_eps10":"DPCTGAN eps 10","ctgan_nodp":"CTGAN, not DP"}
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
def p_lt(m,se,n,thr): return float(stats.t.cdf((m-thr)/se,n-1))
def p_eq(m,se,n): return float(max(1-stats.t.cdf((m+MARGIN)/se,n-1),stats.t.cdf((m-MARGIN)/se,n-1)))
def p_sh(m,se,n): return float(min(1-stats.t.cdf((m-MARGIN)/se,n-1),stats.t.cdf((m+MARGIN)/se,n-1)))
def equivalence(g,W,rels,inf,learned,title):
    T=[]
    for r in rels:
        for a in inf[r]:
            d=np.array([g(w,"contaminated")[f"{r}_f0"][a]-g(w,"clean_matched")[f"{r}_f0"][a] for w in W]); m,se,lo,hi,nn=ci(d); T.append((r,a,m,lo,hi,p_eq(m,se,nn),p_sh(m,se,nn),int((d>0).sum())))
    if not T: print(f"\n{title}: no informative attack, no verdict"); return
    he=holm([t[5] for t in T]); hs=holm([t[6] for t in T])
    print(f"\n{title}: contaminated minus clean_matched at f=0, margin +/-{MARGIN}, 90% CI, Holm over {len(T)} tests, n={len(W)}")
    for t,a_,b_ in zip(T,he,hs):
        vv="SHIFT beyond the margin" if b_<ALPHA else ("equivalent within the margin" if a_<ALPHA else "inconclusive")
        if not learned[t[0]]: vv+=" [UNINFORMATIVE: training not shown to bring the release closer to the members than an untrained generator (two-way TVD)]"
        print(f"  {NAME[t[0]]:15s} {t[1]:10s} diff {t[2]:+.4f} CI [{t[3]:+.4f},{t[4]:+.4f}] Holm eq {a_:.3g} shift {b_:.3g} -> {vv}; positive in {t[7]}/{len(W)}")
for cell in ("adult_gan","mimic_gan"):
    print("\n"+"="*72+"\nCELL",cell,"(DPCTGAN at epsilon 1 and 10, batch 64, epoch cap 300; CTGAN without DP as a reference; publicly binned data)")
    R=load(cell); W=sorted({r["world"] for r in R}); n=len(W); print("worlds completed:",n,f"(minimum {MINW})"+(" TEST MODE, not a result" if TEST_MODE else ""))
    if any(r.get("test_mode") for r in R):
        print("TEST-MODE RESULT FILES PRESENT (shortened training): no claim for this cell")
        if os.environ.get("V18_ANALYSE_TEST_FILES")!="1": continue
        print("(code test: analysing test-mode files anyway; nothing below is a result)")
    if n<MINW: print("INSUFFICIENT WORLDS: no claim for this cell"); continue
    idx={(r["world"],r["arm"]):r for r in R}; g=lambda w,a:idx[(w,a)]
    print("DPCTGAN training record (mean over worlds; epochs trained, share stopped by budget, spent epsilon, fit seconds):")
    for arm in STD:
        for r in DPREL:
            F=[g(w,arm)[f"{r}_fit"] for w in W]
            print(f"  {arm:14s} {NAME[r]:15s} epochs {np.mean([x['epochs_trained'] for x in F]):6.1f} (min {min(x['epochs_trained'] for x in F)}, max {max(x['epochs_trained'] for x in F)})"
                  f" | stopped by budget {sum(x['stopped_by_budget'] for x in F)}/{n} | spent eps {np.mean([x['eps_spent'] for x in F]):.3f} (max {max(x['eps_spent'] for x in F):.3f}) | fit s {np.mean([x['fit_seconds'] for x in F]):.0f}")
        print(f"  {arm:14s} {NAME['ctgan_nodp']:15s} fit s {np.mean([g(w,arm)['ctgan_nodp_fit']['fit_seconds'] for w in W]):.0f}")
    ro=[np.mean([g(w,a)["records_only_oof"] for w in W]) for a in STD]; ro_ok=all(.45<=x<=.55 for x in ro)
    print("records-only means (clean_full, clean_matched, contaminated)",np.round(ro,3),"PASS" if ro_ok else "FAIL")
    inf={r:[] for r in REL}
    for a in ATT:
        pos=[np.mean([g(w,arm)["lap_eps100"][a] for w in W]) for arm in STD]; okp=min(pos)>0.80; line=f"{a:18s} positive(lap eps100) min-arm {min(pos):.3f} {'PASS' if okp else 'FAIL'} | placebo means"
        for r in REL:
            pl=[np.mean([g(w,arm)[f"plc_{r}"][a] for w in W]) for arm in STD]; okl=all(.47<=x<=.53 for x in pl)
            line+=f" {NAME[r]} {min(pl):.3f}-{max(pl):.3f} {'PASS' if okl else 'FAIL'};"
            if okp and okl: inf[r].append(a)
        print(line)
    for r in REL: print(f"informative attacks, {NAME[r]}:",inf[r])
    print("FIDELITY (mean TVD against the members; lower is closer). one-way / two-way. Comparison points: non-members, uniform draw, untrained generator")
    for arm in STD:
        s=f"  {arm:14s} non-members {np.mean([g(w,arm)['tvd1_nonmembers'] for w in W]):.3f}/{np.mean([g(w,arm)['tvd2_nonmembers'] for w in W]):.3f} uniform {np.mean([g(w,arm)['tvd1_uniform'] for w in W]):.3f}/{np.mean([g(w,arm)['tvd2_uniform'] for w in W]):.3f}"
        for r in REL: s+=f" | {NAME[r]} trained {np.mean([g(w,arm)[f'tvd1_{r}'] for w in W]):.3f}/{np.mean([g(w,arm)[f'tvd2_{r}'] for w in W]):.3f} untrained {np.mean([g(w,arm)[f'tvd1_untrained_{r}'] for w in W]):.3f}/{np.mean([g(w,arm)[f'tvd2_untrained_{r}'] for w in W]):.3f}"
        print(s)
    FT=[]
    for r in REL:
        d=np.array([g(w,"clean_matched")[f"tvd2_{r}"]-g(w,"clean_matched")[f"tvd2_untrained_{r}"] for w in W]); m,se,lo,hi,nn=ci(d); FT.append((r,m,lo,hi,p_lt(m,se,nn,0.0)))
    hf=holm([t[4] for t in FT]); learned={}
    for t,a_ in zip(FT,hf):
        learned[t[0]]=a_<ALPHA
        print(f"  clean_matched {NAME[t[0]]:15s}: two-way TVD trained minus untrained {t[1]:+.4f} CI [{t[2]:+.4f},{t[3]:+.4f}] Holm p(trained closer) {a_:.3g} -> {'training brought the release closer to the members' if a_<ALPHA else 'NOT shown that training brought the release closer'}")
    print("Mean AUC by arm, release and share f (all attacks, descriptive):")
    for arm in STD:
        for r in REL:
            for f in ["0"]+FGRID: print(f"  {arm:14s} {NAME[r]:15s} f {f:>4s}",{a:round(float(np.mean([g(w,arm)[f'{r}_f{f}'][a] for w in W])),3) for a in ATT})
    if not ro_ok: print("Gates not met (records-only baseline): no claim for this cell."); continue
    equivalence(g,W,DPREL,inf,learned,"PRIMARY (DPCTGAN)")
    equivalence(g,W,["ctgan_nodp"],inf,learned,"REFERENCE (CTGAN, not DP, own Holm family)")
    for r in REL:
        D=[]
        for a in inf[r]:
            for f in FGRID:
                d=np.array([g(w,"clean_matched")[f"{r}_f{f}"][a]-g(w,"clean_matched")[f"{r}_f0"][a] for w in W]); m,se,lo,hi,nn=ci(d); D.append((a,f,m,lo,hi,p_gt(m,se,nn,0.0),p_gt(m,se,nn,MARGIN)))
        if not D: print(f"\nSECONDARY (detection), {NAME[r]}: no informative attack"); continue
        h0=holm([t[5] for t in D]); hM=holm([t[6] for t in D])
        print(f"\nSECONDARY (detection), {NAME[r]}, clean_matched arm: AUC at share f minus AUC at f=0, paired, 90% CI, Holm over {len(D)} tests")
        first0={}; firstM={}
        for t,a0,aM in zip(D,h0,hM):
            vv="BEYOND the 0.03 margin" if aM<ALPHA else ("detected (increase > 0)" if a0<ALPHA else "not detected")
            print(f"  {t[0]:10s} f {t[1]:>4s} diff {t[2]:+.4f} CI [{t[3]:+.4f},{t[4]:+.4f}] Holm p(>0) {a0:.3g} p(>0.03) {aM:.3g} -> {vv}")
            if a0<ALPHA: first0.setdefault(t[0],t[1])
            if aM<ALPHA: firstM.setdefault(t[0],t[1])
        for a in inf[r]: print(f"  {a:10s} smallest share detected: {first0.get(a,'none in grid')}; smallest share beyond the margin: {firstM.get(a,'none in grid')}")
    print("SIZE (descriptive): clean_matched minus clean_full at f=0")
    for r in REL:
        for a in inf[r]:
            d=np.array([g(w,"clean_matched")[f"{r}_f0"][a]-g(w,"clean_full")[f"{r}_f0"][a] for w in W]); print(f"  {NAME[r]:15s} {a:10s} {d.mean():+.4f} sd {d.std(ddof=1):.4f}")
