import io
import json
import math
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from contextlib import closing
from unittest.mock import patch

import numpy as np
from PIL import Image
import terrain as t
from server import Application, Server, TileStore, TileUnavailable, write_export, Cancelled


def encoded(heights):
    value=np.rint((np.asarray(heights)+32768)*256).astype(np.int64)
    rgb=np.stack(((value >> 16)&255,(value >> 8)&255,value&255),axis=-1).astype(np.uint8)
    output=io.BytesIO()
    Image.fromarray(rgb).save(output,format="PNG")
    return output.getvalue()


def filters(**changes):
    return t.Filters.parse(dict(altitude=[0,8848.86],slope=[0,90],aspects=list(range(8)),flats=True,opacity=175)|changes)


def bounds_of_tile(z,x,y):
    def lat(y):return math.degrees(math.atan(math.sinh(math.pi*(1-2*y/2**z))))
    return [x/2**z*360-180,lat(y+1),(x+1)/2**z*360-180,lat(y)]


class TerrainTests(unittest.TestCase):
    def test_rgb_fraction_zero_negative_nodata(self):
        heights=np.zeros((256,256));heights[0,:5]=[-10999.5,-20.125,0,2523.265625,8848.5]
        decoded=t.decode_terrarium(encoded(heights))
        np.testing.assert_array_equal(decoded,heights)
        pixels=np.array(Image.open(io.BytesIO(encoded(heights))).convert("RGBA"))
        pixels[1,1]=[0,0,0,255];pixels[1,2,3]=0
        output=io.BytesIO();Image.fromarray(pixels).save(output,format="PNG")
        result=t.decode_terrarium(output.getvalue())
        self.assertTrue(np.isnan(result[1,1]));self.assertTrue(np.isnan(result[1,2]));self.assertEqual(result[2,2],0)

    def test_all_cardinals_and_diagonals(self):
        yy,xx=np.mgrid[-1:257,-1:257]
        for azimuth in range(0,360,45):
            with self.subTest(azimuth=azimuth):
                # Independent analytic plane: descent vector (sin A, -cos A).
                slope=37.0;spacing=12.3;g=math.tan(math.radians(slope))
                h=1500+spacing*g*(-math.sin(math.radians(azimuth))*xx+math.cos(math.radians(azimuth))*yy)
                metric=t.horn(h,spacing)
                np.testing.assert_allclose(metric[1],slope,atol=1e-5)
                delta=(metric[2]-azimuth+180)%360-180
                np.testing.assert_allclose(delta,0,atol=1e-4)

    def test_latitude_resolution_and_row_variation(self):
        for lat in (0,45,75,-60):
            z=12;x,y=t.tile_position(0,lat,z);y=int(y)
            spacing=t.ground_resolution(z,y)
            rowlat=t.row_latitudes(z,y)
            expected=2*math.pi*6378137/(256*2**z)*np.cos(rowlat)
            np.testing.assert_allclose(spacing,expected,rtol=1e-14)
            # A plane linear in Mercator: the correct physical slope changes with latitude.
            yy,xx=np.mgrid[-1:257,-1:257]
            h=1000+xx*7.0
            metrics=t.horn(h,spacing)
            expected_slope=np.degrees(np.arctan(7/spacing))
            np.testing.assert_allclose(metrics[1,:,100],expected_slope,rtol=1e-6)
            np.testing.assert_allclose(metrics[2],270,atol=1e-5)
        equator=2*math.pi*t.RADIUS/(256*2**12)
        self.assertAlmostEqual(equator*math.cos(math.radians(60)),equator/2,places=10)

    def test_halo_preserves_slope_at_seams(self):
        def load(z,x,y):
            yy,xx=np.mgrid[:256,:256]
            return 3*(x*256+xx)+4*(y*256+yy)+200.0
        a=t.horn(t.padded_tile(4,7,6,load),10)
        b=t.horn(t.padded_tile(4,8,6,load),10)
        np.testing.assert_allclose(a[1],math.degrees(math.atan(.5)),atol=1e-5)
        np.testing.assert_array_equal(a[1,:,-1],b[1,:,0])
        np.testing.assert_array_equal(a[2,:,-1],b[2,:,0])

    def test_antimeridian_wrap_and_polar_no_neighbour(self):
        calls=[]
        def load(z,x,y):calls.append((z,x,y));return np.full((256,256),x*100+y,dtype=float)
        p=t.padded_tile(2,0,0,load)
        self.assertTrue(np.isnan(p[0]).all());self.assertEqual(p[1,0],300)
        self.assertIn((2,3,0),calls)
        metric=t.horn(p,t.ground_resolution(2,0))
        self.assertTrue(np.isnan(metric[:,0,:]).all());self.assertTrue(np.isfinite(metric[0,1:]).all())

    def test_nodata_propagates_full_neighbourhood(self):
        padded=np.ones((258,258));padded[101,101]=np.nan
        metric=t.horn(padded,30)
        self.assertEqual(np.isnan(metric[0]).sum(),9)
        self.assertFalse(t.selection(metric,filters())[99:102,99:102].any())

    def test_flat_is_separate_from_aspect(self):
        metric=t.horn(np.full((258,258),0.0),30)
        self.assertTrue(np.isnan(metric[2]).all());self.assertTrue((metric[1]==0).all())
        self.assertTrue(t.selection(metric,filters(aspects=[])).all())
        self.assertFalse(t.selection(metric,filters(flats=False)).any())
        self.assertFalse(t.selection(metric,filters(slope=[.1,90])).any())

    def test_north_wrap_and_inclusive_limits(self):
        angles=np.array([337.499,337.5,359.99,0,22.499,22.5,360,135],dtype=np.float32)
        metric=np.stack([np.full(8,1200),np.full(8,30),angles])
        expected=[False,True,True,True,True,False,True,False]
        np.testing.assert_array_equal(t.selection(metric,filters(altitude=[1200,1200],slope=[30,30],aspects=[0],flats=False)),expected)
        self.assertTrue(t.selection(metric,filters(aspects=[0,3]))[-1])

    def test_invalid_filter_inputs(self):
        for change in ({"altitude":[20,10]},{"altitude":[float('nan'),20]},{"slope":[0,91]},{"slope":[True,10]},{"aspects":[8]},{"aspects":[False]},{"aspects":None},{"flats":"yes"},{"opacity":300}):
            with self.subTest(change=change),self.assertRaises(ValueError):filters(**change)

    def test_tile_exact_bounds_and_mercator_limits(self):
        for z,x,y in [(0,0,0),(3,4,3),(14,8495,5841),(14,0,0),(14,16383,16383)]:
            with self.subTest(tile=(z,x,y)):
                plan=t.plan_region(dict(bounds=bounds_of_tile(z,x,y),minzoom=z,maxzoom=z))
                self.assertEqual(plan['tiles'],[(z,x,y)])
                self.assertTrue(t.clip_mask(z,x,y,plan['bounds']).all())

    def test_count_limit_invalid_bbox_and_zoom(self):
        base=dict(bounds=[6.8,45.8,7,46],minzoom=11,maxzoom=14)
        for change in ({"bounds":[-180,-85,180,85]},{"bounds":[170,0,-170,20]},{"bounds":[0,0,1,90]},{"bounds":[0,0,float('inf'),1]},{"minzoom":14,"maxzoom":11},{"maxzoom":15},{"minzoom":True}):
            with self.subTest(change=change),self.assertRaises(ValueError):t.plan_region(base|change)

    def test_subpixel_bbox_and_clipping(self):
        plan=t.plan_region(dict(bounds=[6.9,45.9,6.90000001,45.90000001],minzoom=14,maxzoom=14))
        self.assertEqual(plan['count'],1)
        b=bounds_of_tile(4,8,6);b[2]=(b[0]+b[2])/2
        clip=t.clip_mask(4,8,6,b)
        self.assertTrue(clip[:,:128].all());self.assertFalse(clip[:,128:].any())


