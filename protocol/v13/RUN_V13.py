"""One-shot V13 run. Usage (Windows):  python RUN_V13.py
Design: ../../22_FROZEN_DESIGN_V13.md. Start it by hand only after RUN_V12.py has finished or been stopped. It refuses to start while RUN_V12.py is running.
Steps: hash check -> check that V12 is not running -> git freeze commit -> smoke test (world 0 of both cells, with exact-replication checks against V10 and V12) ->
worlds 1..99 of adult_pat and mimic_pat (2 workers) -> analysis -> results commit. Safe to re-run: finished worlds are skipped."""
import os,sys,re,json,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V13_MAX_HOURS","6")); SMOKE_TIMEOUT=3600; JOB_CAP=3600; WORKERS=int(os.environ.get("WORKERS","2")); THREADS=os.environ.get("THREADS","2")
TMP=Path(r"E:\Temp")
try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
except Exception as e: print("could not use E:\\Temp, continuing with the default temp folder:",e,flush=True)
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
os.environ["V13_OUT"]=str(RES)
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"22_FROZEN_DESIGN_V13.md").read_text(); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<4: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)

cmd=("(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*RUN_V12.py*' -and $_.ProcessId -ne $PID } | Measure-Object).Count")
SKIP=os.environ.get("V13_SKIP_V12_CHECK")=="1"
r=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True)
if not SKIP:
    if r.returncode!=0 or not r.stdout.strip().isdigit(): sys.exit("could not check whether RUN_V12.py is running: "+r.stdout+r.stderr+" Check by hand in Task Manager, then re-run with V13_SKIP_V12_CHECK=1.")
    if int(r.stdout.strip())>0: sys.exit("RUN_V12.py is still running. The PC has 8 GB of memory, so only one heavy job runs at a time. Stopping.")

def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["22_FROZEN_DESIGN_V13.md","_drafts/v13/v13_protocol.py","_drafts/v13/analyse_v13.py","_drafts/v13/RUN_V13.py"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V13 frozen design and scripts, committed before the V13 run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V13.txt"
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
    try: r=subprocess.run([sys.executable,str(H/"v13_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=env)
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"

CELLS=("adult_pat","mimic_pat")
print("SMOKE TEST: world 0 of each cell, one at a time, 1 h limit each",flush=True)
for c in CELLS:
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
if "adult_pat" in dropped: sys.exit("adult_pat dropped at smoke test, replication checks impossible. Stopping.")
# Replication checks on Adult world 0. P6_sym must equal V10 contaminated (divisor 1); P6_asym must equal V12 contaminated_mismatched (divisor 1). Only compared when the member count is the same.
def cmp(x,y,tag):
    worst=abs(x["records_only_oof"]-y["records_only_oof"])
    for att in ("DCR","DCRDiff","KDEratio"): worst=max(worst,abs(x["lap"]["1"][att]-y["lap_eps1"][att]))
    print(f"replication check {tag}: largest absolute difference",worst,flush=True)
    if worst>1e-6: sys.exit(f"REPLICATION CHECK FAILED ({tag}). Stopping. Do not use any V13 result.")
a=json.load(open(RES/"adult_pat_w0.json"))["results"]; arm=lambda R,n:next(r for r in R if r["arm"]==n)
for tag,path,src,mine in (("P6_sym vs V10 contaminated",D/"v10"/"results"/"adult_laplace_w0.json","contaminated","P6_sym"),("P6_asym vs V12 contaminated_mismatched",D/"v12"/"results"/"adult_asym_w0.json","contaminated_mismatched","P6_asym")):
    try: y=arm(json.load(open(path))["results"],src)
    except FileNotFoundError: print("replication check",tag,"skipped, file not found:",path,flush=True); continue
    x=arm(a,mine)
    if x["n_members"]!=y["n_members"]: print("replication check",tag,"skipped, member counts differ",x["n_members"],y["n_members"],flush=True); continue
    cmp(x,y,tag)

jobs=[(c,w) for w in range(1,100) for c in CELLS]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in CELLS}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v13.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v13.txt").write_text(out); print(out)
git("add","_drafts/v13/results","_drafts/v13/analysis_output_v13.txt"); git("commit","-m","V13 results and analysis output")
