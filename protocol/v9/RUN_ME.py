"""One-shot overnight run. Usage (Windows):  python RUN_ME.py
Checks script hashes against 16_FROZEN_DESIGN_V9.md, runs 100 worlds (resumable), retries errors once, writes analysis_output.txt."""
import os,sys,re,hashlib,subprocess
from pathlib import Path
H=Path(__file__).resolve().parent; D=H.parent; AUD=D.parent
os.environ.setdefault("MIMIC_CANONICAL_CSV",r"<LOCAL_PATH>")
if not Path(os.environ["MIMIC_CANONICAL_CSV"]).exists(): sys.exit("Data file not found: "+os.environ["MIMIC_CANONICAL_CSV"])
doc=(AUD/"16_FROZEN_DESIGN_V9.md").read_text()
bad=[]
for h,rel in re.findall(r"^\s+([0-9a-f]{64})\s+(\S+)$",doc,re.M):
    p=D/rel; got=hashlib.sha256(p.read_bytes()).hexdigest()
    # tolerate CRLF conversion
    got2=hashlib.sha256(p.read_bytes().replace(b"\r\n",b"\n")).hexdigest()
    if h not in (got,got2): bad.append(rel)
if bad: sys.exit("HASH MISMATCH, stopping: "+", ".join(bad))
print("hashes OK",flush=True)
def git(*a): return subprocess.run(["git","-C",str(AUD)]+list(a),capture_output=True,text=True)
if git("rev-parse","--git-dir").returncode!=0: 
    r=git("init"); 
    if r.returncode: sys.exit("git init failed: "+r.stderr)
for k,v in (("user.name","the author <redacted>"),("user.email","the author.<redacted>@<redacted>")):
    if not git("config",k).stdout.strip(): git("config",k,v)
files=["16_FROZEN_DESIGN_V9.md","_drafts/repaired_protocol/v8_repaired_protocol.py","_drafts/repaired_protocol/kde_ratio_own.py","_drafts/overnight/run_overnight.py","_drafts/overnight/analyse_overnight.py","_drafts/overnight/RUN_ME.py"]
r=git("add",*files)
if r.returncode: sys.exit("git add failed: "+r.stderr)
r=git("commit","-m","V9 frozen design and scripts, committed before the 100-world run",*files)
if r.returncode and "nothing to commit" not in (r.stdout+r.stderr): sys.exit("git commit failed: "+r.stdout+r.stderr)
h=git("rev-parse","HEAD").stdout.strip(); t=git("log","-1","--format=%cI").stdout.strip()
(H/"FREEZE_RECORD.txt").write_text(f"freeze commit {h}\ncommit time {t}\nfiles: {', '.join(files)}\n")
print("frozen at commit",h,t,flush=True)
for attempt in (1,2):
    subprocess.run([sys.executable,str(H/"run_overnight.py"),"0","99"],check=False)
    if len(list((H/"results").glob("v2_ov_reference_worlds_*.json")))==100: break
n=len(list((H/"results").glob("v2_ov_reference_worlds_*.json"))); print("worlds finished:",n)
r=subprocess.run([sys.executable,str(H/"analyse_overnight.py")],capture_output=True,text=True)
out=f"worlds finished: {n}\n"+r.stdout+r.stderr
(H/"analysis_output.txt").write_text(out); print(out)
git("add","_drafts/overnight/results","_drafts/overnight/analysis_output.txt")
git("commit","-m","V9 results and analysis output")
