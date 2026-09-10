import sys,time,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import TileStore,write_export
import terrain
store=TileStore(Path('data/cache'),offline=True)
tiles=[]
for p in (store.path/'dem').glob('*/*/*.png'):
 z,x,y=int(p.parent.parent.name),int(p.parent.name),int(p.stem)
 if z>=9 and all(store.filename('dem',z,x+dx,y+dy).exists() for dx in (-1,0,1) for dy in (-1,0,1)):tiles.append((z,x,y))
tiles=sorted(tiles)[:96]
plan={'tiles':tiles,'count':len(tiles),'bounds':[-180,-85,180,85],'minzoom':min(t[0] for t in tiles),'maxzoom':max(t[0] for t in tiles)}
f=terrain.Filters.parse({"altitude":[0,8848.86],"slope":[25,55],"aspects":list(range(8)),"flats":True,"opacity":176})
results={}
with tempfile.TemporaryDirectory() as folder:
 for workers in (1,4):
  times=[]
  for repeat in range(3):
   store.metrics_cache.clear();store.decoded_cache.clear();start=time.perf_counter()
   write_export(Path(folder)/f'{workers}-{repeat}.mbtiles',plan,f,store,'mbtiles',False,lambda *_:None,lambda:False,workers=workers)
   times.append(round(time.perf_counter()-start,3))
  results[workers]=times
print(json.dumps({'real_cached_tiles':len(tiles),'seconds':results,'speedup':sum(results[1])/sum(results[4])}))

