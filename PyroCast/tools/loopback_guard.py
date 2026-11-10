"""Reject requests whose Host header does not name this loopback server.

Binding to 127.0.0.1 does not stop DNS rebinding: a remote page can point its
own hostname at 127.0.0.1, and its requests then arrive from the local browser
with ``Origin: http://<that name>:<port>`` and a matching Host header, which
passes a same-origin comparison. Only the Host value reveals it.
"""

LOOPBACK_NAMES = ('127.0.0.1', 'localhost', '[::1]')


def host_allowed(host, port):
    """True for an absent Host (non-browser HTTP/1.0 client) or a loopback name on this port."""
    if host is None:
        return True
    return host.strip().lower() in {f'{name}:{port}' for name in LOOPBACK_NAMES}


class LoopbackHostMixin:
    """Place before the request-handler base class; covers every method and subclass."""

    def parse_request(self):
        if not super().parse_request():
            return False
        if host_allowed(self.headers.get('Host'), self.server.server_port):
            return True
        self.send_error(403, 'Host not allowed')
        return False
