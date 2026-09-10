"""One-command launcher: python launch.py. Installs two dependencies if needed."""
import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import urllib.request
import webbrowser
from runtime_paths import RESOURCE_ROOT

ROOT = RESOURCE_ROOT


def main():
    if not getattr(sys,"frozen",False) and any(importlib.util.find_spec(name) is None for name in ("numpy","PIL")):
        env = ROOT / ".venv"
        python = env / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if Path(sys.prefix).resolve() != env.resolve():
            if not python.exists():
                print("Première installation des dépendances (Internet requis)…",flush=True)
                subprocess.check_call([sys.executable,"-m","venv",str(env)])
            subprocess.check_call([str(python),"-m","pip","install","-r",str(ROOT / "requirements.txt")])
            return subprocess.call([str(python),str(__file__),*sys.argv[1:]])
        subprocess.check_call([sys.executable,"-m","pip","install","-r",str(ROOT / "requirements.txt")])
    from server import Application, Server, local_addresses
    parser = argparse.ArgumentParser(description="Fat Tiles — atelier de terrain local")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--host",default="0.0.0.0")
    parser.add_argument("--no-browser",action="store_true")
    parser.add_argument("--offline",action="store_true")
    args = parser.parse_args()
    try:
        server = Server((args.host,args.port),Application(offline=args.offline))
    except OSError as exc:
        # Re-running the single launch command should simply reopen our app.
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/api/status",timeout=2) as response:
                ours = response.headers.get("Server", "").startswith("FatTiles/")
            if ours:
                url = f"http://localhost:{args.port}"
                print(f"Fat Tiles fonctionne déjà : {url}\nLe serveur existant est conservé.")
                if not args.no_browser:
                    webbrowser.open(url)
                return 0
        except OSError:
            pass
        print(f"Impossible de démarrer : {exc}\nEssayez : python launch.py --port 8766")
        return 1
    url = f"http://localhost:{server.server_port}"
    print(f"\nFat Tiles est prêt.\nPC : {url}",flush=True)
    if args.host != "127.0.0.1":
        for address in local_addresses(server.server_port):
            print(f"Téléphone, même Wi-Fi : {address}",flush=True)
    print("Gardez ce terminal ouvert. Ctrl+C pour arrêter.\n",flush=True)
    if not args.no_browser:
        threading.Timer(.7,lambda:webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nFat Tiles arrêté.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
