"""Render original CAD vectors at room-review coordinates, without editing CAD."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'simulation/deps'),str(ROOT/'simulation/plot_deps')]
from PIL import Image,ImageDraw,ImageFont

def main(reader,floor_name):
    sys.path.insert(0,reader)
    from cadio import load,units_to_m
    b=json.loads((ROOT/'data/parkmarine-hotel/building.json').read_text('utf-8'));f=next(f for f in b['floors'] if f['name']==floor_name)
    out=ROOT/'reviews/cad-interior-arcs-20261104'
    doc,prims,_=load(str(out/'dxf'/f['src']));unit=units_to_m(doc,prims)
    def xy(p):return [p[i]*unit*f.get('scale',1)+f.get('shift',[0,0])[i]-b['origin'][i] for i in (0,1)]
    polys=[(r,part['o'] if isinstance(part,dict) else part) for r in f['rooms'] for part in r['polys']]
    points=[p for _,poly in polys for p in poly];xs=[p[0] for p in points];ys=[p[1] for p in points]
    views=[('floor',(min(xs)-.5,min(ys)-.5,max(xs)+.5,max(ys)+.5))]
    if floor_name in ('5F','6F','7F','8F'):views += [('core',(10.5,50.8,17,59.5)),('R4',(19.5,62.3,23,66))]
    for tag,(x0,y0,x1,y1) in views:
        scale=min(1800/(x1-x0),1800/(y1-y0));im=Image.new('RGB',(int((x1-x0)*scale)+40,int((y1-y0)*scale)+40),'white');draw=ImageDraw.Draw(im)
        def pixel(p):return (20+(p[0]-x0)*scale,20+(y1-p[1])*scale)
        for p in prims:
            pts=[xy(q) for q in p.pts]
            if len(pts)<2:continue
            if max(q[0] for q in pts)<x0 or min(q[0] for q in pts)>x1 or max(q[1] for q in pts)<y0 or min(q[1] for q in pts)>y1:continue
            draw.line([pixel(q) for q in pts],fill='#1d7198' if p.arc else '#505050',width=1)
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20)
        for r,poly in polys:
            xx=sum(q[0] for q in poly)/len(poly);yy=sum(q[1] for q in poly)/len(poly)
            if not (x0<xx<x1 and y0<yy<y1):continue
            if tag=='floor' and r['id'] in f['simulation_graph']['isolated_rooms']:
                draw.line([pixel(q) for q in poly+[poly[0]]],fill='#ed6a16',width=4)
            draw.text(pixel((xx,yy)),r['id'],font=font,fill='#d22a36',stroke_width=2,stroke_fill='white')
        im.save(out/f'CAD-{floor_name}-{tag}.png')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reader',required=True);p.add_argument('--floor',default='5F');a=p.parse_args();main(a.reader,a.floor)
