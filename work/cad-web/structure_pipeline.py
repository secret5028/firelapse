"""Local OCR -> floor groups -> registered common structural candidates."""
from pathlib import Path
import json,subprocess,os
import pypdfium2 as pdfium
from structural_consensus import groups,consensus
import cv2

def run(folder,resources):
 folder=Path(folder);out=folder/'structure';out.mkdir(exist_ok=True)
 ocr=out/'ocr.jsonl'
 if not ocr.exists():
  rows=[]
  with pdfium.PdfDocument(str(folder/'source.pdf')) as doc:
   for i in range(len(doc)):
    pg=doc[i];bmp=pg.render(scale=2600/max(pg.get_size()));im=bmp.to_pil().convert('RGB')
    if im.height>im.width:im=im.rotate(90,expand=True)
    im.save(out/f'page-{i+1}.jpg',quality=92);w,h=im.size;title=out/f'title-{i+1}.png';im.crop((w*.79,h*.68,w,h)).resize((1000,1100)).save(title);rows.append({'page':i+1,'path':str(title.resolve())});bmp.close();pg.close()
  manifest=out/'ocr-input.json';manifest.write_text(json.dumps(rows),'utf8')
  part=out/'ocr.partial.jsonl'
  subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(Path(resources)/'windows_drawing_ocr.ps1'),'-Manifest',str(manifest),'-Output',str(part)],check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  part.replace(ocr)
 rows=[json.loads(l) for l in ocr.read_text('utf-8-sig').splitlines() if l.strip()];g=groups(rows);cache={};result=[]
 for (building,floor),items in g.items():
  pages=tuple(r['page'] for r in items)
  if pages not in cache:
   if len(pages)<2:cache[pages]={'status':'insufficient','walls':[],'accepted':[],'reason':'같은 동·층의 독립 도면이 2개 미만'}
   else:
    r,ref,common=consensus([out/f'page-{n}.jpg' for n in pages]);cache[pages]=r;cv2.imencode('.png',common)[1].tofile(str(out/f'common-{pages[0]}.png'))
  result.append({'building':building,'floor':floor,'pages':list(pages),'referencePage':pages[0],**cache[pages]})
 report={'status':'complete','ocrPages':len(rows),'groups':result,'displayFacilities':['extinguisher','sprinkler','indoorHydrant','standpipe','waterSpray'],'unclassifiedPages':[r['page'] for r in rows if not any(r['page'] in k for k in cache)],'note':'공통선 기반 구조 후보. 서로 다른 층 복제 금지. 임시소방설비는 영구 설비로 표시하지 않음. 제목 OCR은 우측 하단 표제란 형식에 한정.'}
 (out/'report.json').write_text(json.dumps(report,ensure_ascii=False),'utf8');return report
