"""Offline file selection, PDF/image extraction and HTML preparation. No LLM calls."""
from pathlib import Path
import argparse,base64,ctypes,hashlib,html,io,json,os,sys,time,uuid
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageSequence

VERSION='0.1.0'
SAMPLE_HASH='7908fa6546129ea8d54d28c23775a7a2a485cc2f5cc9e13116c9a80f1ea70ad9'
MARKER='<!--fire-space-generated-v1-->'
SUPPORTED={'.pdf','.png','.jpg','.jpeg','.tif','.tiff','.bmp'}
BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

def resource(name):return BASE/name
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def select_files():
    from ctypes import wintypes as w
    class OPENFILENAMEW(ctypes.Structure):
        _fields_=[('lStructSize',w.DWORD),('hwndOwner',w.HWND),('hInstance',w.HINSTANCE),('lpstrFilter',w.LPCWSTR),('lpstrCustomFilter',w.LPWSTR),('nMaxCustFilter',w.DWORD),('nFilterIndex',w.DWORD),('lpstrFile',w.LPWSTR),('nMaxFile',w.DWORD),('lpstrFileTitle',w.LPWSTR),('nMaxFileTitle',w.DWORD),('lpstrInitialDir',w.LPCWSTR),('lpstrTitle',w.LPCWSTR),('Flags',w.DWORD),('nFileOffset',w.WORD),('nFileExtension',w.WORD),('lpstrDefExt',w.LPCWSTR),('lCustData',ctypes.c_ssize_t),('lpfnHook',ctypes.c_void_p),('lpTemplateName',w.LPCWSTR),('pvReserved',ctypes.c_void_p),('dwReserved',w.DWORD),('FlagsEx',w.DWORD)]
    buf=ctypes.create_unicode_buffer(65536);dlg=OPENFILENAMEW();dlg.lStructSize=ctypes.sizeof(dlg);dlg.lpstrFile=ctypes.cast(buf,w.LPWSTR);dlg.nMaxFile=len(buf)
    dlg.lpstrFilter='도면 파일 (PDF·이미지)\0*.pdf;*.png;*.jpg;*.jpeg;*.tif;*.tiff;*.bmp\0모든 파일\0*.*\0\0';dlg.nFilterIndex=1;dlg.lpstrTitle='처리할 도면 파일을 선택하세요 · 여러 파일 선택 가능';dlg.Flags=0x80000|0x800|0x1000|0x8
    api=ctypes.windll.comdlg32.GetOpenFileNameW;api.argtypes=[ctypes.POINTER(OPENFILENAMEW)];api.restype=w.BOOL
    if not api(ctypes.byref(dlg)):
        err=ctypes.windll.comdlg32.CommDlgExtendedError()
        if err:raise RuntimeError('파일 선택 창 오류: '+str(err))
        return []
    parts=buf[:].split('\0');parts=[p for p in parts if p]
    return [Path(parts[0])] if len(parts)==1 else [Path(parts[0])/name for name in parts[1:]]

def data_image(im):
    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2200,2200));b=io.BytesIO();im.save(b,'JPEG',quality=82)
    return {'image':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode(),'width':im.width,'height':im.height}

def extract_pages(path,progress=print):
    pages=[]
    if path.suffix.lower()=='.pdf':
        doc=pdfium.PdfDocument(str(path))
        try:
            if len(doc)>300:raise ValueError('한 파일은 300쪽까지 지원합니다. PDF를 나누어 선택해주세요.')
            for i in range(len(doc)):
                page=doc[i]
                try:
                    w,h=page.get_size();bitmap=page.render(scale=min(2.5,2200/max(w,h)))
                    try:entry=data_image(bitmap.to_pil())
                    finally:bitmap.close()
                    tp=page.get_textpage()
                    try:entry['text']=' '.join(tp.get_text_range().split())[:500]
                    finally:tp.close()
                    entry.update({'number':i+1,'source':path.name});pages.append(entry)
                    progress(f'  {i+1}/{len(doc)}쪽 추출')
                finally:page.close()
        finally:doc.close()
    else:
        with Image.open(path) as im:
            if getattr(im,'n_frames',1)>300:raise ValueError('이미지는 300프레임까지 지원합니다.')
            for i,frame in enumerate(ImageSequence.Iterator(im)):
                entry=data_image(frame.copy());entry.update({'number':i+1,'source':path.name,'text':''});pages.append(entry)
    if not pages:raise ValueError('읽을 수 있는 페이지가 없습니다.')
    return pages

