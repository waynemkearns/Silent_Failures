"""One-shot V11 run for the two MST cells. Usage (Windows):  python RUN_V11.py
Design: ../../18_FROZEN_DESIGN_V11.md (addendum to 17_FROZEN_DESIGN_V10.md).
Steps: hash check -> git freeze commit -> smoke test (world 0 of each MST cell, one at a time, 3 h limit) -> worlds 1..49 of both cells
with 4 workers until the time limit -> analysis -> results commit. Safe to re-run: finished worlds are skipped."""
import os,sys,re,hashlib,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent; V10=D/"v10"; RES=V10/"results"; RES.mkdir(exist_ok=True)
MAX_HOURS=float(os.environ.get("V11_MAX_HOURS","10")); SMOKE_TIMEOUT=3*3600; JOB_CAP=3*3600; WORKERS=int(os.environ.get("WORKERS","4")); THREADS=os.environ.get("THREADS","2")
TMP=Path(r"E:\Temp")
try: TMP.mkdir(parents=True,exist_ok=True); [os.environ.__setitem__(k,str(TMP)) for k in ("TEMP","TMP","TMPDIR")]
except Exception as e: print("could not use E:\\Temp, continuing with the default temp folder:",e,flush=True)
# set environment variable MIMIC_CANONICAL_CSV to your local path
# set environment variable ADULT_CSV to your local path
for k in ("MIMIC_CANONICAL_CSV","ADULT_CSV"):
    if not Path(os.environ[k]).exists(): sys.exit(f"Data file not found for {k}: {os.environ[k]}")
doc=(AUD/"18_FROZEN_DESIGN_V11.md").read_text(); bad=[]; nchk=0
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    nchk+=1; b=(D/rel).read_bytes()
    if h not in (hashlib.sha256(b).hexdigest(),hashlib.sha256(b.replace(b"\r\n",b"\n")).hexdigest()): bad.append(rel)
if bad or nchk<4: sys.exit("HASH MISMATCH or hashes missing, stopping: "+", ".join(bad))
print("hashes OK",nchk,"files",flush=True)
def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0:
    r=git("init")
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","author"),("user.email","author@example.invalid")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["18_FROZEN_DESIGN_V11.md","_drafts/v11/v11_protocol.py","_drafts/v11/RUN_V11.py"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V11 frozen design addendum and scripts, committed before the V11 run",*files)
if r.returncode and not any(m in (r.stdout+r.stderr) for m in ("nothing to commit","no changes added to commit")): sys.exit("git commit failed: "+r.stdout+r.stderr)
rec=H/"FREEZE_RECORD_V11.txt"
if not rec.exists():
    hh=git("rev-parse","HEAD").stdout.strip(); tt=git("log","-1","--format=%cI").stdout.strip()
    rec.write_text(f"freeze commit {hh}\ncommit time {tt}\nfiles: {', '.join(files)}\n"); print("frozen at commit",hh,tt,flush=True)
else: print("freeze record already exists, kept:",rec.read_text().splitlines()[0],flush=True)
for c in ("adult_mst","mimic_mst"):   # keep the V10 drop notices out of the V11 analysis, but do not delete them
    s=RES/f"{c}_STATUS.txt"
    if s.exists(): s.rename(RES/f"{c}_V10_dropped_at_smoke_notice.txt")
START=time.time(); dropped=set()
def run(cell,w,timeout,threads=None):
    if cell in dropped or (RES/f"{cell}_w{w}.json").exists(): return "skip"
    env=dict(os.environ)
    if threads:
        for k in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS"): env[k]=threads
    t=time.time()
    try: r=subprocess.run([sys.executable,str(H/"v11_protocol.py"),cell,str(w)],capture_output=True,text=True,timeout=timeout,env=env)
    except subprocess.TimeoutExpired: return "TIMEOUT"
    (RES/f"log_{cell}_w{w}.txt").write_text(r.stdout[-3000:]+r.stderr[-3000:])
    if r.returncode!=0: (RES/f"error_{cell}_w{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return "ERROR"
    print(f"{cell} w{w} ok in {time.time()-t:.0f} s, elapsed {(time.time()-START)/3600:.2f} h",flush=True); return "ok"
print("SMOKE TEST: world 0 of each MST cell, one at a time, 3 h limit each",flush=True)
for c in ("adult_mst","mimic_mst"):
    s=run(c,0,SMOKE_TIMEOUT); print(c,"world 0:",s,flush=True)
    if s in ("ERROR","TIMEOUT"):
        dropped.add(c); (RES/f"{c}_STATUS.txt").write_text(f"cell dropped at smoke test: {s}. See progress_{c}_w0.log and error_{c}_w0.txt\n")
jobs=[(c,w) for w in range(1,50) for c in ("adult_mst","mimic_mst")]
def go(j):
    if time.time()-START>MAX_HOURS*3600: return j,"time limit, not started"
    return j,run(j[0],j[1],JOB_CAP,THREADS)
with ThreadPoolExecutor(WORKERS) as ex:
    for j,s in ex.map(go,jobs):
        if s not in ("ok","skip"): print(j,s,flush=True)
cells=["adult_laplace","adult_mst","mimic_mst"]
n={c:len(list(RES.glob(f"{c}_w*.json"))) for c in cells}; print("worlds finished:",n,flush=True)
r=subprocess.run([sys.executable,str(V10/"analyse_v10.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr; (H/"analysis_output_v11.txt").write_text(out); print(out)
git("add","_drafts/v10/results","_drafts/v11/analysis_output_v11.txt"); git("commit","-m","V11 results and analysis output")
