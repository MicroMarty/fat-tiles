"""Fat Tiles local HTTP service. Disk-backed DEM cache and streaming tile exports."""
import concurrent.futures
import gzip
import io
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import socket
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from PIL import Image
import terrain
from runtime_paths import RESOURCE_ROOT, USER_ROOT

ROOT = RESOURCE_ROOT
ATTRIBUTION = (ROOT / "ATTRIBUTION.txt").read_text(encoding="utf-8")
DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TOPO_URL = "https://a.tile.opentopomap.org/{z}/{x}/{y}.png"
MAX_CACHE_BYTES = 10 * 1024**3


class TileUnavailable(Exception):
    pass


class Cancelled(Exception):
    pass


class TileStore:
    def __init__(self, path, offline=False):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self.offline = offline
        self.network = threading.BoundedSemaphore(4)
        self.compute = threading.BoundedSemaphore(4)
        self.stripes = [threading.RLock() for _ in range(64)]
        self.lock = threading.RLock()
        self.metrics_cache = OrderedDict()
        self.bytes = sum(p.stat().st_size for p in self.path.rglob("*.png"))
        self.downloaded = 0

    def filename(self, kind, z,x,y):
        return self.path / kind / str(z) / str(x) / f"{y}.png"

    def tile(self, kind, z,x,y):
        path = self.filename(kind,z,x,y)
        with self.stripes[hash((kind,z,x,y)) % len(self.stripes)]:
            if path.exists():
                return path.read_bytes()
            if self.offline:
                raise TileUnavailable(f"Tuile {z}/{x}/{y} absente du cache. Téléchargez cette zone avec Internet.")
            with self.network:
                template = DEM_URL if kind == "dem" else TOPO_URL
                request = urllib.request.Request(template.format(z=z,x=x,y=y), headers={"User-Agent":"FatTiles/1.0 (local terrain analysis)","Accept":"image/png"})
                try:
                    with urllib.request.urlopen(request, timeout=18) as response:
                        data = response.read(2*1024*1024 + 1)
                    if len(data) > 2*1024*1024:
                        raise ValueError("Tuile trop volumineuse")
                    with Image.open(io.BytesIO(data)) as image:
                        if image.size != (256,256):
                            raise ValueError("Dimensions de tuile incorrectes")
                        image.verify()
                except (OSError, ValueError) as exc:
                    raise TileUnavailable(f"Source {'DEM' if kind == 'dem' else 'OpenTopoMap'} indisponible pour {z}/{x}/{y}. Vérifiez Internet ou réessayez. ({type(exc).__name__})") from exc
                with self.lock:
                    if self.bytes + len(data) > MAX_CACHE_BYTES or shutil.disk_usage(self.path).free < 300*1024**2:
                        raise TileUnavailable("Cache plein (limite 10 Go) ou espace disque insuffisant. Libérez de l’espace dans data/cache.")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    temporary = path.with_suffix(".part")
                    temporary.write_bytes(data)
                    temporary.replace(path)
                    self.bytes += len(data)
                    self.downloaded += 1
                return data

    def metrics(self,z,x,y):
        key = (z,x,y)
        with self.lock:
            if key in self.metrics_cache:
                self.metrics_cache.move_to_end(key)
                return self.metrics_cache[key]
        with self.compute:
            padded = terrain.padded_tile(z,x,y, lambda zz,xx,yy: terrain.decode_terrarium(self.tile("dem",zz,xx,yy)))
            metrics = terrain.horn(padded, terrain.ground_resolution(z,y))
            metrics.flags.writeable = False
            with self.lock:
                self.metrics_cache[key] = metrics
                self.metrics_cache.move_to_end(key)
                while len(self.metrics_cache) > 32:
                    self.metrics_cache.popitem(last=False)
            return metrics