def js_json(data):return json.dumps(data,ensure_ascii=False).replace('</','<\\/').replace('\u2028','\\u2028').replace('\u2029','\\u2029')

def render_review(name,digest,pages):
    from hydraulic_embed import embed_hydraulics
    template=resource('folder_review.html').read_text(encoding='utf-8')
    marker='/* STRUCTURE_EDITOR_V1:'
    if marker in template:
        begin=template.index(marker);end=template.index('\n});\n</script>',begin)
        old=resource('structure-editor.js').read_text(encoding='utf-8')
        tail=old[old.index('\n(function(){\n const details='):]
        template=template[:begin]+resource('guided-editor.js').read_text(encoding='utf-8')+tail+template[end:]
    template=template.replace("{wall:'#dc3b45',door:'#ffd343',window:'#ffe375'}", "{wall:'#ffd568',door:'#ff626a',window:'#50b7e4'}")
    template=template.replace('ctx.moveTo(...sh.a);ctx.lineTo(...sh.b);ctx.stroke()', "(sh.path||[sh.a,sh.b]).forEach((q,i)=>i?ctx.lineTo(...q):ctx.moveTo(...q));ctx.stroke()")
    template=template.replace("s.b.length!==2)throw Error('잘못된 도형입니다.')", "s.b.length!==2||(s.path&&(!Array.isArray(s.path)||s.path.length<2||s.path.some(q=>!Array.isArray(q)||q.length!==2||!q.every(Number.isFinite)))))throw Error('잘못된 도형입니다.')")
    # Older templates embed the editor. Keep the page key independent of editable floor names.
    template=template.replace("const key=p=>[p.sourcePage,p.building,p.floor].join('|');", "const key=p=>{const i=state.pages.indexOf(p),src=D.pages[i];return src.pageId||`${D.sourceHash}:page-${src.number??i+1}:index-${i}:render-${src.width}x${src.height}`;};")
    libs={'core':resource('three.core.js').read_text(encoding='utf-8'),'module':resource('three.module.js').read_text(encoding='utf-8')}
    content=MARKER+'\n'+template.replace('__DATA__',js_json({'name':name,'sourceHash':digest,'pages':pages}),1).replace('__LIBS__',js_json(libs),1)
    # Shared renderer dependencies; no per-document generator required.
    helpers=[]
    for filename in ['guide-geometry.js','touch-view.js','elevator-display.js','wall-surface.js','floor-details.js']:
        helpers.append(resource(filename).read_text('utf8'))
    helpers.append(resource('fire-facilities.js').read_text('utf8').split('(function(){',1)[0])
    tag='<script>\n'+'\n'.join(helpers).replace('</script','<\\/script')+'\n</script>'
    content=content.replace('<header>',tag+'\n<header>',1)
    layout=resource('review-layout.js').read_text('utf8')+'\n'+resource('common-facilities.js').read_text('utf8')
    content=content.replace('</html>','<script>'+layout+'</script></html>',1)
    content=embed_hydraulics(content,BASE,digest,name)
    addons=[]
    if any(p.get('initial',{}).get('detectorDraft') for p in pages):
        content=content.replace("{wall:'#dc3b45',door:'#ffd343',window:'#ffe375'}", "{wall:'#ffd568',door:'#ff626a',window:'#50b7e4'}")
        addon=resource('draft-handoff.js').read_text(encoding='utf-8')
        addons.append(addon)
    stages=resource('workflow-stages.js').read_text(encoding='utf-8')
    addons.append(stages)
    for filename in ['annotation-store.js','annotation-ui.js','result-bundle.js']:
        addons.append(resource(filename).read_text(encoding='utf-8'))
    content+='\n<script>window.addEventListener("DOMContentLoaded",()=>{\n'+'\n'.join(addons)+'\n});</script>'
    return content

def safe_output(folder,name):
    dest=folder/name
    if dest.exists():
        try:
            with dest.open('r',encoding='utf-8') as f:owned=f.read(len(MARKER))==MARKER
        except (OSError,UnicodeError):owned=False
        if not owned:dest=folder/(dest.stem+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]+dest.suffix)
    return dest

def atomic_write(path,content):
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_text(content,encoding='utf-8');os.replace(temp,path)
    finally:
        if temp.exists():temp.unlink()

