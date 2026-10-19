# -*- coding: utf-8 -*-
"""本地预览用的多线程静态服务器。

标准库的 python -m http.server 是单线程的，几百张图标会把请求队列堵死，
导致浏览器一直等。这里用 ThreadingHTTPServer 顶替，仅用于本地预览。
"""

from __future__ import annotations

import functools
import http.server
import socketserver
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "docs"
PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt, *args):  # 静音
        pass


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    handler = functools.partial(Handler, directory=str(ROOT))
    with Server(("127.0.0.1", PORT), handler) as httpd:
        print(f"serving {ROOT} at http://127.0.0.1:{PORT}/")
        httpd.serve_forever()
