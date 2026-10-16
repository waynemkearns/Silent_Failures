"""Run scanner v2 (unchanged, hash checked) on limits_suite.py. Usage: python run_limits.py"""
import sys, hashlib, json
from pathlib import Path
SC=Path(__file__).with_name("pipeline_scan.py")
H="3f378ee6aedfc7f21ac9963b6d3e15893de4e9f398b02459c08f4c3a94f113e4"
assert hashlib.sha256(SC.read_bytes()).hexdigest()==H, "scanner hash mismatch"
sys.path.insert(0,str(SC.parent)); sys.path.insert(0,str(Path(__file__).parent))
from pipeline_scan import scan_source
from limits_suite import C
rules=["ENC_PER_FRAME","DROPNA_UNSCOPED","ROW_CAP","DEAD_MERGE","POS_SELECT","CONST_OUTPUT"]
rows=[]
for c in C:
    got=any(r["rule"]==c["rule"] for r in scan_source(c["src"],c["id"]) )
    rows.append(dict(c,flag=got))
print(f"cases {len(rows)}; prediction matched the scanner on {sum(r['flag']==r['pred'] for r in rows)}")
for r in rows:
    if r["flag"]!=r["pred"]: print("PREDICTION MISS",r["id"],"predicted",r["pred"],"got",r["flag"])
print()
print(f"{'rule':16s} defects detected  defects missed  benign flagged  benign not flagged")
for ru in rules:
    R=[r for r in rows if r["rule"]==ru]
    d=[r for r in R if r["truth"]=="defect"]; b=[r for r in R if r["truth"]=="benign"]
    print(f"{ru:16s} {sum(r['flag'] for r in d):>2}/{len(d):<2}            {sum(not r['flag'] for r in d):>2}/{len(d):<2}          {sum(r['flag'] for r in b):>2}/{len(b):<2}           {sum(not r['flag'] for r in b):>2}/{len(b):<2}")
print()
print("By kind, defect cases only (detected / total):")
for k in ("canonical","variant"):
    for ru in rules:
        d=[r for r in rows if r["rule"]==ru and r["truth"]=="defect" and r["kind"]==k]
        print(f"  {k:9s} {ru:16s} {sum(r['flag'] for r in d)}/{len(d)}")
print()
print("Missed defects:",", ".join(r["id"] for r in rows if r["truth"]=="defect" and not r["flag"]))
print("False alarms:  ",", ".join(r["id"] for r in rows if r["truth"]=="benign" and r["flag"]))
json.dump(rows,open(Path(__file__).parent/"limits_results.json","w"),indent=1)
