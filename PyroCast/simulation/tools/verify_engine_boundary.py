"""Fail if upstream, project additions, generated sources or builds are mixed."""
from pathlib import Path
import argparse
import json
from engine_sources import ROOT, VENDOR, ORDER, verify_upstream, digest
from prepare_engine import OUT
from extensions.cfbt.hooks import render


def verify_generated(output=OUT):
    upstream=verify_upstream()
    output=Path(output)
    manifest=json.loads((output/'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest['upstream_lock_sha256']!=upstream['source_lock_sha256']:
        raise ValueError('Generated sources use a different upstream lock')
    originals={n+'.f90':(VENDOR/'Source'/(n+'.f90')).read_text(encoding='utf-8') for n in ORDER}
    expected,hooks=render(originals)
    if manifest['hooks']!=hooks:
        raise ValueError('Generated hook catalog is stale')
    if {p.name for p in (output/'Source').glob('*.f90')}!=set(originals):
        raise ValueError('Generated source inventory differs')
    touched={r['upstream_file'] for r in hooks}
    entries={e['file']:e for e in manifest['sources']}
    if set(entries)!=set(originals) or len(entries)!=len(manifest['sources']):
        raise ValueError('Generated manifest inventory differs')
    for entry in manifest['extension_inputs']:
        path=(ROOT/entry['file']).resolve()
        if not path.is_relative_to((ROOT/'extensions/cfbt').resolve()) or digest(path)!=entry['sha256']:
            raise ValueError('Extension input was changed; regenerate the build sources')
    for name,text in expected.items():
        path=output/'Source'/name;entry=entries[name]
        role='patched_upstream' if name in touched else 'upstream_unchanged'
        if entry['role']!=role or path.read_text(encoding='utf-8')!=text or digest(path)!=entry['generated_sha256']:
            raise ValueError('Generated file was edited: '+name)
        if entry['upstream_sha256']!=upstream['files'][name]['sha256']:
            raise ValueError('Incorrect upstream provenance: '+name)
        if name not in touched and digest(path)!=upstream['files'][name]['sha256']:
            raise ValueError('Unpatched CFAST file changed: '+name)
    return {'upstream_files':upstream['verified_files'],'upstream_lock_sha256':upstream['source_lock_sha256'],
            'patched_generated_files':sorted(touched),'hook_count':len(hooks),
            'generated_files_verified':len(entries)}


def verify_builds(build_root):
    build_root=Path(build_root).resolve();report={}
    upstream=verify_upstream()
    generated=json.loads((OUT/'MANIFEST.json').read_text(encoding='utf-8'))
    generated_entries={entry['file']:entry for entry in generated['sources']}
    if not build_root.is_relative_to((ROOT/'build').resolve()):
        raise ValueError('Build root is outside simulation/build/')
    for variant in ('baseline','cfbt'):
        folder=build_root/variant
        meta=json.loads((folder/'build.json').read_text(encoding='utf-8'))
        if meta['variant']!=variant or len(meta['sources'])!=len(ORDER) or {Path(e['file']).stem for e in meta['sources']}!=set(ORDER):
            raise ValueError('Invalid engine build manifest')
        if meta['upstream_tag']!=upstream['tag'] or meta['upstream_lock_sha256']!=upstream['source_lock_sha256']:
            raise ValueError('Engine build uses a different upstream release')
        if variant=='baseline' and meta['extension_inputs']:
            raise ValueError('Baseline build includes project additions')
        if variant=='cfbt' and (meta['extension_inputs']!=generated['extension_inputs'] or meta['generated_manifest_sha256']!=digest(OUT/'MANIFEST.json')):
            raise ValueError('Extension build provenance is stale')
        for entry in meta['sources']:
            path=(ROOT/entry['file']).resolve()
            base=(VENDOR/'Source').resolve() if variant=='baseline' else (OUT/'Source').resolve()
            if path.parent!=base or digest(path)!=entry['sha256']:
                raise ValueError('Engine sources do not match declared source boundary')
            if variant=='baseline' and (entry['role']!='upstream_original' or entry['hook_ids']):
                raise ValueError('Baseline build includes an extension hook')
            if variant=='cfbt':
                expected=generated_entries[path.name]
                if entry['role']!=expected['role'] or entry['hook_ids']!=expected['hook_ids']:
                    raise ValueError('Incorrect extension ownership in build manifest')
        exe=folder/('cfast-baseline.exe' if variant=='baseline' else 'cfast-cfbt.exe')
        if digest(exe)!=meta['engine_sha256']:
            raise ValueError('Engine binary does not match its build manifest')
        report[variant]={'source_files':len(meta['sources']),'engine_sha256':meta['engine_sha256']}
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--build-root',type=Path)
    args=parser.parse_args()
    report=verify_generated()
    if args.build_root:report['builds']=verify_builds(args.build_root)
    print(json.dumps(report,ensure_ascii=False,indent=2))
