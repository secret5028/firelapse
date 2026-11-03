"""Read-only, self-contained viewer packaging. Never runs a simulation."""
import base64
import copy
import gzip
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit, quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / 'simulation/viewer'
LIMIT = 50 * 1024 * 1024


def packed(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()
    return base64.b64encode(gzip.compress(raw, mtime=0)).decode('ascii')


def sample_playback(source, interval):
    if interval not in (10, 20):
        raise ValueError('출력 간격은 10 또는 20초입니다')
    if interval == 10:
        return source
    data = copy.deepcopy(source)
    times = data['time_s']
    indices = [i for i, t in enumerate(times) if t % interval == 0 or i == len(times)-1]
    def series(value):
        if isinstance(value, dict):
            return {k: series(v) for k, v in value.items()}
        if isinstance(value, list) and len(value) == len(times):
            return [value[i] for i in indices]
        return value
    # Only time-series namespaces; never decimate geometry, IDs or event records.
    data['solvers'] = series(data['solvers'])
    for fire in data['fires']:
        fire['Q_kW'] = series(fire['Q_kW'])
        fire['visuals'] = series(fire.get('visuals', {}))
    data['time_s'] = [times[i] for i in indices]
    data['limits'] = [*data.get('limits', []), '단독 파일 20초 표시 표본: 중간 최고값·짧은 조건 충족은 생략될 수 있음. 재계산 아님.']
    return data


def build_export(origin, case, state, interval=10):
    """Fetch only this local viewer's read endpoints; package their exact outputs."""
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,160}', case):
        raise ValueError('사례 ID 형식 오류')
    if not isinstance(state, dict) or len(json.dumps(state)) > 100000:
        raise ValueError('화면 상태 크기 오류')
    def read(path):
        with urlopen(origin + path, timeout=60) as response:
            return response.read()
    def value(path):
        return json.loads(read(path))
    playback = sample_playback(value('/cfbt/lite/result/' + quote(case)), interval)
    playback['case_id'] = case
    # Use the same model URL/HTML as the online handler, including its attach hook.
    with urlopen(origin + '/', timeout=30) as response:
        model_url = urlsplit(response.url).path
        html = response.read().decode('utf-8')
    directory = model_url.rsplit('/', 1)[0] + '/'
    routes = {directory+'building.json': value(directory+'building.json'),
              directory+'legacy-context.json': value(directory+'legacy-context.json'),
              '/cfbt/lite/active.json': playback,
              '/cfbt/lite/result/'+case: playback}
    for path in ['/cfbt/lite/doors', '/cfbt/lite/screening', '/cfbt/r8/schema',
                 '/cfbt/lite/fire-load-table', '/cfbt/model-info']:
        routes[path] = value(path)
    job = directory.strip('/').split('/')[-1]
    routes['/api/jobs/'+job+'/hydraulics'] = value('/api/jobs/'+job+'/hydraulics')
    routes['/cfbt/r8/review'] = {'batch_state': None, 'comparison': None, 'progress': {}}
    routes['/cfbt/lite/mc'] = {'running': False, 'available': False, 'server_busy': False}
    catalog = value('/cfbt/lite/catalog.json')
    row = next(r for r in catalog['cases'] if r['id'] == case)
    routes['/cfbt/lite/catalog.json'] = {'cases': [{'id': case, 'label': row['label']}],
        'progress_text': '단독 HTML · 보기 전용', 'reuse_by_case': {}}
    config = ROOT/'simulation/config/lite-door-overrides.json'
    corrections = json.loads(config.read_text('utf-8')) if config.exists() else {}
    modules = {}
    def resolve(spec, parent):
        if spec == 'three': return '/cad-assets/three.module.js'
        if spec.startswith('three/addons/'): return '/cad-assets/addons/'+spec[13:]
        if spec.startswith(('/', './', '../')): return urljoin(parent, spec)
        raise ValueError('외부 모듈은 내보내기에 허용되지 않습니다: '+spec)
    pattern = re.compile(r"(\bfrom\s*|\bimport\s*\(\s*|\bimport\s*)(['\"])([^'\"]+\.js|three|three/addons/[^'\"]+)(\2)")
    relative = re.compile(r"(['\"])(\./[^'\"]+\.js)\1")
    def translate(code, parent):
        def link(spec):
            path = resolve(spec, parent)
            if not path.startswith(('/cfbt/', '/cad-assets/')): raise ValueError('모듈 경로 오류')
            if path not in modules:
                modules[path] = ''  # break cycles
                modules[path] = translate(read(path).decode('utf-8'), path)
            return 'pc:'+path
        code = pattern.sub(lambda m: m[1]+m[2]+link(m[3])+m[4], code)
        # Legacy menu modules are selected through string variables.
        return relative.sub(lambda m: m[1]+link(m[2])+m[1], code)
    html = re.sub(r'<script type="importmap">.*?</script>', '', html, flags=re.S)
    scripts = []
    def module_tag(m):
        scripts.append(translate(m[1], model_url))
        return ''
    html = re.sub(r'<script type="module">(.*?)</script>', module_tag, html, flags=re.S)
    html = html.replace('<link rel="stylesheet" href="/cfbt/overlay.css">',
                        '<style>'+read('/cfbt/overlay.css').decode('utf-8')+'</style>')
    envelope = {'schema': 'pyrocast.offline/1', 'case_id': case, 'interval_s': interval,
        'base_path': directory, 'state': state, 'door_overrides': corrections,
        'fixed_openings': corrections.get('fixed_state'), 'route_result': state.get('route_result'),
        'vehicle': state.get('route', {}).get('vehicle'), 'routes': routes,
        'modules': modules, 'scripts': scripts}
    from lite_ai_tools import Tools
    from lite_ai_briefing import list_reports
    envelope['assistant_reports']=list_reports(Tools(),{'building':playback['building_sha256'],'case':case})
    pako = (VIEWER/'vendor/pako_inflate.min.js').read_text('utf-8')
    license_text = (VIEWER/'vendor/pako-LICENSE.txt').read_text('utf-8').replace('--', '—')
    boot = (VIEWER/'offline_bootstrap.js').read_text('utf-8')
    csp = "default-src 'none'; script-src 'unsafe-inline' blob:; style-src 'unsafe-inline' blob:; img-src data: blob:; font-src data:; connect-src 'none'; worker-src blob:; object-src 'none'; base-uri 'none'; form-action 'none'"
    html = html.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="'+csp+'">', 1)
    # Compressed JSON and module sources cannot terminate a script element.
    tail = '<!-- pako 2.1.0 license\n'+license_text+'--><script>'+pako+'</script><script id="pcOfflineData" type="application/octet-stream">'+packed(envelope)+'</script><script>'+boot+'</script>'
    html = html.replace('</body>', tail+'</body>')
    output = html.encode('utf-8')
    return output, {'bytes': len(output), 'interval_s': interval, 'case_id': case,
                    'offer_20s': len(output)>LIMIT, 'modules': len(modules)}
