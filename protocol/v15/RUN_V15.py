"""One-shot V15 run (sensitivity test: a known share of real member rows planted in DP releases). Usage (Windows):  python RUN_V15.py
Design: ../../25_FROZEN_DESIGN_V15.md. Start it by hand only after RUN_V14.py and RUN_V14D.py have finished. It refuses to start while RUN_V12.py, RUN_V13.py, RUN_V14.py or RUN_V14D.py is running.
It changes no earlier file and installs nothing (the vendored DataSynthesizer copy in ../v14d/vendor is hash-checked).
Steps: hash check -> check no other run is active -> git freeze commit -> environment report ->
smoke test (world 0 of the four cells, with an exact-replication check of the f = 0 results, the records-only baseline and the positive control against V14 and V14D) ->
worlds 1..29 of the four cells (2 workers) -> analysis -> results commit. Safe to re-run: finished worlds are skipped."""
import os,sys,re,json,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
try:  # keep Windows awake while this script runs (idle sleep only; lid close, manual sleep and forced restarts still win)
    import ctypes; ctypes.windll.kernel32.SetThreadExecutionState(0x80000001); print("keep-awake request set",flush=True)
except Exception as e: print("keep-awake request not set:",e,flush=True)
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; RES=H/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V15_MAX_HOURS","10")); SMOKE_TIMEOUT=3*3600; JOB_CAP=3*3600; WORKERS=int(os.environ.get("WORKERS","2")); THREADS=os.environ.get("THREADS","2")
TMP=Path(r"E:\Temp")
try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
except Exception as e: print("could not use E:\\Temp, continuing with the default temp folder:",e,flush=True)
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
os.environ["V15_OUT"]=str(RES)
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"25_FROZEN_DESIGN_V15.md").read_text(); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<8: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)

if os.environ.get("V15_SKIP_RUN_CHECK")!="1":
    cmd=("(Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and ($_.CommandLine -like '*RUN_V12.py*' -or $_.CommandLine -like '*RUN_V13.py*' -or $_.CommandLine -like '*RUN_V14.py*' -or $_.CommandLine -like '*RUN_V14D.py*') -and $_.ProcessId -ne $PID } | Measure-Object).Count")
    r=subprocess.run(["powershell","-NoProfile","-Command",cmd],capture_output=True,text=True)
    if r.returncode!=0 or not r.stdout.strip().isdigit(): sys.exit("could not check whether RUN_V12.py, RUN_V13.py, RUN_V14.py or RUN_V14D.py is running: "+r.stdout+r.stderr+" Check by hand, then re-run with V15_SKIP_RUN_CHECK=1.")
    if int(r.stdout.strip())>0: sys.exit("RUN_V12.py, RUN_V13.py, RUN_V14.py or RUN_V14D.py is still running. The PC has 8 GB of memory, so only one heavy job runs at a time. Stopping.")

def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["25_FROZEN_DESIGN_V15.md","_drafts/v15/v15_protocol.py","_drafts/v15/analyse_v15.py","_drafts/v15/RUN_V15.py","_drafts/v15/CURSOR_PROMPT_V15.md"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V15 amended design and scripts (MWEM replication check), committed before worlds 1 to 29 were run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V15_AMENDED.txt"
if not rec.exists():
    hh=git("rev-parse","HEAD").stdout.strip(); tt=git("log","-1","--format=%cI").stdout.strip()
    rec.write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
else: print("freeze record already exists, kept:",rec.read_text().splitlines()[0],flush=True)

code=("import sys;sys.path.insert(0,r'%s');print(sys.version)\n"
      "import numpy,pandas,sklearn,scipy;print('numpy',numpy.__version__,'pandas',pandas.__version__,'sklearn',sklearn.__version__,'scipy',scipy.__version__)\n"
      "import DataSynthesizer;print('DataSynthesizer',DataSynthesizer.__version__,DataSynthesizer.__file__)\n"
      "import snsynth;print('snsynth',getattr(snsynth,'__version__','unknown'))\n"
      "from DataSynthesizer.DataDescriber import DataDescriber;from DataSynthesizer.DataGenerator import DataGenerator;print('DataSynthesizer imports OK')")%str(D/"v14d"/"vendor")
r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True)
(RES/"ENV_V15.txt").write_text(r.stdout+r.stderr); print("ENVIRONMENT:\n"+r.stdout+r.stderr,flush=True)
if r.returncode!=0: sys.exit("environment check failed, stopping. Send me the text above.")

START=time.time(); dropped=set()
def child_env():
    env=dict(os.environ)
    for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"): env[k]=THREADS
    return env
def run(cell,w,timeout):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    t=time.time()
    try: r=subprocess.run([sys.executable,str(H/"v15_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=child_env())
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"

CELLS=("adult_mwem","mimic_mwem","adult_pb","mimic_pb")
print("SMOKE TEST: world 0 of each cell, one at a time, 3 h limit each",flush=True)
for c in CELLS:
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See error_{c}_w0.txt\n")
if dropped: sys.exit("A cell was dropped at the smoke test ("+", ".join(sorted(dropped))+"), so the replication check cannot run for all four cells. Stopping.")
# replication check: the f = 0 results, the records-only baseline and the near-copy positive control must equal the earlier runs exactly
REF={"adult_mwem":(D/"v14"/"results"/"adult_mwem_w0.json","mwem_eps10"),"mimic_mwem":(D/"v14"/"results"/"mimic_mwem_w0.json","mwem_eps10"),
     "adult_pb":(D/"v14d"/"results"/"adult_pb_w0.json","pb_eps10"),"mimic_pb":(D/"v14d"/"results"/"mimic_pb_w0.json","pb_eps10")}
worst=0.0; worst_mwem=0.0; MWEM_BAND=0.08
try:
    for c,(fref,kold) in REF.items():
        method=c.split("_")[1]; a=json.load(open(RES/f"{c}_w0.json"))["results"]; b=json.load(open(fref))["results"]
        for arm in ("clean_full","clean_matched","contaminated"):
            x=next(r for r in a if r["arm"]==arm); y=next(r for r in b if r["arm"]==arm)
            if x["n_members"]!=y["n_members"]: sys.exit("REPLICATION CHECK FAILED: member counts differ for "+c+" "+arm)
            worst=max(worst,abs(x["records_only_oof"]-y["records_only_oof"]))
            for att in y["lap_eps100"]: worst=max(worst,abs(x["lap_eps100"][att]-y["lap_eps100"][att]))
            for att in y[kold]:
                dd=abs(x[f"{method}_eps10_f0"][att]-y[kold][att])
                if method=="mwem": worst_mwem=max(worst_mwem,dd)
                else: worst=max(worst,dd)
    print("replication check against V14 (MWEM) and V14D (PrivBayes-style) world 0 (records-only baseline, near-copy positive control and the release at epsilon 10 with no planted rows): largest absolute difference, exact quantities and PrivBayes-style release:",worst,"; MWEM release (not bit-reproducible, band",MWEM_BAND,"):",worst_mwem,flush=True)
    if worst>1e-6 or worst_mwem>MWEM_BAND: sys.exit("REPLICATION CHECK FAILED: V15 at f = 0 differs from V14 or V14D. Stopping. Do not use any V15 result.")
except FileNotFoundError as e: sys.exit("replication check could not run: "+str(e))

jobs=[(c,w) for w in range(1,30) for c in CELLS]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in CELLS}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(H/"analyse_v15.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v15.txt").write_text(out); print(out)
git("add","_drafts/v15/results","_drafts/v15/analysis_output_v15.txt"); git("commit","-m","V15 results and analysis output")
