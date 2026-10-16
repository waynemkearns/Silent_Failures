"""V11 job wrapper. Usage: python v11_protocol.py <cell> <world>   (cells: adult_mst, mimic_mst)
Runs the unchanged V10 job (../v10/v10_protocol.py) and only adds progress lines for each MST fit, written to
../v10/results/progress_<cell>_w<world>.log. It changes no data, seed, attack or analysis step."""
import sys,time
from pathlib import Path
H=Path(__file__).resolve().parent; sys.path.insert(0,str(H.parent/"v10"))
import v10_protocol as v

def main(cell,w):
    log=v.OUT/f"progress_{cell}_w{w}.log"
    def note(s):
        with open(log,"a") as f: f.write(time.strftime("%Y-%m-%d %H:%M:%S ")+s+"\n")
    orig=v.mst_release; k=[0]
    def timed(mem,ref,cat_idx,eps,seed,n):
        k[0]+=1; t=time.time(); note(f"MST fit {k[0]} of 9, epsilon {eps:g}, started")
        out=orig(mem,ref,cat_idx,eps,seed,n); note(f"MST fit {k[0]} done in {time.time()-t:.0f} s"); return out
    v.mst_release=timed
    note("job started"); v.job(cell,w); note("job finished")

if __name__=="__main__": main(sys.argv[1],int(sys.argv[2]))
