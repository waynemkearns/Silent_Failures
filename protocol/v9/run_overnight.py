"""Resumable overnight driver for the V9 powered design. Runs one world per process, skips finished worlds.
Usage: MIMIC_CANONICAL_CSV=<csv> python run_overnight.py [first_world] [last_world]   (default 0 99)
Safe to stop and restart: finished worlds are skipped (output file exists)."""
import os,sys,subprocess,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
HERE=Path(__file__).parent; PROTO=HERE.parent/"repaired_protocol"; OUT=HERE/"results"; OUT.mkdir(exist_ok=True)
lo=int(sys.argv[1]) if len(sys.argv)>1 else 0; hi=int(sys.argv[2]) if len(sys.argv)>2 else 99
workers=int(os.environ.get("WORKERS",max(1,(os.cpu_count() or 2)-1)))
def run(w):
    f=PROTO/f"v2_ov_reference_worlds_{w}_{w}.json"; dst=OUT/f.name
    if dst.exists(): return w,"skip"
    env=dict(os.environ,KDE="1",LN="1",TAG="_ov",VOCAB="reference",WORLDS=f"{w}-{w}")
    t=time.time(); r=subprocess.run([sys.executable,str(PROTO/"v8_repaired_protocol.py")],env=env,capture_output=True,text=True)
    if r.returncode==0 and f.exists(): f.replace(dst); return w,f"ok {time.time()-t:.0f}s"
    (OUT/f"error_world_{w}.txt").write_text(r.stdout[-2000:]+r.stderr[-4000:]); return w,"ERROR"
with ThreadPoolExecutor(workers) as ex:
    for w,msg in ex.map(run,range(lo,hi+1)): print(w,msg,flush=True)