class FakeStore:
    def metrics(self,z,x,y):
        yy,xx=np.mgrid[-1:257,-1:257]
        return t.horn(1000+xx*3+yy*4,20)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.plan=t.plan_region(dict(bounds=bounds_of_tile(4,8,6),minzoom=4,maxzoom=5))
    def tearDown(self):self.temp.cleanup()

    def test_mbtiles_sqlite_schema_tms_png_and_metadata(self):
        path=self.root/'test.mbtiles';progress=[]
        write_export(path,self.plan,filters(),FakeStore(),'mbtiles',False,lambda a,b:progress.append((a,b)),lambda:False)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('pragma integrity_check').fetchone()[0],'ok')
            meta=dict(db.execute('select name,value from metadata'))
            self.assertEqual(meta['format'],'png');self.assertEqual(meta['type'],'overlay');self.assertIn('Mapzen',meta['attribution'])
            rows=db.execute('select zoom_level,tile_column,tile_row,tile_data from tiles').fetchall()
            self.assertEqual(len(rows),5)
            self.assertEqual([(z,x,2**z-1-y) for z,x,y,_ in rows],self.plan['tiles'])
            for *_,blob in rows:
                img=Image.open(io.BytesIO(blob));self.assertEqual(img.size,(256,256));self.assertEqual(img.mode,'RGBA');self.assertEqual(img.getpixel((100,100)),(38,132,255,175))
        self.assertEqual(progress[-1],(5,5))

    def test_xyz_archive_and_osmand_direct_numbering(self):
        path=self.root/'test.zip'
        write_export(path,self.plan,filters(),FakeStore(),'xyz',True,lambda *_:None,lambda:False)
        with zipfile.ZipFile(path) as archive:
            self.assertIsNone(archive.testzip());meta=json.loads(archive.read('metadata.json'));self.assertEqual(meta['scheme'],'xyz')
            for z,x,y in self.plan['tiles']:self.assertIn(f'{z}/{x}/{y}.png',archive.namelist())
        path=self.root/'test.sqlitedb'
        write_export(path,self.plan,filters(),FakeStore(),'osmand',False,lambda *_:None,lambda:False)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute('select tilenumbering,inverted_y,minzoom,maxzoom from info').fetchone(),('simple',0,4,5))
            self.assertEqual(set(db.execute('select z,x,y from tiles')),set(self.plan['tiles']))

    def test_export_clip_transparency_and_no_matches(self):
        m=FakeStore().metrics(4,8,6);bounds=bounds_of_tile(4,8,6);bounds[2]=(bounds[0]+bounds[2])/2
        image=np.array(Image.open(io.BytesIO(t.png_tile(m,filters(),bounds,(4,8,6),True))))
        self.assertTrue((image[:,:128,3]==255).all());self.assertTrue((image[:,128:,3]==0).all())
        image=np.array(Image.open(io.BytesIO(t.png_tile(m,filters(aspects=[],flats=False)))))
        self.assertFalse(image[:,:,3].any())

    def test_cancel_stops_generation(self):
        with self.assertRaises(Cancelled):write_export(self.root/'cancel.mbtiles',self.plan,filters(),FakeStore(),'mbtiles',False,lambda *_:None,lambda:True)

    def test_custom_color_matches_all_export_formats(self):
        f=filters(color='#eC4899')
        self.assertEqual(f.color,'#ec4899')
        for fmt in ('mbtiles','xyz','osmand'):
            path=self.root/f'custom-{fmt}'
            write_export(path,self.plan,f,FakeStore(),fmt,False,lambda *_:None,lambda:False)
            if fmt=='xyz':
                with zipfile.ZipFile(path) as z:blob=z.read('4/8/6.png')
            else:
                with closing(sqlite3.connect(path)) as db:
                    blob=db.execute('SELECT '+('tile_data' if fmt=='mbtiles' else 'image')+' FROM tiles LIMIT 1').fetchone()[0]
                    self.assertIn('#ec4899',dict(db.execute('SELECT name,value FROM metadata'))['description'])
            self.assertEqual(Image.open(io.BytesIO(blob)).getpixel((100,100)),(236,72,153,175))
        metrics=FakeStore().metrics(4,8,6)
        base=t.relief_rgba(metrics)[100,100,:3]
        mixed=np.array(Image.open(io.BytesIO(t.png_tile(metrics,f,composite=True))))[100,100,:3]
        np.testing.assert_array_equal(mixed,np.rint(base*(1-175/255)+np.array([236,72,153])*175/255).astype(np.uint8))

    def test_altitude_and_color_validation(self):
        self.assertEqual(filters().altitude,(0,8848.86))
        for change in ({'altitude':[-.01,8848.86]},{'altitude':[0,8848.87]},{'color':'red'},{'color':'#fff'},{'color':'#12345z'},{'color':None},{'color':[0,0,0]}):
            with self.subTest(change=change),self.assertRaises(ValueError):filters(**change)

    def test_offline_cache_never_requests_network(self):
        store=TileStore(self.root/'cache',offline=True)
        path=store.filename('dem',4,8,6);path.parent.mkdir(parents=True);path.write_bytes(encoded(np.zeros((256,256))))
        with patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):
            self.assertTrue(store.tile('dem',4,8,6).startswith(b'\x89PNG'))
            with self.assertRaises(TileUnavailable):store.tile('dem',4,8,7)

    def test_failed_job_never_publishes_partial_file(self):
        app=Application(self.root/'data',self.root/'exports',offline=True)
        obj=dict(bounds=bounds_of_tile(4,8,6),minzoom=4,maxzoom=4,filters=dict(altitude=[0,4000],slope=[0,90],aspects=[0]))
        plan=t.plan_region(obj);job={'id':'a'*32,'kind':'export','cancel':False}
        app.run_job(job,obj,plan,filters(),'mbtiles',False)
        self.assertEqual(job['state'],'error');self.assertEqual(list(app.exports.iterdir()),[])


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();root=Path(cls.temp.name)
        cls.app=Application(root/'data',root/'exports',offline=True)
        cls.server=Server(('127.0.0.1',0),cls.app)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def request(self,path,data=None,headers=None):
        return urllib.request.urlopen(urllib.request.Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers=headers or {'Content-Type':'application/json'}))
    def test_local_assets_no_cdn(self):
        for path in ['/','/style.css','/app.js','/vendor/leaflet.js','/filters.js','/icon.svg']:
            with self.request(path) as response:self.assertEqual(response.status,200)
        with self.request('/') as response:
            html=response.read().decode();self.assertNotIn('src="https://',html)
    def test_missing_tile_reports_failure(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/terrain/4/8/6')
        self.assertEqual(ctx.exception.code,503)
    def test_path_traversal_and_bad_coordinates(self):
        for path in ['/../server.py','/%2e%2e/server.py','/api/terrain/15/0/0','/api/terrain/3/8/0']:
            with self.subTest(path=path),self.assertRaises(urllib.error.HTTPError):self.request(path)
    def test_foreign_origin_and_wrong_content_type(self):
        for headers in [{'Content-Type':'application/json','Origin':'https://evil.example'},{'Content-Type':'text/plain'}]:
            with self.assertRaises(urllib.error.HTTPError) as ctx:self.request('/api/offline',{'offline':False},headers)
            self.assertIn(ctx.exception.code,(403,415))
        self.assertTrue(self.app.store.offline)
    def test_estimate_validated_and_not_downloaded(self):
        with patch('urllib.request.urlopen',wraps=urllib.request.urlopen):
            with self.request('/api/estimate',dict(bounds=bounds_of_tile(4,8,6),minzoom=4,maxzoom=4)) as response:
                data=json.load(response);self.assertEqual(data['count'],1);self.assertEqual(data['missing'],9)
        self.assertEqual(self.app.store.downloaded,0)


if __name__=='__main__':unittest.main(verbosity=2)
