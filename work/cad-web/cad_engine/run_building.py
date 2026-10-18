"""건물 폴더 하나 일괄 처리: DWG → DXF(dwg2dxf) → 층별 평면 추출 → 층 정렬 3D.
python run_building.py <도면수집\\관리번호 폴더> [--out 출력폴더] [--dwg2dxf 경로] [--levels 0.9,6.4,...]
- 층 평면 판정: 도면 안 제목 문자 'N 층 평 면 도' / '지하N층' / '옥탑층' (공백 무시). 지붕평면·배치도·입면은 제외.
- 층 높이: 도면 안 층별 LEVEL 표(1FFL +900 …) 또는 입면도('2nd FLOOR' +7,500) 자동, 실패 시 --levels.
- dwg2dxf: --dwg2dxf, 환경변수 DWG2DXF, PATH 순으로 찾음. 같은 이름 .dxf 가 이미 있으면 변환 생략."""
import sys, os, re, glob, json, shutil, argparse, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ezdxf
from cad_plan import run as plan_run
import cad_build3d


def title_of(fn):
    d = ezdxf.readfile(fn)
    ts = []
    for e in d.modelspace().query('TEXT MTEXT'):
        t = (e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text())
        ts.append(re.sub(r'\s+', '', t))
    for t in ts:
        if '평면도' not in t or re.search(r'지붕|배치|확대|부분|단위세대', t): continue
        m = re.search(r'지하(\d+)층', t)
        if m: return f'B{m.group(1)}'
        if '옥탑' in t: return 'PH'
        m = re.search(r'(\d+)층', t)
        if m: return f'{m.group(1)}F'
    base = os.path.basename(fn)
    m = re.search(r'지하\s*(\d+)\s*층', base)
    if m and '평면' in base: return f'B{m.group(1)}'
    if re.search(r'지붕|배치', base): return None
    m = re.search(r'평면도\s*(\d+)\s*층|(\d+)\s*층\s*평면', base)
    if m: return f'{m.group(1) or m.group(2)}F'
    return None


def sl_level(fn):
    """평면 주기 'N층 SL ±0 = GL ±X,XXX' → 층 바닥 레벨(m). 1층 'GL ±0' → 0"""
    d = ezdxf.readfile(fn); found = []
    def walk(es, dep=0):
        for e in es:
            t = e.dxftype()
            if t in ('TEXT', 'MTEXT'):
                try: s = e.dxf.text if t == 'TEXT' else e.plain_text()
                except Exception: continue
                s = re.sub(r'%%[pP]|±', '±', s)
                m = re.search(r'층\s*SL\s*±?\s*0?\s*=\s*GL\s*(±\s*0|[+-]\s*[\d,]+)', s)
                if m:
                    v = m.group(1).replace(' ', '').replace(',', '')
                    found.append(0.0 if v.startswith('±') else float(v) / 1000)
            elif t == 'INSERT' and dep < 3:
                try: walk(e.virtual_entities(), dep + 1)
                except Exception: pass
    walk(d.modelspace())
    return found[0] if found else None