def write_export(path, plan, filters, store, fmt, composite, progress, cancelled):
    """At most one RGBA tile is held during export; TMS rows only in MBTiles."""
    metadata = {"name":"Fat Tiles — sélection de terrain", "format":"png", "type":"baselayer" if composite else "overlay", "version":"1", "minzoom":str(plan["minzoom"]), "maxzoom":str(plan["maxzoom"]), "bounds":",".join(map(str,plan["bounds"])), "attribution":ATTRIBUTION, "description":"Masque dérivé du DEM Mapzen Terrarium. Horn, échelle sphérique corrigée par latitude. " + json.dumps(filters.__dict__, ensure_ascii=False), "center":f"{(plan['bounds'][0]+plan['bounds'][2])/2},{(plan['bounds'][1]+plan['bounds'][3])/2},{plan['minzoom']}"}
    db, archive = None, None
    try:
        if fmt == "xyz":
            archive = zipfile.ZipFile(path,"w",compression=zipfile.ZIP_STORED)
            archive.writestr("metadata.json",json.dumps({**metadata,"scheme":"xyz","bounds":plan["bounds"],"minzoom":plan["minzoom"],"maxzoom":plan["maxzoom"]},ensure_ascii=False,indent=2))
            archive.writestr("ATTRIBUTION.txt",ATTRIBUTION)
        else:
            db = sqlite3.connect(path)
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute("CREATE TABLE metadata (name TEXT, value TEXT)")
            db.executemany("INSERT INTO metadata VALUES (?,?)",metadata.items())
            if fmt == "mbtiles":
                db.execute("CREATE TABLE tiles (zoom_level INTEGER, tile_column INTEGER, tile_row INTEGER, tile_data BLOB)")
                db.execute("CREATE UNIQUE INDEX tile_index ON tiles (zoom_level,tile_column,tile_row)")
            else:
                db.execute("CREATE TABLE tiles (x INTEGER,y INTEGER,z INTEGER,s INTEGER DEFAULT 0,image BLOB,PRIMARY KEY(x,y,z,s))")
                db.execute("CREATE TABLE info (minzoom INTEGER,maxzoom INTEGER,tilenumbering TEXT,tilesize INTEGER,ellipsoid INTEGER,inverted_y INTEGER,timecolumn TEXT,expireminutes INTEGER,url TEXT)")
                db.execute("INSERT INTO info VALUES (?,?,?,?,?,?,?,?,?)",(plan["minzoom"],plan["maxzoom"],"simple",256,0,0,"no",0,""))
        for index,(z,x,y) in enumerate(plan["tiles"]):
            if cancelled():
                raise Cancelled()
            metrics = store.metrics(z,x,y)
            image = terrain.png_tile(metrics,filters,plan["bounds"],(z,x,y),composite)
            if archive:
                archive.writestr(f"{z}/{x}/{y}.png",image)
            elif fmt == "mbtiles":
                db.execute("INSERT INTO tiles VALUES (?,?,?,?)",(z,x,2**z-1-y,image))
            else:
                db.execute("INSERT INTO tiles (x,y,z,image) VALUES (?,?,?,?)",(x,y,z,image))
            if db and index % 50 == 0:
                db.commit()
            progress(index+1,plan["count"])
        if db:
            db.commit()
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Le contrôle SQLite a échoué.")
    finally:
        if db:
            db.close()
        if archive:
            archive.close()


