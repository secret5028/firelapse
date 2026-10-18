import file_tool as t
from pathlib import Path
import re
source=Path('work/tool-check/소방전기도면-변경.pdf');before=t.sha(source)
r=t.process_file(source)
assert r['kind']=='검토된 예제 모델 재사용'
assert t.sha(source)==before
assert Path(r['output']).parent==source.resolve().parent
r=t.process_file(Path('work/tool-check/다른PDF.pdf'))
assert r['pages']==1 and r['kind'].startswith('자동')
r=t.process_file(Path('work/tool-check/새도면.png'));assert r['pages']==1
target=Path('work/tool-check/보호.html');target.write_text('existing user content')
assert t.safe_output(target.parent,target.name)!=target
assert target.read_text()=='existing user content'
try:
    t.process_file(Path('work/tool-check/손상.pdf'))
    raise AssertionError('must reject corrupt PDF')
except t.pdfium.PdfiumError:pass
h=Path('work/viewer.html').read_text(encoding='utf-8')
ids=re.findall(r'id="([^"]+)"',h);assert len(ids)==len(set(ids))
js=Path('work/app.js').read_text(encoding='utf-8')
requested=re.findall(r"\$\('([^']+)'\)",js)
assert set(requested)<=set(ids),set(requested)-set(ids)
print('PASS exact source matching, source preservation, same-folder outputs, unknown PDF/image extraction, collision protection, corrupt PDF rejection, unique and existing UI IDs.')
