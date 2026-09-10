"""Real AWS DEM -> prepare -> fresh offline server -> three validated export formats."""
import io
import json
from pathlib import Path
import sqlite3
import sys
import threading
import time
import urllib.request
import zipfile
from contextlib import closing

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
import terrain
from server import Application, Server

ROOT=Path(__file__).resolve().parents[1]
URL='http://localhost:8765'


def request(base,path,obj=None):
    req=urllib.request.Request(base+path,data=None if obj is None else json.dumps(obj).encode(),headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=60) as response:return json.load(response)


def wait(base,job):
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        status=request(base,'/api/jobs/'+job['id'])
        if status['state'] in ('done','error','cancelled'):
            if status['state']!='done':raise AssertionError(status)
            return status
        time.sleep(.4)
    raise AssertionError('Job timeout')


def main():
    payload=dict(bounds=[6.84,45.90,6.90,45.94],minzoom=11,maxzoom=12,filters=dict(altitude=[1000,4800],slope=[25,55],aspects=[0,3],flats=True,opacity=175))
    estimate=request(URL,'/api/estimate',payload)
    print('Estimation réelle :',json.dumps(estimate),flush=True)
    wait(URL,request(URL,'/api/jobs',payload|{'kind':'prepare'}))
    # New application instance: no metrics in memory, same on-disk cache, no Internet.
    app=Application(ROOT/'data',ROOT/'exports',offline=True)
    local=Server(('127.0.0.1',0),app)
    thread=threading.Thread(target=local.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{local.server_port}'
    plan=terrain.plan_region(payload)
    outputs=[]
    try:
        for fmt in ['mbtiles','xyz','osmand']:
            result=wait(base,request(base,'/api/jobs',payload|{'kind':'export','format':fmt}))
            path=ROOT/'exports'/result['filename'];blobs=[]
            if fmt=='xyz':
                with zipfile.ZipFile(path) as archive:
                    assert archive.testzip() is None
                    blobs=[(z,x,y,archive.read(f'{z}/{x}/{y}.png')) for z,x,y in plan['tiles']]
            else:
                with closing(sqlite3.connect(path)) as db:
                    assert db.execute('pragma integrity_check').fetchone()[0]=='ok'
                    if fmt=='mbtiles':blobs=[(z,x,2**z-1-y,blob) for z,x,y,blob in db.execute('select zoom_level,tile_column,tile_row,tile_data from tiles')]
                    else:blobs=db.execute('select z,x,y,image from tiles').fetchall()
            assert len(blobs)==estimate['count']
            selected=0
            for z,x,y,blob in blobs:
                pixels=np.array(Image.open(io.BytesIO(blob)));assert pixels.shape==(256,256,4)
                expected=terrain.selection(app.store.metrics(z,x,y),terrain.Filters.parse(payload['filters'])) & terrain.clip_mask(z,x,y,payload['bounds'])
                np.testing.assert_array_equal(pixels[:,:,3]>0,expected)
                selected+=int(expected.sum())
            assert selected>0
            outputs.append(dict(format=fmt,path=str(path),tiles=len(blobs),selected_pixels=selected,bytes=path.stat().st_size))
            print('Export hors ligne vérifié :',json.dumps(outputs[-1]),flush=True)
        assert app.store.downloaded==0
        z,x,y=plan['tiles'][0]
        with urllib.request.urlopen(f'{base}/api/terrain/{z}/{x}/{y}') as response:
            assert len(response.read())==1048576
        report=dict(date=time.strftime('%Y-%m-%d %H:%M:%S'),estimate=estimate,offline_network_downloads=app.store.downloaded,exports=outputs)
        (ROOT/'test-results').mkdir(exist_ok=True)
        (ROOT/'test-results'/'real-data.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('OK : cache disque relu, trois formats corrects, zéro téléchargement hors ligne.',flush=True)
    finally:
        local.shutdown();local.server_close();thread.join()


if __name__=='__main__':main()
