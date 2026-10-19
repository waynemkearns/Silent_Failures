"""Runs V18 and then V19, one after the other, in one command. Usage (Windows):  python RUN_V18_V19.py
V19 starts only if RUN_V18.py ended normally (exit code 0). Both scripts are unchanged and run exactly as they would on their own.
Safe to re-run: each script skips worlds that are already finished and keeps its freeze record."""
import subprocess,sys
from pathlib import Path
H=Path(__file__).resolve().parent; D=H.parent
for name,folder in (("RUN_V18.py",D/"v18"),("RUN_V19.py",H)):
    print(f"===== starting {name} =====",flush=True)
    r=subprocess.run([sys.executable,"-u",name],cwd=str(folder))
    print(f"===== {name} ended with exit code {r.returncode} =====",flush=True)
    if r.returncode!=0: sys.exit(f"{name} did not end normally, so the next run was not started. Send me the text above.")
print("===== both runs finished =====",flush=True)
