"""Generate disposable CFBT sources from verified upstream + project-owned hooks."""
from pathlib import Path
import difflib
import json
import sys
from engine_sources import ROOT, VENDOR, ORDER, verify_upstream, digest

sys.path.insert(0,str(ROOT))
from extensions.cfbt.hooks import render, HERE

OUT=ROOT/'build/generated/cfbt'


def prepare(output=OUT):
    upstream=verify_upstream()
    output=Path(output).resolve()
    if not output.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Generated engine sources must stay inside simulation/build/')
    originals={name+'.f90':(VENDOR/'Source'/(name+'.f90')).read_text(encoding='utf-8') for name in ORDER}
    patched,hooks=render(originals)
    touched={r['upstream_file'] for r in hooks}
    sources=output/'Source';sources.mkdir(parents=True,exist_ok=True)
    if {p.name for p in sources.glob('*.f90')}-set(originals):
        raise ValueError('Unexpected source in generated engine directory')
    entries=[];diff=[]
    for filename,original in originals.items():
        target=sources/filename
        if filename in touched:
            target.write_text(patched[filename],encoding='utf-8')
            diff.extend(difflib.unified_diff(original.splitlines(True),patched[filename].splitlines(True),
                                           fromfile='upstream/'+filename,tofile='generated/'+filename))
        else:
            target.write_bytes((VENDOR/'Source'/filename).read_bytes())
        entries.append({'file':filename,'role':'patched_upstream' if filename in touched else 'upstream_unchanged',
                        'upstream_sha256':upstream['files'][filename]['sha256'],
                        'generated_sha256':digest(target),
                        'hook_ids':[r['id'] for r in hooks if r['upstream_file']==filename]})
    inputs=[HERE/'hooks.py',*sorted((HERE/'fortran').glob('*.inc'))]
    manifest={'upstream_tag':upstream['tag'],'upstream_lock_sha256':upstream['source_lock_sha256'],
              'generated_only':True,'edit_sources_in':'extensions/cfbt/',
              'extension_inputs':[{'file':p.relative_to(ROOT).as_posix(),'sha256':digest(p)} for p in inputs],
              'sources':entries,'hooks':hooks}
    (output/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'CFAST_DIFF.patch').write_text(''.join(diff),encoding='utf-8')
    (output/'README.txt').write_text('Generated build input. Do not edit.\nUpstream: vendor/cfast-7.7.7/Source\nProject code: extensions/cfbt/\nRegenerate: python tools/prepare_engine.py\n',encoding='utf-8')
    verify_upstream()
    return manifest


if __name__=='__main__':
    data=prepare()
    print(f"Verified upstream and generated {len(data['sources'])} sources / {len(data['hooks'])} explicit hooks at {OUT}")
