#!/usr/bin/env python3
"""
Container entrypoint.

Runs the version scan once on start-up and then again every day at local
midnight, and serves the generated ``versions.html`` over HTTP.

Everything here is Python standard library only, matching ``get_versions.py``.

Environment variables:
    DATA_DIR   Directory for state files and versions.html (default: /data)
    PORT       TCP port to listen on                       (default: 80)
    TZ         Standard tz name (e.g. America/New_York) controls when
               "midnight" is; defaults to UTC.
"""
import http.server
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(APP_DIR, "get_versions.py")
DATA_DIR = os.environ.get("DATA_DIR", "/data")
HTML_PATH = os.path.join(DATA_DIR, "versions.html")
PORT = int(os.environ.get("PORT", "80"))
SCAN_TIMEOUT = 600  # seconds


def log(msg: str) -> None:
    print(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}", flush=True)


def write_placeholder() -> None:
    """Ensure there is always something to serve before the first scan finishes."""
    if os.path.exists(HTML_PATH):
        return
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(
            "<!DOCTYPE html><meta charset='utf-8'>"
            "<meta http-equiv='refresh' content='30'>"
            "<title>Thales Product Versions</title>"
            "<body style='font-family:system-ui,sans-serif;margin:3rem;color:#1a1f2b'>"
            "<h1 style='color:#071b3a'>Thales Product Versions</h1>"
            "<p>The first version scan is running. This page will refresh automatically.</p>"
        )


def run_scan() -> None:
    log("Running version scan ...")
    try:
        result = subprocess.run(
            [sys.executable, SCRIPT, "--html", HTML_PATH],
            cwd=DATA_DIR,
            capture_output=True,
            text=True,
            timeout=SCAN_TIMEOUT,
        )
    except Exception as e:  # noqa: BLE001 - want any failure logged, not fatal
        log(f"Scan failed to run: {e}")
        return

    if result.stderr.strip():
        log("scan progress:\n" + result.stderr.strip())
    if result.returncode != 0:
        log(f"Scan exited {result.returncode}; stdout:\n{result.stdout.strip()}")
    else:
        log(f"Scan complete; report written to {HTML_PATH}")


def seconds_until_midnight() -> float:
    now = datetime.now()
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (nxt - now).total_seconds()


def scheduler() -> None:
    while True:
        wait = seconds_until_midnight()
        log(f"Next scheduled scan at local midnight (in {wait / 3600:.2f} h)")
        time.sleep(wait)
        run_scan()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DATA_DIR, **kwargs)

    def send_head(self):  # serves GET and HEAD
        if self.path in ("/", "/index.html"):
            self.path = "/versions.html"
        return super().send_head()

    def log_message(self, fmt, *args):
        log("http " + (fmt % args))


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    write_placeholder()

    # Refresh on boot (in the background so the server comes up immediately),
    # then keep refreshing at midnight.
    threading.Thread(target=run_scan, daemon=True).start()
    threading.Thread(target=scheduler, daemon=True).start()

    log(f"Serving {DATA_DIR} on port {PORT}  (/ and /index.html -> versions.html)")
    httpd = http.server.ThreadingHTTPServer(("", PORT), Handler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down")
        httpd.shutdown()


if __name__ == "__main__":
    main()