def process_file(path,progress=print):
    path=Path(path).resolve()
    if not path.is_file():raise ValueError('파일을 찾을 수 없습니다.')
    if path.suffix.lower() not in SUPPORTED:raise ValueError('지원 형식: PDF, PNG, JPG, TIFF, BMP')
    progress(path.name);digest=sha(path)
    # Reuse a reviewed model only for this exact PDF. A filename match is insufficient.
    sample=digest==SAMPLE_HASH
    if sample:
        output=safe_output(path.parent,path.stem+'_소방공간뷰.html')
        content=MARKER+'\n'+resource('sample.html').read_text(encoding='utf-8')
        if not output.exists() or output.read_text(encoding='utf-8')!=content:atomic_write(output,content)
        progress('  해당 원본의 수작업 검토 모델로 생성 완료')
        return {'input':path.name,'output':str(output),'kind':'검토된 예제 모델 재사용','llm':False,'sha256':digest}
    pages=extract_pages(path,progress)
    output=safe_output(path.parent,path.stem+'_도면검토.html');atomic_write(output,render_review(path.name,digest,pages))
    progress('  도면 검토 HTML 생성 완료 · 구조 판독/보정 필요')
    return {'input':path.name,'output':str(output),'kind':'자동 페이지 추출 + 수동 구조 보정','llm':False,'sha256':digest,'pages':len(pages)}

def message(text,title='소방공간뷰',flags=0):return ctypes.windll.user32.MessageBoxW(None,text,title,flags)

def process_factory_set(files,progress=print):
    """Reuse reviewed factory only when all three exact source images are selected."""
    if len(files) not in [3,20] or len({Path(p).resolve().parent for p in files})!=1:return None
    industrial=len(files)==20
    expected=set(json.loads(resource('industrial-hashes.json' if industrial else 'factory-hashes.json').read_text(encoding='utf-8')).values())
    if {sha(p) for p in files}!=expected:return None
    dest=safe_output(Path(files[0]).resolve().parent,'강화산업단지_통합_소방공간뷰.html' if industrial else '당산리공장_1-3층_소방공간뷰.html')
    atomic_write(dest,MARKER+'\n'+resource('industrial-sample.html' if industrial else 'factory-sample.html').read_text(encoding='utf-8'))
    progress('  통합 검토 모델 생성 완료 · 수작업 판독 예제 재사용')
    return {'input':'강화산업단지 원본 20장' if industrial else '당산리 공장 원본 이미지 3장','output':str(dest),'kind':'검토된 통합 예제 모델 재사용','llm':False}

def main():
    parser=argparse.ArgumentParser(description='도면 파일 옆에 오프라인 HTML 결과를 생성합니다. LLM 호출 없음.')
    parser.add_argument('files',nargs='*');parser.add_argument('--no-open',action='store_true');args=parser.parse_args()
    interactive=not args.files
    if os.name=='nt':ctypes.windll.kernel32.SetConsoleTitleW('소방공간뷰 · 도면 처리')
    print('소방공간뷰 0.1\n도면 선택 → 같은 폴더에 결과 생성\n새 도면은 자동 추출 후 구조 보정이 필요합니다. LLM은 사용하지 않습니다.\n',flush=True)
    files=[Path(p) for p in args.files] if args.files else select_files()
    if not files:return 0
    done=[];errors=[]
    files=list(dict.fromkeys(files))
    try:
        factory=process_factory_set(files,lambda s:print(s,flush=True))
        if factory:done.append(factory);files=[]
    except Exception as e:
        print('통합 예제 적용 불가, 개별 파일 처리:',str(e),flush=True)
    for path in dict.fromkeys(files):
        try:done.append(process_file(path,lambda s:print(s,flush=True)))
        except KeyboardInterrupt:print('취소했습니다. 이미 생성한 결과는 유지됩니다.');return 2
        except Exception as e:errors.append(path.name+': '+str(e));print('처리 실패:',errors[-1],flush=True)
    print(f'\n완료 {len(done)}개 / 실패 {len(errors)}개',flush=True)
    if interactive:
        text=f'완료 {len(done)}개 / 실패 {len(errors)}개\n결과는 선택한 원본 파일과 같은 폴더에 저장했습니다.'
        if any(r['kind'].startswith('자동') for r in done):text+='\n\n새 도면: 페이지 추출 완료. HTML에서 치수·벽·문·창 보정 후 3D 초안을 볼 수 있습니다. 자동 설비 판독·경로는 아직 지원하지 않습니다.'
        if errors:text+='\n\n'+'\n'.join(errors[:5])
        if done and not args.no_open:
            if message(text+'\n\n첫 결과를 열까요?',flags=4)==6:os.startfile(done[0]['output'])
        else:message(text)
    elif done and not args.no_open:os.startfile(done[0]['output'])
    return 1 if errors else 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:
        if os.name=='nt':message('실행 오류: '+str(e))
        raise
