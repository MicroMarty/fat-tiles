/* Shared scalar predicate: also exercised by the Node/Python parity tests. */
(function(root){
  'use strict';
  const FLAT_DEGREES=Math.atan(1e-7)*180/Math.PI*1.001;
  function sector(aspect){return Math.floor(((aspect+22.5)%360+360)%360/45);}
  function matches(h,s,a,f){
    if(!Number.isFinite(h)||!Number.isFinite(s)||h<f.altitude[0]||h>f.altitude[1]||s<f.slope[0]||s>f.slope[1]) return false;
    return Number.isFinite(a)?f.aspects.includes(sector(a)):(f.flats&&s<=FLAT_DEGREES);
  }
  function rgb(color){
    if(!/^#[0-9a-fA-F]{6}$/.test(color)) throw new Error('Couleur invalide');
    return [1,3,5].map(i=>parseInt(color.slice(i,i+2),16));
  }
  const api={sector,matches,rgb};
  if(typeof module!=='undefined'&&module.exports) module.exports=api;
  else root.FatFilters=api;
})(typeof window!=='undefined'?window:globalThis);
