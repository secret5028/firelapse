"""Host-header guard: a rebinding hostname must not reach any loopback endpoint."""
import http.client
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
from loopback_guard import LoopbackHostMixin, host_allowed


class Handler(LoopbackHostMixin, BaseHTTPRequestHandler):
    def answer(self):
        self.send_response(200); self.send_header('Content-Length', '2'); self.end_headers(); self.wfile.write(b'ok')
    do_GET = do_POST = answer

    def log_message(self, *_): pass


class LoopbackGuardTest(unittest.TestCase):
    def test_host_names(self):
        for host in ('127.0.0.1:8780', 'localhost:8780', 'LOCALHOST:8780', '[::1]:8780', None):
            self.assertTrue(host_allowed(host, 8780), host)
        for host in ('evil.invalid:8780', '127.0.0.1:8781', '127.0.0.1', '127.0.0.1.evil.invalid:8780', '', 'localhost:8780.evil.invalid'):
            self.assertFalse(host_allowed(host, 8780), host)

    def test_requests(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        port = server.server_port
        def status(method, host):
            conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
            try:
                conn.putrequest(method, '/', skip_host=True)
                conn.putheader('Host', host)
                if method == 'POST': conn.putheader('Content-Length', '0')
                conn.endheaders()
                return conn.getresponse().status
            finally:
                conn.close()
        try:
            for method in ('GET', 'POST'):
                self.assertEqual(status(method, f'127.0.0.1:{port}'), 200)
                self.assertEqual(status(method, f'localhost:{port}'), 200)
                # Same-origin from the attacker's point of view, so an Origin comparison alone passes it.
                self.assertEqual(status(method, f'evil.invalid:{port}'), 403)
        finally:
            server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()
