const {test}=require('node:test');
const assert=require('node:assert/strict');
const {matches,sector,rgb}=require('../static/filters.js');
const f={altitude:[1000,2000],slope:[0,45],aspects:[0,3],flats:true};
test('shared RGB decoding preserves blue and custom colors',()=>{
  assert.deepEqual(rgb('#2684ff'),[38,132,255]);assert.deepEqual(rgb('#eC4899'),[236,72,153]);
  for(const color of ['red','#fff','#12345z'])assert.throws(()=>rgb(color));
});
test('north wraps through zero with deterministic half-open sectors',()=>{
  for(const a of [337.5,359.999,0,22.499,360])assert.equal(sector(a),0);
  assert.equal(sector(22.5),1);assert.equal(sector(337.499),7);
});
test('inclusive ranges and cardinal unions',()=>{
  assert.equal(matches(1000,45,135,f),true);assert.equal(matches(2000,0,0,f),true);
  assert.equal(matches(999,45,0,f),false);assert.equal(matches(1500,45.01,0,f),false);assert.equal(matches(1500,30,180,f),false);
});
test('flats, empty selection and missing values',()=>{
  assert.equal(matches(1200,0,NaN,f),true);assert.equal(matches(1200,0,NaN,{...f,flats:false}),false);
  assert.equal(matches(NaN,0,0,f),false);assert.equal(matches(1200,NaN,0,f),false);
  assert.equal(matches(1200,30,NaN,f),false);assert.equal(matches(1200,30,0,{...f,aspects:[]}),false);
});
test('Python / browser parity on seeded random float32 terrain and threshold edges',()=>{
  const {execFileSync}=require('node:child_process');
  const script=`import json, numpy as np, terrain as t\nrng=np.random.default_rng(2026)\nm=np.stack([rng.uniform(-11000,9000,2000),rng.uniform(0,90,2000),rng.uniform(0,360,2000)]).astype('float32')\nm[:,:9]=np.array([[1000,2000,999,1500,1500,1500,1500,1500,1500],[45,0,45,30,30,0,30,30,30],[135,0,0,337.5,22.5,np.nan,np.nan,359.99,337.499]])\nf=dict(altitude=[1000,2000],slope=[0,45],aspects=[0,3],flats=True)\nprint(json.dumps(dict(values=[[None if np.isnan(v) else float(v) for v in row] for row in m.T],selected=t.selection(m,t.Filters.parse(f)).tolist())))`;
  const fixture=JSON.parse(execFileSync('python',['-c',script],{cwd:require('node:path').join(__dirname,'..'),encoding:'utf8'}));
  assert.deepEqual(fixture.values.map(row=>matches(...row.map(v=>v===null?NaN:v),f)),fixture.selected);
});