def key(n):
    if n.startswith('B'): return -int(n[1:])
    if n == 'PH': return 999
    return int(n[:-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--out'); ap.add_argument('--dwg2dxf'); ap.add_argument('--levels')
    ap.add_argument('--map', default=os.path.join(HERE, 'layer_map.json'))
    ap.add_argument('--fire-dir', help='기존 정렬된 <층>_fire.json 및 기준 <층>.json 폴더. 검증 후 보조 판정 통합')
    a = ap.parse_args()
    out = a.out or os.path.join(HERE, 'out', os.path.basename(os.path.normpath(a.folder)))
    if a.fire_dir and os.path.abspath(a.fire_dir) == os.path.abspath(out):
        raise ValueError('--fire-dir은 새 출력폴더와 달라야 기존 기준 평면이 보존됩니다.')
    os.makedirs(out, exist_ok=True); dxfdir = os.path.join(out, 'dxf'); os.makedirs(dxfdir, exist_ok=True)
    exe = a.dwg2dxf or os.environ.get('DWG2DXF') or shutil.which('dwg2dxf')
    dxfs = []
    for dwg in sorted(glob.glob(os.path.join(a.folder, '*.dwg'))):
        tgt = os.path.join(dxfdir, os.path.splitext(os.path.basename(dwg))[0] + '.dxf')
        if not os.path.exists(tgt):
            if not exe: sys.exit('dwg2dxf 를 찾을 수 없음 (--dwg2dxf 또는 DWG2DXF 지정)')
            subprocess.run([exe, '-y', '-o', tgt, dwg], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        if os.path.exists(tgt): dxfs.append(tgt)
    for f in glob.glob(os.path.join(a.folder, '*.dxf')): dxfs.append(f)
    floors, others = {}, []
    for f in dxfs:
        try: n = title_of(f)
        except Exception as e: print('읽기 실패', f, e); continue
        if n and n not in floors: floors[n] = f
        else: others.append(f)
    if not floors: sys.exit('층 평면도를 찾지 못함')
    order = sorted(floors, key=key)
    print('층 평면:', {n: os.path.basename(floors[n]) for n in order})
    js = []
    for n in order:
        r = plan_run(floors[n], os.path.join(out, n), a.map, floor=n)
        from cad_pipeline import finalize_plan
        fire = reference = None
        if a.fire_dir:
            fire = os.path.join(a.fire_dir, n + '_fire.json')
            reference = os.path.join(a.fire_dir, n + '.json')
            if not os.path.isfile(fire) or not os.path.isfile(reference):
                raise FileNotFoundError(f'{n}: 소방 대조 파일과 기준 평면을 모두 확인하세요: {a.fire_dir}')
        r = finalize_plan(r,os.path.join(out,n+'_evidence'),floor=n,fire_json=fire,
            fire_reference_plan=reference,input_source=floors[n],base_image=os.path.join(out,n+'_plan.png'))
        if r['quality']['errors']: raise ValueError(f'{n}: 형상 검사 실패. 검사 결과를 확인하세요.')
        json.dump(r,open(os.path.join(out,n+'.json'),'w',encoding='utf-8'),ensure_ascii=False)
        print(n, json.dumps(r['stats'], ensure_ascii=False))
        js.append(os.path.join(out, n + '.json'))
    # 층 높이: 표가 든 도면(평면 또는 입면)을 찾아 사용
    argv = [os.path.join(out, 'building')] + js + ['--names', ','.join(order)]
    if a.levels:
        argv += ['--levels=' + a.levels]
    else:
        L = None
        # 1순위: 층별 평면의 'N층 SL ±0 = GL ±X' 주기(층 바닥 절대 레벨)
        sl = {n: sl_level(floors[n]) for n in order}
        if sum(v is not None for v in sl.values()) >= max(2, len(order) // 2):
            lv = [sl[n] for n in order] + [None]
            L = lv; print('층 높이 출처: 층별 SL=GL 주기', {n: v for n, v in sl.items()})
        for f in ([] if L else [floors[n] for n in order] + others):
            try: fl, top = cad_build3d.levels_from_elev(f)
            except Exception: continue
            ks = [key(n) for n in order if n != 'PH']
            if not fl or not all(k in fl for k in ks if k > 0): continue
            fl = dict(fl)
            lv = []
            for n in order:
                k = key(n)
                if n == 'PH': lv.append(top if top else None)
                else: lv.append(fl.get(k))
            # 표에 없는 층은 비워 둠(nan) → cad_build3d 가 용도별 기본 층고로 채움
            nxt = fl.get(max(ks) + 1) if 'PH' not in order else None
            if 'PH' in order:   # 옥탑 위: 옥탑보다 높은 다음 레벨(옥탑지붕 등)
                ph = lv[order.index('PH')]
                above = [v for v in fl.get('_extra', []) if ph is not None and v > ph + 1.0]
                lv.append(above[0] if above else None)
            else:
                lv.append(nxt or top)
            L = lv; print('층 높이 출처:', os.path.basename(f)); break
        if L: argv += ['--levels=' + ','.join('nan' if v is None else f'{v:.3f}' for v in L)]
    sys.argv = ['cad_build3d.py'] + argv
    cad_build3d.main()
    print('완료 →', out)


if __name__ == '__main__':
    main()
