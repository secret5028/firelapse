"""Local, per-launch shutdown signal shared by the portable supervisor and servers."""
import json
import os
from pathlib import Path
from urllib.request import ProxyHandler, build_opener

SIGNAL_ENV = 'FIRELAPSE_SHUTDOWN_SIGNAL'
OPEN_LOCAL = build_opener(ProxyHandler({}))


def signal_path():
    path = os.environ.get(SIGNAL_ENV)
    return Path(path) if path else None


def stopping():
    path = signal_path()
    return path is not None and path.exists()


def running_calculations(ports):
    for port in ports:
        for route in ('/cfbt/calculation', '/cfbt/lite/mc'):
            with OPEN_LOCAL.open(f'http://127.0.0.1:{port}{route}', timeout=2) as response:
                status = json.load(response)
            if status.get('running') or status.get('server_busy'):
                return True
    return False


def request_shutdown(ports):
    path = signal_path()
    if path is None:
        return {'error': '이 실행 방식은 브라우저 종료를 지원하지 않습니다.'}, 404
    try:
        with path.open('x', encoding='ascii'):
            pass
    except FileExistsError:
        return {'error': 'FireLapse가 종료 요청을 처리 중입니다.'}, 409
    except OSError:
        return {'error': '종료 요청을 저장할 수 없습니다.'}, 503
    accepted = False
    try:
        if running_calculations(ports):
            return {'error': '계산이 진행 중입니다. 완료 후 종료하세요.'}, 409
        path.write_text('stop', encoding='ascii')
        accepted = True
        return {'stopping': True}, 200
    except (OSError, ValueError):
        return {'error': '계산 상태를 확인할 수 없습니다. 잠시 후 다시 시도하세요.'}, 503
    finally:
        if not accepted:
            path.unlink(missing_ok=True)
