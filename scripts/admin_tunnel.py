"""经 SSH 把服务器本机 80 端口转发到本地，用于外网 80 未放行时访问运营后台。密码从 REMOTE_PASSWORD 读取。"""
from __future__ import annotations

import argparse
import getpass
import os
import select
import socketserver
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support.ssh_hosts import create_ssh_client  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="SSH 隧道访问运营后台")
    parser.add_argument("--host", default="124.223.182.85")
    parser.add_argument("--user", default="ubuntu")
    parser.add_argument("--local-port", type=int, default=8080)
    args = parser.parse_args()
    password = os.environ.get("REMOTE_PASSWORD") or getpass.getpass("SSH password: ")
    client = create_ssh_client(False)
    client.connect(args.host, username=args.user, password=password, timeout=15, auth_timeout=15, banner_timeout=15)
    client.get_transport().set_keepalive(30)
    transport = client.get_transport()

    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            channel = transport.open_channel("direct-tcpip", ("127.0.0.1", 80), self.request.getpeername())
            try:
                while True:
                    ready, _, _ = select.select([self.request, channel], [], [])
                    if self.request in ready:
                        data = self.request.recv(65536)
                        if not data:
                            break
                        channel.sendall(data)
                    if channel in ready:
                        data = channel.recv(65536)
                        if not data:
                            break
                        self.request.sendall(data)
            finally:
                channel.close()

    class Server(socketserver.ThreadingTCPServer):
        daemon_threads = True
        allow_reuse_address = True

    server = Server(("127.0.0.1", args.local_port), Handler)
    print(f"隧道已建立：http://127.0.0.1:{args.local_port}/admin/  （Ctrl+C 关闭）", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
