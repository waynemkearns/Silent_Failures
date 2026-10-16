"""One-shot V10 run. Usage (Windows):  python RUN_V10.py
Needs: pip install numpy pandas scipy scikit-learn smartnoise-synth     (smartnoise-synth pulls in torch; that is expected)
Steps: hash check -> git freeze commit -> smoke test (world 0 of each cell) -> remaining worlds until the time limit -> analysis -> results commit."""
import os,sys,re,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V10_MAX_HOURS","10")); SMOKE_TIMEOUT=60*45
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"17_FROZEN_DESIGN_V10.md").read_text(); bad=[]
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad: sys.exit("HASH MISMATCH, stopping: "+", ".join(bad))
print("hashes OK",flush=True)
def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["17_FROZEN_DESIGN_V10.md","_drafts/v10/v10_protocol.py","_drafts/v10/analyse_v10.py","_drafts/v10/RUN_V10.py","_drafts/repaired_protocol/kde_ratio_own.py"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V10 frozen design and scripts, committed before the V10 run",*files)
if r.returncode and "nothing to commit" not in (r.stdout+r.stderr): sys.exit("git commit failed: "+r.stdout+r.stderr)
hh=git("rev-parse","HEAD").stdout.strip(); tt=git("log","-1","--format=%cI").stdout.strip()
(H/"FREEZE_RECORD_V10.txt").write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
START=time.time(); WORKERS=int(os.environ.get("WORKERS",max(1,(os.cpu_count() or 2)-1))); dropped=set()
def run(cell,w,timeout=None):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    try: r=subprocess.run([sys.executable,str(H/"v10_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout)
    except subprocess.TimeoutExpired: return "TIMEOUT"
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    return "ok"
cells=["adult_laplace","adult_mst","mimic_mst"]
print("SMOKE TEST: world 0 of each cell",flush=True)
with ThreadPoolExecutor(3) as ex:
    for c,s in zip(cells,ex.map(lambda c:run(c,0,SMOKE_TIMEOUT),cells)):
        print(c,s,flush=True)
        if s in ("ERROR","TIMEOUT"):
            dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
jobs=[]
for w in range(1,100):
    jobs.append(("adult_laplace",w))
    if w<50: jobs += [("adult_mst",w),("mimic_mst",w)]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(*j)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in cells}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v10.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v10.txt").write_text(out); print(out)
git("add","_drafts/v10/results","_drafts/v10/analysis_output_v10.txt"); git("commit","-m","V10 results and analysis output")
