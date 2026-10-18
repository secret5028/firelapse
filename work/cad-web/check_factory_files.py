from pathlib import Path
import file_tool as t
root=Path('work/factory-check')
files=[root/f'{n}층 평면도.jpg' for n in [1,2,3]]
expected=set(__import__('json').loads(Path('work/factory-hashes.json').read_text()).values())
assert {t.sha(p) for p in files}==expected
artifact=Path('outputs/소방공간뷰-당산리공장-1~3층.html').read_text(encoding='utf-8')
assert (root/'당산리공장_1-3층_소방공간뷰.html').read_text(encoding='utf-8')==t.MARKER+'\n'+artifact
assert t.process_factory_set(files[:1]) is None
assert t.process_factory_set([files[0],files[0],files[2]]) is None
assert t.process_factory_set([files[0],files[1],Path('work/tool-check/새도면.png')]) is None
assert '/*BOOT*/' not in artifact
assert len(artifact)>4000000
print('PASS bundled EXE output matches verified HTML; exact 3-file identity; missing/duplicate/unrelated input rejected; source hashes preserved.')
