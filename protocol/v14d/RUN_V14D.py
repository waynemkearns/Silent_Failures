"""One-shot V14D run (Part D: PrivBayes-style synthesizer). Usage (Windows):  python RUN_V14D.py
Design: ../../24_FROZEN_DESIGN_V14D.md. Start it by hand only after RUN_V14.py has finished. It refuses to start while RUN_V12.py, RUN_V13.py or RUN_V14.py is running.
It changes no V14 file and installs nothing: DataSynthesizer 0.1.13 is vendored in ./vendor and hash-checked.
Steps: hash check -> check no other run is active -> git freeze commit -> environment report ->
smoke test (world 0 of adult_pb and mimic_pb, with an exact-replication check of the positive control against V11) ->
worlds 1..29 of adult_pb and mimic_pb (2 workers) -> analysis -> results commit. Safe to re-run: finished worlds are skipped."""
import os,sys,re,json,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
try:  # keep Windows awake while this script runs (idle sleep only; lid close, manual sleep and forced restarts still win)
    import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000001); print("keep-awake request set",flush=True)
except Exception as e: print("keep-awake request not set:",e,flush=True)
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V14D_MAX_HOURS","8")); SMOKE_TIMEOUT=3*3600; JOB_CAP=2*3600; WORKERS=int(os.environ.get("WORKERS","2")); THREADS=os.environ.get("THREADS","2")
TMP=Path(r"E:\Temp")
try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
except Exception as e: print("could not use E:\\Temp, continuing with the default temp folder:",e,flush=True)
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
os.environ["V14D_OUT"]=str(RES)
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"24_FROZEN_DESIGN_V14D.md").read_text(); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<8: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)

if os.environ.get("V14D_SKIP_RUN_CHECK")!="1":
    cmd=("(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and ($_.CommandLine -like '*RUN_V12.py*' -or $_.CommandLine -like '*RUN_V13.py*' -or $_.CommandLine -like '*RUN_V14.py*') -and $_.ProcessId -ne $PID } | Measure-Object).Count")
    r=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True)
    if r.returncode!=0 or not r.stdout.strip().isdigit(): sys.exit("could not check whether RUN_V12.py, RUN_V13.py or RUN_V14.py is running: "+r.stdout+r.stderr+" Check by hand, then re-run with V14D_SKIP_RUN_CHECK=1.")
    if int(r.stdout.strip())>0: sys.exit("RUN_V12.py, RUN_V13.py or RUN_V14.py is still running. The PC has 8 GB of memory, so only one heavy job runs at a time. Stopping.")

def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["24_FROZEN_DESIGN_V14D.md","_drafts/v14d/v14d_protocol.py","_drafts/v14d/analyse_v14d.py","_drafts/v14d/RUN_V14D.py","_drafts/v14d/CURSOR_PROMPT_V14D.md","_drafts/v14d/vendor"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V14D frozen design and scripts, committed before the V14D run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V14D.txt"
if not rec.exists():
    hh=git("rev-parse","HEAD").stdout.strip(); tt=git("log","-1","--format=%cI").stdout.strip()
    rec.write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
else: print("freeze record already exists, kept:",rec.read_text().splitlines()[0],flush=True)

code=("import sys;sys.path.insert(0,r'%s');print(sys.version)\n"
      "import numpy,pandas,sklearn,scipy;print('numpy',numpy.__version__,'pandas',pandas.__version__,'sklearn',sklearn.__version__,'scipy',scipy.__version__)\n"
      "import DataSynthesizer;print('DataSynthesizer',DataSynthesizer.__version__,DataSynthesizer.__file__)\n"
      "from DataSynthesizer.DataDescriber import DataDescriber;from DataSynthesizer.DataGenerator import DataGenerator;print('DataSynthesizer imports OK')")%str(H/"vendor")
r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
(RES/"ENV_V14D.txt").write_text(r.stdout+r.stderr); print("ENVIRONMENT:\n"+r.stdout+r.stderr,flush=True)
if r.returncode!=0: sys.exit("environment check failed, stopping. Send me the text above.")

START=time.time(); dropped=set()
def child_env():
    env=dict(os.environ)
    for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"): env[k]=THREADS
    return env
def run(cell,w,timeout):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    t=time.time()
    try: r=subprocess.run([sys.executable,str(H/"v14d_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=child_env())
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"

CELLS=("adult_pb","mimic_pb")
print("SMOKE TEST: world 0 of each cell, one at a time, 3 h limit each",flush=True)
for c in CELLS:
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
if "adult_pb" in dropped: sys.exit("adult_pb dropped at smoke test, replication check impossible. Stopping.")
try:
    a=json.load(open(RES/"adult_pb_w0.json"))["results"]; b=json.load(open(D/"v10"/"results"/"adult_mst_w0.json"))["results"]; worst=0.0
    for arm in ("clean_full","clean_matched","contaminated"):
        x=next(r for r in a if r["arm"]==arm); y=next(r for r in b if r["arm"]==arm)
        if x["n_members"]!=y["n_members"]: sys.exit("REPLICATION CHECK FAILED: member counts differ for "+arm)
        worst=max(worst,abs(x["records_only_oof"]-y["records_only_oof"]))
        for att in y["lap_eps100"]: worst=max(worst,abs(x["lap_eps100"][att]-y["lap_eps100"][att]))
    print("replication check against V11 adult_mst world 0 (records-only baseline and near-copy positive control): largest absolute difference",worst,flush=True)
    if worst>1e-6: sys.exit("REPLICATION CHECK FAILED: V14D standard arms differ from V11. Stopping. Do not use any V14D result.")
except FileNotFoundError as e: sys.exit("replication check could not run: "+str(e))

jobs=[(c,w) for w in range(1,30) for c in CELLS]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in CELLS}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v14d.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v14d.txt").write_text(out); print(out)
git("add","_drafts/v14d/results","_drafts/v14d/analysis_output_v14d.txt"); git("commit","-m","V14D results and analysis output")
