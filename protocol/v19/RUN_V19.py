"""One-shot V19 run (DP-CTGAN on current opacus, a second DP GAN, on the V14 worlds and arms). Usage (Windows):  python RUN_V19.py
Design: ../../29_FROZEN_DESIGN_V19.md. It refuses to start while RUN_V12.py to RUN_V18.py is running.
It changes no earlier file and installs nothing. The ctgan package must already be in <LOCAL_PATH> and opacus 1.5.2 in <LOCAL_PATH> (install step in CURSOR_PROMPT_V18_V19.md).
Steps: hash check -> check no other run is active -> git freeze commit -> environment report ->
smoke test (world 0 of both cells, with an exact-replication check of the records-only baseline and the near-copy positive control against V14) ->
worlds 1..29 of both cells (2 workers) -> analysis -> results commit. Safe to re-run: finished worlds are skipped."""
import os,sys,re,json,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
try:  # keep Windows awake while this script runs (idle sleep only; lid close, manual sleep and forced restarts still win)
    import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000001); print("keep-awake request set",flush=True)
except Exception as e: print("keep-awake request not set:",e,flush=True)
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V19_MAX_HOURS","10")); SMOKE_TIMEOUT=3*3600; JOB_CAP=3*3600; WORKERS=int(os.environ.get("WORKERS","2")); THREADS=os.environ.get("THREADS","2")
for k in ("V18_TEST_EPOCHS","V18_MIN_WORLDS","V18_ANALYSE_TEST_FILES","V19_TEST_EPOCHS","V19_MIN_WORLDS","V19_ANALYSE_TEST_FILES"):
    if k in os.environ: sys.exit(f"{k} is set. That switch is for code testing only. Remove it and start again.")
TMP=Path(r"<LOCAL_PATH>")
if os.name=="nt":
  try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
  except Exception as e: print("could not use <LOCAL_PATH>, continuing with the default temp folder:",e,flush=True)
os.environ.setdefault("MIMIC_CANONICAL_CSV",r"<LOCAL_PATH>")
os.environ.setdefault("ADULT_CSV",r"<LOCAL_PATH>")
os.environ["V19_OUT"]=str(RES); os.environ["THREADS"]=THREADS
os.environ.setdefault("V18_PKGS",r"<LOCAL_PATH>"); os.environ.setdefault("V19_PKGS",r"<LOCAL_PATH>")
for k in ("V18_PKGS","V19_PKGS"):
    if not Path(os.environ[k]).is_dir(): sys.exit("The package folder "+os.environ[k]+" is missing. Run the install step in CURSOR_PROMPT_V18_V19.md first.")
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"29_FROZEN_DESIGN_V19.md").read_text(encoding="utf-8"); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<6: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)

if os.environ.get("V19_SKIP_RUN_CHECK")!="1":
    names=" -or ".join(f"$_.CommandLine -like '*RUN_V{x}.py*'" for x in ("12","13","14","14D","15","16","17","18"))
    cmd=f"(Get-CimInstance Win32_Process | Where-Object {{ $_.Name -like 'python*' -and ({names}) -and $_.ProcessId -ne $PID }} | Measure-Object).Count"
    r=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True)
    if r.returncode!=0 or not r.stdout.strip().isdigit(): sys.exit("could not check whether an earlier run is still going: "+r.stdout+r.stderr+" Check by hand, then re-run with V19_SKIP_RUN_CHECK=1.")
    if int(r.stdout.strip())>0: sys.exit("An earlier run (RUN_V12.py to RUN_V18.py) is still running. The PC has 8 GB of memory, so only one heavy job runs at a time. Stopping.")

