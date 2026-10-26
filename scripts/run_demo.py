"""Start an isolated TA backend and UI. Ctrl+C stops only the processes this script starts."""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]

def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    if not os.getenv('REX_CATALOG_ADMIN_KEY'):
        print('Set REX_CATALOG_ADMIN_KEY in your local .env first. Never share this key.')
        return 1
    for port in (8010, 8510):
        with socket.socket() as sock:
            if sock.connect_ex(('127.0.0.1',port)) == 0:
                print(f'Port {port} is already in use. Close the previous demo before starting another.')
                return 1
    env = dict(os.environ, REX_APP_MODE='demo', REX_API_URL='http://127.0.0.1:8010')
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    logdir = ROOT/'data'/'demo'/'logs'
    logdir.mkdir(parents=True,exist_ok=True)
    children=[]
    handles=[]
    try:
        backendlog=(logdir/'backend.log').open('a',encoding='utf-8'); handles.append(backendlog)
        children.append(subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port','8010'],cwd=ROOT,env=env,stdout=backendlog,stderr=subprocess.STDOUT,creationflags=flags))
        for attempt in range(40):
            if children[0].poll() is not None:
                raise RuntimeError('Backend could not start. Check data/demo/logs/backend.log locally.')
            try:
                with urlopen('http://127.0.0.1:8010/health',timeout=1) as response:
                    if response.status==200: break
            except OSError:
                time.sleep(.5)
        else:
            raise RuntimeError('Backend startup timed out. Check data/demo/logs/backend.log locally.')
        frontlog=(logdir/'frontend.log').open('a',encoding='utf-8');handles.append(frontlog)
        children.append(subprocess.Popen([sys.executable,'-m','streamlit','run','frontend/app.py','--server.address','127.0.0.1','--server.port','8510','--server.headless','true','--browser.gatherUsageStats','false','--client.toolbarMode','minimal'],cwd=ROOT,env=env,stdout=frontlog,stderr=subprocess.STDOUT,creationflags=flags))
        print('Demo: http://127.0.0.1:8510')
        print('API documentation: http://127.0.0.1:8010/docs')
        print('Open Demo setup in the sidebar. Sign in with your name and the existing staff key from .env.')
        print('Fictional records are kept in data/demo. Your academy records are separate.')
        print('Press Ctrl+C to stop the demo.')
        while all(child.poll() is None for child in children):
            time.sleep(1)
        return 1
    except KeyboardInterrupt:
        return 0
    except RuntimeError as exc:
        print(str(exc));return 1
    finally:
        for child in reversed(children):
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=5)
        for handle in handles: handle.close()

if __name__=='__main__': raise SystemExit(main())
