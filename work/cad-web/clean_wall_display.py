from pathlib import Path
p=Path('work/cad_viewer.js');s=p.read_text('utf-8')
s=s.replace('color:0xafdae9,transparent:true,opacity:.25,side:T.DoubleSide,depthWrite:false','color:0xb9d4e6,transparent:true,opacity:.30,side:T.FrontSide,depthWrite:false,roughness:.9')
s=s.replace('color:0x8dc5df,transparent:true,opacity:.65','color:0x8dc5df,transparent:true,opacity:.22')
p.write_text(s,'utf-8')
p=Path('work/package_cad.py');s=p.read_text('utf-8')
s=s.replace('key not in ("labels","furniture")','key not in ("labels","furniture","outlines")')
s=s.replace('<output id="opacityValue">75%</output>','<output id="opacityValue">70%</output>').replace('max="95" value="75"','max="95" value="70"')
p.write_text(s,'utf-8')