def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0: sys.exit("The P1_EVIDENCE_AUDIT_2026-09 folder is not a git repository. Stopping.")
files=["29_FROZEN_DESIGN_V19.md","_drafts/v19/v19_protocol.py","_drafts/v19/dp_ctgan_opacus.py","_drafts/v19/analyse_v19.py","_drafts/v19/RUN_V19.py","_drafts/v19/RUN_V18_V19.py","_drafts/v19/CURSOR_PROMPT_V18_V19.md"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V19 frozen design and scripts, committed before the V19 run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V19.txt"
if not rec.exists():
    msg="V19 frozen design and scripts, committed before the V19 run"
    hh,_,tt=git("log","-1","--fixed-strings","--grep="+msg,"--format=%H %cI").stdout.strip().partition(" ")
    if not hh: sys.exit("No V19 freeze commit found in git log (it is not the V19 freeze commit). Stopping.")
    if git("status","--porcelain","--",*files).stdout.strip(): sys.exit("The frozen V19 files differ from the freeze commit. Stopping.")
    rec.write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
else: print("freeze record already exists, kept:",rec.read_text().splitlines()[0],flush=True)

code=("import sys,os;sys.path.insert(0,os.environ['V19_PKGS']);sys.path.append(os.environ['V18_PKGS']);print(sys.version)\n"
      "import numpy,pandas,sklearn,scipy;print('numpy',numpy.__version__,'pandas',pandas.__version__,'sklearn',sklearn.__version__,'scipy',scipy.__version__)\n"
      "import torch;print('torch',torch.__version__,'cuda',torch.cuda.is_available())\n"
      "import opacus;print('opacus',opacus.__version__)\n"
      "import importlib.metadata as m;print('smartnoise-synth',m.version('smartnoise-synth'),'packaging',m.version('packaging'))\n"
      "import ctgan,rdt,faker;print('ctgan',m.version('ctgan'),ctgan.__file__);print('rdt',m.version('rdt'),'Faker',m.version('Faker'))\n"
      "assert opacus.__version__.startswith('1.5'),'opacus 1.5 not first on the path';print('opacus file',opacus.__file__)\n"
      "from ctgan import CTGAN;from opacus import GradSampleModule;from opacus.optimizers import DPOptimizer;from opacus.accountants import RDPAccountant;print('CTGAN and opacus 1.5 imports OK')")
r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
(RES/"ENV_V19.txt").write_text(r.stdout+r.stderr); print("ENVIRONMENT:\n"+r.stdout+r.stderr,flush=True)
if r.returncode!=0: sys.exit("environment check failed, stopping. Send me the text above.")

START=time.time(); dropped=set()
def child_env():
    env=dict(os.environ)
    for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"): env[k]=THREADS
    return env
def run(cell,w,timeout):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    t=time.time()
    try: r=subprocess.run([sys.executable,str(H/"v19_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=child_env())
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"

CELLS=("adult_gan2","mimic_gan2")
print("SMOKE TEST: world 0 of each cell, one at a time, 3 h limit each",flush=True)
for c in CELLS:
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
if dropped: sys.exit("A cell was dropped at the smoke test ("+", ".join(sorted(dropped))+"). Stopping.")
# replication check: member counts, the records-only baseline and the near-copy positive control must equal V14 world 0 exactly
REF={"adult_gan2":D/"v14"/"results"/"adult_mwem_w0.json","mimic_gan2":D/"v14"/"results"/"mimic_mwem_w0.json"}
worst=0.0
try:
    for c,fref in REF.items():
        a=json.load(open(RES/f"{c}_w0.json"))["results"]; b=json.load(open(fref))["results"]
        for arm in ("clean_full","clean_matched","contaminated"):
            x=next(r for r in a if r["arm"]==arm); y=next(r for r in b if r["arm"]==arm)
            if x["n_members"]!=y["n_members"]: sys.exit("REPLICATION CHECK FAILED: member counts differ for "+c+" "+arm)
            worst=max(worst,abs(x["records_only_oof"]-y["records_only_oof"]))
            for att in y["lap_eps100"]: worst=max(worst,abs(x["lap_eps100"][att]-y["lap_eps100"][att]))
        for arm in ("clean_full","clean_matched","contaminated"):
            x=next(r for r in a if r["arm"]==arm)
            print(f"  {c} {arm}: discriminator steps eps 1 {x['dpctgan2_eps1_fit']['steps']}, eps 10 {x['dpctgan2_eps10_fit']['steps']}; spent eps {x['dpctgan2_eps1_fit']['eps_spent']:.3f}, {x['dpctgan2_eps10_fit']['eps_spent']:.3f}; fit seconds {x['dpctgan2_eps1_fit']['fit_seconds']}, {x['dpctgan2_eps10_fit']['fit_seconds']}",flush=True)
    print("replication check against V14 world 0 (member counts, records-only baseline, near-copy positive control): largest absolute difference",worst,flush=True)
    if worst>1e-6: sys.exit("REPLICATION CHECK FAILED: V19 differs from V14 on quantities that do not depend on the release. Stopping. Do not use any V19 result.")
except FileNotFoundError as e: sys.exit("replication check could not run: "+str(e))

jobs=[(c,w) for w in range(1,30) for c in CELLS]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in CELLS}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v19.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v19.txt").write_text(out); print(out)
git("add","_drafts/v19/results","_drafts/v19/analysis_output_v19.txt","_drafts/v19/FREEZE_RECORD_V19.txt"); r=git("commit","-m","V19 results and analysis output")
print("results commit:",(r.stdout+r.stderr).strip()[:300],flush=True)
