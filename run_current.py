"""Portable entry point for the preserved v30 scenario; writes a new output folder."""
from pathlib import Path
import subprocess, sys
root=Path(__file__).resolve().parent
cmd=[sys.executable,str(root/'work/cad_cfast_multifloor.py'),
     '--ignition-config',str(root/'work/cfast_fuel_groups_v30.json'),
     '--ceiling-config',str(root/'work/cfast_ceiling_heights_v30.json'),
     '--output','home-run','--max-time-step','0.25',*sys.argv[1:]]
raise SystemExit(subprocess.call(cmd,cwd=root))
