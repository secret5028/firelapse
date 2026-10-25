"""Build a pinned GNU CFAST baseline or the isolated CFBT variant."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
from engine_sources import ROOT, VENDOR, ORDER, verify_upstream, digest


def build(variant="baseline", output_root=None, optimization="O1", debug=False):
    if variant not in ('baseline','cfbt'):
        raise ValueError('Unknown engine variant')
    upstream=verify_upstream()
    source = VENDOR/'Source'
    generated=None
    if variant=='cfbt':
        from prepare_engine import prepare, OUT
        generated=prepare()
        source=OUT/'Source'
    compiler = ROOT / "tools" / "w64devkit" / "bin" / "gfortran.exe"
    if not compiler.exists():
        compiler = Path(shutil.which("gfortran") or "gfortran")
    build_root=Path(output_root).resolve() if output_root else ROOT/'build'
    if not build_root.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Build artifacts must stay inside simulation/build/')
    folder = build_root / variant
    folder.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PATH"] = str(compiler.parent) + os.pathsep + environment.get("PATH", "")
    if optimization not in ('O1', 'O2'):
        raise ValueError('Supported optimization levels are O1 and O2')
    flags = ["-"+optimization, "-cpp", "-finit-local-zero", "-ffree-line-length-none", "-fallow-argument-mismatch"]
    if debug:
        flags.append('-g')
    sources = []
    for name in ORDER:
        path = source / (name + '.f90')
        obj = folder / (name + ".o")
        subprocess.run([str(compiler), *flags, "-c", str(path), "-o", str(obj)], cwd=folder, env=environment, check=True)
        role='upstream_original'
        hooks=[]
        if generated:
            entry=next(r for r in generated['sources'] if r['file']==name+'.f90')
            role=entry['role'];hooks=entry['hook_ids']
        sources.append({'file':path.relative_to(ROOT).as_posix(),'sha256':digest(path),
                        'role':role,'hook_ids':hooks})
    exe = folder / ("cfast-cfbt.exe" if variant == "cfbt" else "cfast-baseline.exe")
    subprocess.run([str(compiler), "-static", "-Wl,--stack,268435456", "-o", str(exe), *[str(folder / (n + ".o")) for n in ORDER]], cwd=folder, env=environment, check=True)
    verify_upstream()
    metadata={'variant':variant,'upstream_tag':upstream['tag'],
              'upstream_lock_sha256':upstream['source_lock_sha256'],
              'sources':sources,'flags':flags,'engine_sha256':digest(exe),
              'extension_inputs':generated['extension_inputs'] if generated else []}
    if generated:
        metadata['generated_manifest_sha256']=digest(OUT/'MANIFEST.json')
    (folder/'build.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(exe)
    return exe


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=["baseline", "cfbt"], default="baseline", nargs="?")
    parser.add_argument('--output-root',type=Path,help='Optional isolated artifact root under simulation/build/')
    parser.add_argument('--optimization',choices=['O1','O2'],default='O1')
    parser.add_argument('--debug',action='store_true',help='Include source locations for a project-owned diagnostic run')
    args=parser.parse_args()
    build(args.variant,args.output_root,args.optimization,args.debug)
