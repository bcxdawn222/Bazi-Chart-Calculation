from __future__ import annotations

import argparse
import logging
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIR = ROOT / "admin"
LOG_FILE = ROOT / "logs" / "admin-preview.log"


def configure_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="本地预览运营配置页面")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    configure_logging()
    handler = partial(SimpleHTTPRequestHandler, directory=str(ADMIN_DIR))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    logging.info("运营页面预览：http://%s:%s/ops-config.html", args.host, args.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logging.info("运营页面预览已停止")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
