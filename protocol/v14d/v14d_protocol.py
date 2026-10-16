"""V14D job (Part D, PrivBayes-style). Usage: python v14d_protocol.py <cell> <world>      Cells: adult_pb, mimic_pb.
Design: ../../24_FROZEN_DESIGN_V14D.md (read it first).
This file changes no V14 file. It imports the frozen V14 job code unchanged (../v14/v14_protocol.py) and registers one more release method,
'pb': a PrivBayes-style synthesizer, DataSynthesizer 0.1.13 (correlated attribute mode), vendored in ./vendor with one edit
(serial map in place of a multiprocessing Pool in lib/PrivBayes.py; same results, same order).
Everything else in a world (three standard arms, encoding, reference-fitted scaler, attacks, placebo, records-only baseline,
near-copy positive control) is exactly the V14 and V11 code. Release: epsilon is the total budget (DataSynthesizer spends epsilon/2 on the
network and epsilon/2 on the conditional tables), on the same publicly binned data as the V11 MST release.
Network degree k is fixed per dataset and epsilon (table below, rule in the design file)."""
import os,sys,tempfile,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=Path(os.environ.get("V14D_OUT",HERE/"results")); OUT.mkdir(parents=True,exist_ok=True); os.environ["V14_OUT"]=str(OUT)
sys.path.insert(0,str(HERE/"vendor")); sys.path.insert(0,str(HERE.parent/"v14"))
import numpy as np
import v14_protocol as p

# k by number of columns d (15 = Adult, 17 = MIMIC-IV) and epsilon. Rule: largest k in {1,2,3} with
# usefulness n*(eps/2)/((d-k)*2^(k+3)) >= 4 at the smallest matched-arm member count seen in V14 (Adult 522, MIMIC-IV 218), else k = 1.
K={(15,1):1,(15,10):2,(17,1):1,(17,10):1}

def pb_release(mem,ref,cat_idx,eps,seed,n):
    from DataSynthesizer.DataDescriber import DataDescriber
    from DataSynthesizer.DataGenerator import DataGenerator
    D,num_idx,centers=p.bin_release_input(mem,ref,cat_idx); d=mem.shape[1]; k=K[(d,int(round(eps)))]
    tmp=tempfile.mkdtemp(prefix="pb_")
    try:
        f=os.path.join(tmp,"in.csv"); D.to_csv(f,index=False)
        desc=DataDescriber(histogram_bins=20,category_threshold=1000)
        desc.describe_dataset_in_correlated_attribute_mode(f,epsilon=float(eps),k=int(k),
            attribute_to_is_categorical={c:True for c in D.columns},attribute_to_is_candidate_key={c:False for c in D.columns},seed=int(seed))
        j=os.path.join(tmp,"desc.json"); desc.save_dataset_description_to_file(j)
        g=DataGenerator(); g.generate_dataset_in_correlated_attribute_mode(int(n),j,seed=int(seed)); S=g.synthetic_dataset
        S=S.astype(int)
    finally: shutil.rmtree(tmp,ignore_errors=True)
    return p.decode(S,d,n,num_idx,centers)

p.METHODS["pb"]=[1.0,10.0]; p.RELEASE["pb"]=pb_release

if __name__=="__main__": p.job(sys.argv[1],int(sys.argv[2]))