class Application:
    def __init__(self, data_dir=None, export_dir=None, offline=False):
        self.data = Path(data_dir or USER_ROOT / "data")
        self.exports = Path(export_dir or USER_ROOT / "exports")
        self.exports.mkdir(parents=True,exist_ok=True)
        self.store = TileStore(self.data / "cache",offline)
        self.lock = threading.RLock()
        self.jobs = OrderedDict()
        self.regions_file = self.data / "regions.json"
        try:
            self.regions = json.loads(self.regions_file.read_text(encoding="utf-8"))
        except (OSError,ValueError):
            self.regions = []

    def estimate(self,obj):
        plan = terrain.plan_region(obj)
        missing = sum(not self.store.filename("dem",*tile).exists() for tile in plan["sources"])
        return {key:value for key,value in plan.items() if key not in ("tiles","sources")} | {"source_count":len(plan["sources"]),"missing":missing,"download_mb_estimate":round(missing*.065,1),"export_mb_max":round(plan["count"]*.27,1),"limit":terrain.MAX_TILES}

    def start_job(self,obj):
        plan = terrain.plan_region(obj)
        kind = obj.get("kind","export")
        fmt = obj.get("format","mbtiles")
        if kind not in ("export","prepare") or fmt not in ("mbtiles","xyz","osmand"):
            raise ValueError("Type de tâche ou format inconnu.")
        filters = terrain.Filters.parse(obj.get("filters"))
        composite = obj.get("composite",False)
        if type(composite) is not bool:
            raise ValueError("Mode d’export invalide.")
        if shutil.disk_usage(self.exports).free < plan["count"]*300000 + 300*1024**2:
            raise ValueError("Espace disque insuffisant pour cet export.")
        with self.lock:
            if any(j["state"] in ("queued","running") for j in self.jobs.values()):
                raise ValueError("Une opération est déjà en cours. Attendez sa fin ou annulez-la.")
            jobid = uuid.uuid4().hex
            job = {"id":jobid,"kind":kind,"state":"queued","done":0,"total":len(plan["sources"]) if kind == "prepare" else plan["count"],"message":"Préparation…","cancel":False}
            self.jobs[jobid] = job
            while len(self.jobs) > 30:
                self.jobs.popitem(last=False)
        threading.Thread(target=self.run_job,args=(job,obj,plan,filters,fmt,composite),daemon=True).start()
        return dict(job)

    def run_job(self,job,obj,plan,filters,fmt,composite):
        temporary = None
        def progress(done,total):
            with self.lock:
                job.update(done=done,total=total)
        try:
            job.update(state="running",message="Téléchargement du terrain…" if job["kind"] == "prepare" else "Calcul et écriture des tuiles…")
            if job["kind"] == "prepare":
                # Bounded queue: only four submitted requests, including cancellation.
                source = iter(plan["sources"])
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                    pending = {pool.submit(self.store.tile,"dem",*t) for t in [next(source,None) for _ in range(4)] if t is not None}
                    done = 0
                    while pending:
                        completed,pending = concurrent.futures.wait(pending,return_when=concurrent.futures.FIRST_COMPLETED)
                        for future in completed:
                            future.result()
                            done += 1
                            progress(done,len(plan["sources"]))
                            if job["cancel"]:
                                raise Cancelled()
                            tile = next(source,None)
                            if tile is not None:
                                pending.add(pool.submit(self.store.tile,"dem",*tile))
                region = {"id":job["id"],"bounds":plan["bounds"],"minzoom":plan["minzoom"],"maxzoom":plan["maxzoom"],"count":plan["count"],"date":time.strftime("%Y-%m-%d %H:%M")}
                with self.lock:
                    self.regions.append(region)
                    tmp = self.regions_file.with_suffix(".part")
                    tmp.write_text(json.dumps(self.regions,ensure_ascii=False),encoding="utf-8")
                    tmp.replace(self.regions_file)
                job["message"] = "Zone prête hors ligne aux zooms choisis. Fond Relief local disponible."
            else:
                extension = {"mbtiles":"mbtiles","xyz":"zip","osmand":"sqlitedb"}[fmt]
                name = f"fat-tiles-{time.strftime('%Y%m%d-%H%M%S')}-{job['id'][:6]}.{extension}"
                destination = self.exports / name
                temporary = destination.with_suffix(destination.suffix + ".part")
                write_export(temporary,plan,filters,self.store,fmt,composite,progress,lambda:job["cancel"])
                if job["cancel"]:
                    raise Cancelled()
                temporary.replace(destination)
                job.update(filename=name,url=f"/exports/{name}",size=destination.stat().st_size,message="Export terminé et vérifié.")
            job["state"] = "done"
        except Cancelled:
            job.update(state="cancelled",message="Opération annulée. Les données déjà téléchargées restent en cache.")
        except Exception as exc:
            job.update(state="error",message=str(exc))
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
                Path(str(temporary)+"-journal").unlink(missing_ok=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        # Windows SO_REUSEADDR otherwise lets two local instances steal requests.
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        super().server_bind()

    def __init__(self,address,app):
        self.app = app
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = "FatTiles/1.0"

    def log_message(self,fmt,*args):
        if len(args) > 1 and str(args[1]) not in ("200","304"):
            super().log_message(fmt,*args)

    def reply(self,status,data,content_type="application/json",compressed=False):
        if isinstance(data,(dict,list)):
            data = json.dumps(data,ensure_ascii=False,allow_nan=False).encode("utf-8")
        elif isinstance(data,str):
            data = data.encode("utf-8")
        zipped = compressed and "gzip" in self.headers.get("Accept-Encoding","")
        if zipped:
            data = gzip.compress(data,compresslevel=2)
        self.send_response(status)
        self.send_header("Content-Type",content_type)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Cache-Control","no-store" if content_type == "application/json" else "no-cache")
        if zipped:
            self.send_header("Content-Encoding","gzip")
            self.send_header("Vary","Accept-Encoding")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        try:
            self.get()
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass
        except TileUnavailable as exc:
            self.reply(503,{"error":str(exc)})
        except (ValueError,KeyError) as exc:
            self.reply(400,{"error":str(exc)})
        except Exception as exc:
            self.log_error("%s",exc)
            self.reply(500,{"error":"Erreur interne. Consultez le terminal du serveur."})

    def get(self):
        path = urllib.parse.urlsplit(self.path).path
        app = self.server.app
        if path == "/api/status":
            addresses = local_addresses(self.server.server_port)
            return self.reply(200,{"offline":app.store.offline,"cache_mb":round(app.store.bytes/1024**2,1),"regions":app.regions,"urls":addresses,"maxzoom":terrain.MAX_ZOOM,"max_tiles":terrain.MAX_TILES})
        match = re.fullmatch(r"/api/(terrain|relief|topo)/(\d+)/(\d+)/(\d+)",path)
        if match:
            kind,z,x,y = match.groups()
            z,x,y = int(z),int(x),int(y)
            if not 0 <= z <= terrain.MAX_ZOOM or not 0 <= x < 2**z or not 0 <= y < 2**z:
                raise ValueError("Coordonnées de tuile invalides.")
            if kind == "topo":
                return self.reply(200,app.store.tile("topo",z,x,y),"image/png")
            metrics = app.store.metrics(z,x,y)
            if kind == "relief":
                return self.reply(200,terrain.png_tile(metrics),"image/png")
            return self.reply(200,metrics.tobytes()+terrain.relief_rgba(metrics).tobytes(),"application/octet-stream",compressed=True)
        match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})",path)
        if match:
            with app.lock:
                job = app.jobs.get(match[1])
                return self.reply(200,dict(job)) if job else self.reply(404,{"error":"Opération introuvable."})
        if path.startswith("/exports/"):
            name = path.removeprefix("/exports/")
            if not re.fullmatch(r"fat-tiles-[\w-]+\.(mbtiles|zip|sqlitedb)",name):
                return self.reply(404,{"error":"Fichier inconnu."})
            file = app.exports / name
            if not file.is_file():
                return self.reply(404,{"error":"Fichier absent."})
            self.send_response(200)
            self.send_header("Content-Type","application/octet-stream")
            self.send_header("Content-Disposition",f'attachment; filename="{name}"')
            self.send_header("Content-Length",str(file.stat().st_size))
            self.end_headers()
            with file.open("rb") as stream:
                shutil.copyfileobj(stream,self.wfile,1024*1024)
            return
        if path == "/ATTRIBUTION.txt":
            return self.reply(200,ATTRIBUTION,"text/plain; charset=utf-8")
        static = ROOT / "static"
        file = (static / ("index.html" if path == "/" else urllib.parse.unquote(path).lstrip("/"))).resolve()
        if not file.is_relative_to(static) or not file.is_file():
            return self.reply(404,{"error":"Page introuvable."})
        mime = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        return self.reply(200,file.read_bytes(),mime,compressed=True)

    def do_POST(self):
        try:
            origin = self.headers.get("Origin")
            if origin and urllib.parse.urlsplit(origin).netloc != self.headers.get("Host"):
                return self.reply(403,{"error":"Origine non autorisée."})
            if self.headers.get("Content-Type","").split(";")[0] != "application/json":
                return self.reply(415,{"error":"Content-Type application/json requis."})
            length = int(self.headers.get("Content-Length",0))
            if not 0 < length <= 16384:
                raise ValueError("Requête trop grande ou vide.")
            self.connection.settimeout(20)
            obj = json.loads(self.rfile.read(length))
            if not isinstance(obj,dict):
                raise ValueError("Objet JSON attendu.")
            app = self.server.app
            if self.path == "/api/estimate":
                return self.reply(200,app.estimate(obj))
            if self.path == "/api/jobs":
                return self.reply(202,app.start_job(obj))
            if self.path == "/api/offline":
                if type(obj.get("offline")) is not bool:
                    raise ValueError("Mode hors ligne invalide.")
                with app.lock:
                    if any(j["state"] in ("running","queued") for j in app.jobs.values()):
                        raise ValueError("Attendez la fin de l’opération avant de changer de mode.")
                    app.store.offline = obj["offline"]
                return self.reply(200,{"offline":app.store.offline})
            match = re.fullmatch(r"/api/jobs/([a-f0-9]{32})/cancel",self.path)
            if match:
                with app.lock:
                    job = app.jobs.get(match[1])
                    if not job:
                        return self.reply(404,{"error":"Opération introuvable."})
                    job["cancel"] = True
                return self.reply(200,{"ok":True})
            self.reply(404,{"error":"Route inconnue."})
        except (ValueError,KeyError,TypeError) as exc:
            self.reply(400,{"error":str(exc)})
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass
        except Exception as exc:
            self.log_error("%s",exc)
            self.reply(500,{"error":"Erreur interne. Consultez le terminal du serveur."})


def local_addresses(port):
    addresses = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                addresses.add(f"http://{ip}:{port}")
    except OSError:
        pass
    return sorted(addresses)
