"""One-shot V12 run. Usage (Windows):  python RUN_V12.py
Design: ../../21_FROZEN_DESIGN_V12.md. Start it by hand only after RUN_V11.py has finished (set V12_WAIT=1 to make it wait instead; untested).
Steps: hash check -> git freeze commit ->
smoke test (world 0 of the four cells, one at a time, 3 h limit each, plus an exact-replication check against V10) ->
phase 1: worlds 1..99 of adult_asym and mimic_asym -> phase 2: worlds 1..49 of adult_mstasym and mimic_mstasym ->
analysis -> results commit. 2 workers. Safe to re-run: finished worlds are skipped."""
import os,sys,re,json,hashlib,subprocess,time
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V12_MAX_HOURS","9")); SMOKE_TIMEOUT=3*3600; JOB_CAP=3*3600; WORKERS=int(os.environ.get("WORKERS","2")); THREADS=os.environ.get("THREADS","2")
TMP=Path(r"E:\Temp")
try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
except Exception as e: print("could not use E:\\Temp, continuing with the default temp folder:",e,flush=True)
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
os.environ["V12_OUT"]=str(RES)
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"21_FROZEN_DESIGN_V12.md").read_text(); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<4: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)

def v11_running():
    cmd=("(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*RUN_V11.py*' -and $_.ProcessId -ne $PID } | Measure-Object).Count")
    r=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True)
    if r.returncode!=0 or not r.stdout.strip().isdigit(): sys.exit("could not check whether RUN_V11.py is running: "+r.stdout+r.stderr+" (this check is optional: start RUN_V12.py by hand once V11 has finished, without V12_WAIT)")
    return int(r.stdout.strip())>0
if os.environ.get("V12_WAIT")=="1":   # optional and untested on Windows; the default is a manual start after V11 has finished
    t0=time.time(); announced=False
    while v11_running():
        if not announced: print("RUN_V11.py is still running. Waiting for it to finish (checking every 5 minutes, up to 14 hours).",flush=True); announced=True
        if time.time()-t0>14*3600: sys.exit("gave up waiting for RUN_V11.py after 14 hours")
        time.sleep(300)
    if announced: print("RUN_V11.py has finished, starting V12",flush=True)

def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["21_FROZEN_DESIGN_V12.md","_drafts/v12/v12_protocol.py","_drafts/v12/analyse_v12.py","_drafts/v12/RUN_V12.py"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V12 frozen design and scripts, committed before the V12 run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V12.txt"
if not rec.exists():
    hh=git("rev-parse","HEAD").stdout.strip(); tt=git("log","-1","--format=%cI").stdout.strip()
    rec.write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
else: print("freeze record already exists, kept:",rec.read_text().splitlines()[0],flush=True)

START=time.time(); dropped=set()
def run(cell,w,timeout):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    env=dict(os.environ)
    for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"): env[k]=THREADS
    t=time.time()
    try: r=subprocess.run([sys.executable,str(H/"v12_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=env)
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"

CELLS=("adult_asym","mimic_asym","adult_mstasym","mimic_mstasym")
print("SMOKE TEST: world 0 of each cell, one at a time, 3 h limit each",flush=True)
for c in CELLS:
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
# Exact-replication check: the three standard arms must equal the V10 adult_laplace world 0 results.
try:
    a=json.load(open(RES/"adult_asym_w0.json"))["results"]; b=json.load(open(D/"v10"/"results"/"adult_laplace_w0.json"))["results"]
    worst=0.0
    for arm in ("clean_full","clean_matched","contaminated"):
        x=next(r for r in a if r["arm"]==arm); y=next(r for r in b if r["arm"]==arm)
        worst=max(worst,abs(x["records_only_oof"]-y["records_only_oof"]))
        for k in ("lap_eps1","lap_eps100","plc_lap_eps1","plc_lap_eps100"):
            for att in y[k]: worst=max(worst,abs(x[k][att]-y[k][att]))
    print("replication check against V10 adult_laplace world 0: largest absolute difference",worst,flush=True)
    if worst>1e-6: sys.exit("REPLICATION CHECK FAILED: V12 standard arms differ from V10. Stopping. Do not use any V12 result.")
except FileNotFoundError as e: sys.exit("replication check could not run: "+str(e))
if "adult_asym" in dropped: sys.exit("adult_asym dropped at smoke test, replication check impossible. Stopping.")

jobs=[(c,w) for w in range(1,100) for c in ("adult_asym","mimic_asym")]+[(c,w) for w in range(1,50) for c in ("adult_mstasym","mimic_mstasym")]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in CELLS}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v12.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v12.txt").write_text(out); print(out)
git("add","_drafts/v12/results","_drafts/v12/analysis_output_v12.txt"); git("commit","-m","V12 results and analysis output")
