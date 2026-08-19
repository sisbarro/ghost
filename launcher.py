"""GhostMail launcher: starts the local server and opens the web interface."""

import ctypes
import os
import socket
import threading
import time
import webbrowser
from urllib.request import urlopen

from runtime_paths import DATA_DIR


HOST = "127.0.0.1"
PREFERRED_PORT = 5000
PORT_FILE = os.path.join(DATA_DIR, "server.port")
_mutex_handle = None


def _claim_single_instance() -> bool:
    global _mutex_handle
    if os.name != "nt":
        return True
    _mutex_handle = ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\GhostMail")
    return ctypes.windll.kernel32.GetLastError() != 183


def _existing_url() -> str | None:
    try:
        with open(PORT_FILE, "r", encoding="ascii") as port_file:
            port = int(port_file.read().strip())
        url = f"http://{HOST}:{port}"
        with urlopen(url, timeout=1) as response:
            if response.status == 200:
                return url
    except (OSError, ValueError):
        pass
    return None


def _reopen_existing_instance() -> None:
    for _ in range(20):
        url = _existing_url()
        if url:
            webbrowser.open(url)
            return
        time.sleep(0.1)


def _choose_port() -> int:
    for candidate in (PREFERRED_PORT, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind((HOST, candidate))
            if candidate == PREFERRED_PORT:
                return candidate
            return probe.getsockname()[1]
    raise RuntimeError("Unable to find an available local port.")


def _open_browser(url: str) -> None:
    time.sleep(1.25)
    webbrowser.open(url)


def main() -> None:
    if not _claim_single_instance():
        _reopen_existing_instance()
        return

    from app import app

    port = _choose_port()
    url = f"http://{HOST}:{port}"
    with open(PORT_FILE, "w", encoding="ascii") as port_file:
        port_file.write(str(port))
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()
    try:
        app.run(host=HOST, port=port, debug=False, use_reloader=False)
    finally:
        try:
            os.remove(PORT_FILE)
        except OSError:
            pass


if __name__ == "__main__":
    main()
