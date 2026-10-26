"""Start actual localhost processes; no provider calls or academy records."""
import os
import socket
import subprocess
import sys
import time
import requests


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_api_and_streamlit_start_from_repository_root(tmp_path):
    api_port, ui_port = free_port(), free_port()
    env = dict(os.environ, REX_CATALOG_DATA_DIR=str(tmp_path / "runtime-catalog"),
               REX_API_URL=f"http://127.0.0.1:{api_port}")
    commands = [
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(api_port)],
        [sys.executable, "-m", "streamlit", "run", "frontend/app.py", "--server.headless=true",
         "--server.address=127.0.0.1", "--server.port=" + str(ui_port), "--browser.gatherUsageStats=false"],
    ]
    processes = []
    try:
        for command in commands:
            processes.append(subprocess.Popen(command, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0))
        for port, endpoint in ((api_port, "/health"), (ui_port, "/_stcore/health")):
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                try:
                    response = requests.get(f"http://127.0.0.1:{port}{endpoint}", timeout=1)
                    if response.status_code == 200:
                        break
                except requests.exceptions.RequestException:
                    pass
                assert all(p.poll() is None for p in processes), "Application process exited during startup"
                time.sleep(0.1)
            else:
                raise AssertionError("Application did not become healthy in time")
        base = f"http://127.0.0.1:{api_port}"
        assert requests.get(base + "/api/v1/catalog/courses", timeout=5).json()["items"] == []
        assert requests.get(base + "/api/v1/documents/templates", timeout=5).status_code in (401, 503)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
